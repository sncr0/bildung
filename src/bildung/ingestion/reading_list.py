"""Parse reading_list.txt and seed Neo4j.

Format:
    Pre-2019:
    Author Name - Title (LANG)

    2019 - 8
    Author Name - Title (LANG)

Each line: "Author - Title (LANG)"  — language code is 2-letter (EN/NL/FR/DE/…).
Trailing junk (e.g. a bare "v") after the closing paren is ignored.
Multi-author lines use " & " as separator.

Usage:
    uv run python -m bildung.ingestion.reading_list
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from neo4j import AsyncDriver
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bildung.config import load_settings
from bildung.db.neo4j import build_driver, init_constraints
from bildung.db.postgres import build_engine, build_session_factory
from bildung.ids import author_id as _author_id
from bildung.ids import work_id as _work_id

logger = logging.getLogger(__name__)

# Matches:  Author(s) - Title (XX)  with optional trailing noise
_ENTRY_RE = re.compile(r"^(.+?)\s+-\s+(.+?)\s*\(([A-Z]{2,3})\)\s*\S*\s*$")

# Matches section headers like "2024 - 3" or "2024 - 0 :(" or "Pre-2019:"
_HEADER_RE = re.compile(r"^(Pre-\d{4}|\d{4})\s*[-:]")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ParsedEntry:
    authors: list[str]      # split on " & "
    title: str
    language_read_in: str   # "EN", "NL", "FR", …
    year_read: int | None   # from section header; None for Pre-2019


@dataclass
class IngestionResult:
    created_authors: int = 0
    existing_authors: int = 0
    created_works: int = 0
    existing_works: int = 0
    errors: list[str] = field(default_factory=list)
    skipped_lines: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Works:   {self.created_works} created, {self.existing_works} already existed\n"
            f"Authors: {self.created_authors} created, {self.existing_authors} already existed\n"
            f"Errors:  {len(self.errors)}\n"
            f"Skipped: {len(self.skipped_lines)} unparsed lines"
        )


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_reading_list(text: str) -> list[ParsedEntry]:
    entries: list[ParsedEntry] = []
    current_year: int | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Section header?
        if _HEADER_RE.match(line):
            year_str = _HEADER_RE.match(line).group(1)
            if year_str.startswith("Pre-"):
                current_year = None
            else:
                current_year = int(year_str)
            continue

        # Book entry?
        m = _ENTRY_RE.match(line)
        if m:
            raw_authors, title, lang = m.group(1), m.group(2), m.group(3)
            authors = [a.strip() for a in raw_authors.split(" & ") if a.strip()]
            entries.append(ParsedEntry(
                authors=authors,
                title=title.strip(),
                language_read_in=lang.upper(),
                year_read=current_year,
            ))
        else:
            logger.debug("Skipped unparsed line: %r", line)

    return entries


# ---------------------------------------------------------------------------
# Neo4j writer
# ---------------------------------------------------------------------------

async def _upsert_author(session, name: str) -> bool:
    """Returns True if newly created."""
    aid = _author_id(name)
    # Check existence first
    exists_result = await session.run(
        "MATCH (a:Author {id: $id}) RETURN count(a) AS n", id=aid
    )
    record = await exists_result.single()
    if record and record["n"] > 0:
        return False  # already exists

    await session.run(
        "CREATE (a:Author {id: $id, name: $name})",
        id=aid,
        name=name,
    )
    return True


async def _upsert_work(session, entry: ParsedEntry, primary_author: str) -> bool:
    """Returns True if newly created."""
    wid = _work_id(entry.title, primary_author)
    exists_result = await session.run(
        "MATCH (w:Work {id: $id}) RETURN count(w) AS n", id=wid
    )
    record = await exists_result.single()
    if record and record["n"] > 0:
        return False

    date_read = str(entry.year_read) if entry.year_read else None
    await session.run(
        """
        CREATE (w:Work {
            id:               $id,
            title:            $title,
            status:           'read',
            language_read_in: $language_read_in,
            date_read:        $date_read,
            source_type:      'fiction'
        })
        """,
        id=wid,
        title=entry.title,
        language_read_in=entry.language_read_in,
        date_read=date_read,
    )
    return True


async def _link_author_work(session, primary_author: str, title: str) -> None:
    aid = _author_id(primary_author)
    wid = _work_id(title, primary_author)
    await session.run(
        """
        MATCH (a:Author {id: $aid})
        MATCH (w:Work {id: $wid})
        MERGE (a)-[:WROTE]->(w)
""",
        aid=aid,
        wid=wid,
    )


async def _pg_upsert_author(pg: AsyncSession, name: str) -> None:
    aid = _author_id(name)
    await pg.execute(
        text("INSERT INTO authors (id, name) VALUES (:id, :name) ON CONFLICT (id) DO NOTHING"),
        {"id": uuid.UUID(aid), "name": name},
    )


async def _pg_upsert_work(pg: AsyncSession, entry: ParsedEntry, primary_author: str) -> None:
    wid = _work_id(entry.title, primary_author)
    date_read = str(entry.year_read) if entry.year_read else None
    await pg.execute(
        text("""
            INSERT INTO works (id, title, status, language_read_in, date_read, source_type)
            VALUES (:id, :title, 'read', :language_read_in, :date_read, 'fiction')
            ON CONFLICT (id) DO NOTHING
        """),
        {"id": uuid.UUID(wid), "title": entry.title,
         "language_read_in": entry.language_read_in, "date_read": date_read},
    )


async def _pg_link_author_work(pg: AsyncSession, author_name: str, title: str, primary_author: str) -> None:
    aid = _author_id(author_name)
    wid = _work_id(title, primary_author)
    await pg.execute(
        text("INSERT INTO work_authors (work_id, author_id) VALUES (:wid, :aid) ON CONFLICT DO NOTHING"),
        {"wid": uuid.UUID(wid), "aid": uuid.UUID(aid)},
    )


async def ingest(
    entries: list[ParsedEntry],
    driver: AsyncDriver,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> IngestionResult:
    result = IngestionResult()

    async with driver.session() as session:
        for entry in entries:
            try:
                primary_author = entry.authors[0]

                # Authors
                for author_name in entry.authors:
                    created = await _upsert_author(session, author_name)
                    if created:
                        result.created_authors += 1
                        logger.info("  + Author: %s", author_name)
                    else:
                        result.existing_authors += 1

                # Work
                created = await _upsert_work(session, entry, primary_author)
                if created:
                    result.created_works += 1
                    logger.info("  + Work:   %s — %s", primary_author, entry.title)
                else:
                    result.existing_works += 1

                # WROTE edges
                for author_name in entry.authors:
                    await _link_author_work(session, author_name, entry.title)
                    if author_name != primary_author:
                        aid = _author_id(author_name)
                        wid = _work_id(entry.title, primary_author)
                        await session.run(
                            """
                            MATCH (a:Author {id: $aid}), (w:Work {id: $wid})
                            MERGE (a)-[:WROTE]->(w)
                            """,
                            aid=aid,
                            wid=wid,
                        )

            except Exception as exc:
                msg = f"{entry.authors} - {entry.title}: {exc}"
                result.errors.append(msg)
                logger.error("Error ingesting %r: %s", entry.title, exc)

    # Mirror to PostgreSQL
    if session_factory is not None:
        async with session_factory() as pg:
            for entry in entries:
                try:
                    primary_author = entry.authors[0]
                    for author_name in entry.authors:
                        await _pg_upsert_author(pg, author_name)
                    await _pg_upsert_work(pg, entry, primary_author)
                    for author_name in entry.authors:
                        await _pg_link_author_work(pg, author_name, entry.title, primary_author)
                except Exception as exc:
                    logger.error("PG ingestion error for %r: %s", entry.title, exc)
            await pg.commit()

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def _main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = load_settings()

    reading_list_path = Path(__file__).resolve().parents[4] / "reading_list.txt"
    if not reading_list_path.exists():
        # Try cwd
        reading_list_path = Path("reading_list.txt")
    if not reading_list_path.exists():
        raise FileNotFoundError("reading_list.txt not found")

    logger.info("Parsing %s …", reading_list_path)
    entries = parse_reading_list(reading_list_path.read_text(encoding="utf-8"))
    logger.info("Parsed %d entries", len(entries))

    driver = build_driver(settings)
    engine = build_engine(settings)
    pg_factory = build_session_factory(engine)
    await init_constraints(driver)

    logger.info("Ingesting into Neo4j + PostgreSQL …")
    result = await ingest(entries, driver, session_factory=pg_factory)
    await driver.close()
    await engine.dispose()

    print("\n--- Ingestion complete ---")
    print(result.summary())
    if result.errors:
        print("\nErrors:")
        for e in result.errors:
            print(f"  {e}")


if __name__ == "__main__":
    asyncio.run(_main())
