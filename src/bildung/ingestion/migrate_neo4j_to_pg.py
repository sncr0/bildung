"""One-shot migration: Neo4j → PostgreSQL.

Reads all nodes and relationships from Neo4j, writes them to the
PostgreSQL entity tables created in Task 2A.

Run with:
    uv run python -m bildung.ingestion.migrate_neo4j_to_pg

Idempotent: uses INSERT ... ON CONFLICT DO NOTHING so it can be re-run safely.
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from neo4j import AsyncDriver
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bildung.config import load_settings
from bildung.db.neo4j import build_driver
from bildung.db.postgres import build_engine, build_session_factory

logger = logging.getLogger(__name__)


async def migrate_authors(driver: AsyncDriver, session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with driver.session() as neo:
        result = await neo.run("MATCH (a:Author) RETURN a {.*} AS author")
        authors = [r["author"] async for r in result]

    count = 0
    async with session_factory() as pg:
        for a in authors:
            aid = a.get("id", "")
            if not aid:
                logger.warning("Author missing id, skipping: %s", a.get("name"))
                continue
            try:
                await pg.execute(
                    text("""
                        INSERT INTO authors (id, name, birth_year, death_year, nationality, primary_language, openlibrary_id)
                        VALUES (:id, :name, :birth_year, :death_year, :nationality, :primary_language, :openlibrary_id)
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": uuid.UUID(aid),
                        "name": a.get("name", ""),
                        "birth_year": a.get("birth_year"),
                        "death_year": a.get("death_year"),
                        "nationality": a.get("nationality"),
                        "primary_language": a.get("primary_language"),
                        "openlibrary_id": a.get("openlibrary_id"),
                    },
                )
                count += 1
            except (ValueError, AttributeError) as e:
                logger.warning("Skipping author id=%s: %s", aid, e)
        await pg.commit()
    return count


async def migrate_works(driver: AsyncDriver, session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with driver.session() as neo:
        result = await neo.run("MATCH (w:Work) RETURN w {.*} AS work")
        works = [r["work"] async for r in result]

    count = 0
    async with session_factory() as pg:
        for w in works:
            wid = w.get("id", "")
            if not wid:
                logger.warning("Work missing id, skipping: %s", w.get("title"))
                continue
            try:
                await pg.execute(
                    text("""
                        INSERT INTO works (id, title, status, language_read_in, date_read,
                            density_rating, source_type, personal_note, edition_note,
                            significance, page_count, year_published, original_language,
                            original_title, openlibrary_id, isbn, cover_url)
                        VALUES (:id, :title, :status, :language_read_in, :date_read,
                            :density_rating, :source_type, :personal_note, :edition_note,
                            :significance, :page_count, :year_published, :original_language,
                            :original_title, :openlibrary_id, :isbn, :cover_url)
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": uuid.UUID(wid),
                        "title": w.get("title", ""),
                        "status": w.get("status", "to_read"),
                        "language_read_in": w.get("language_read_in"),
                        "date_read": w.get("date_read"),
                        "density_rating": w.get("density_rating"),
                        "source_type": w.get("source_type", "fiction"),
                        "personal_note": w.get("personal_note"),
                        "edition_note": w.get("edition_note"),
                        "significance": w.get("significance"),
                        "page_count": w.get("page_count"),
                        "year_published": w.get("year_published"),
                        "original_language": w.get("original_language"),
                        "original_title": w.get("original_title"),
                        "openlibrary_id": w.get("openlibrary_id"),
                        "isbn": w.get("isbn"),
                        "cover_url": w.get("cover_url"),
                    },
                )
                count += 1
            except (ValueError, AttributeError) as e:
                logger.warning("Skipping work id=%s: %s", wid, e)
        await pg.commit()
    return count


async def migrate_collections(driver: AsyncDriver, session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with driver.session() as neo:
        result = await neo.run("MATCH (c:Collection) RETURN c {.*} AS collection")
        collections = [r["collection"] async for r in result]

    count = 0
    async with session_factory() as pg:
        for c in collections:
            cid = c.get("id", "")
            if not cid:
                logger.warning("Collection missing id, skipping: %s", c.get("name"))
                continue
            try:
                author_id_raw = c.get("author_id")
                author_id = uuid.UUID(author_id_raw) if author_id_raw else None
                await pg.execute(
                    text("""
                        INSERT INTO collections (id, name, description, type, author_id)
                        VALUES (:id, :name, :description, :type, :author_id)
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": uuid.UUID(cid),
                        "name": c.get("name", ""),
                        "description": c.get("description"),
                        "type": c.get("type", "anthology"),
                        "author_id": author_id,
                    },
                )
                count += 1
            except (ValueError, AttributeError) as e:
                logger.warning("Skipping collection id=%s: %s", cid, e)
        await pg.commit()
    return count


async def migrate_streams(driver: AsyncDriver, session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with driver.session() as neo:
        result = await neo.run("MATCH (s:Stream) RETURN s {.*} AS stream")
        streams = [r["stream"] async for r in result]

    count = 0
    async with session_factory() as pg:
        for s in streams:
            sid = s.get("id", "")
            if not sid:
                logger.warning("Stream missing id, skipping: %s", s.get("name"))
                continue
            try:
                await pg.execute(
                    text("""
                        INSERT INTO streams (id, name, description, color)
                        VALUES (:id, :name, :description, :color)
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": uuid.UUID(sid),
                        "name": s.get("name", ""),
                        "description": s.get("description"),
                        "color": s.get("color"),
                    },
                )
                count += 1
            except (ValueError, AttributeError) as e:
                logger.warning("Skipping stream id=%s: %s", sid, e)
        await pg.commit()
    return count


async def migrate_series(driver: AsyncDriver, session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with driver.session() as neo:
        result = await neo.run("MATCH (s:Series) RETURN s {.*} AS series")
        series_list = [r["series"] async for r in result]

    count = 0
    async with session_factory() as pg:
        for s in series_list:
            sid = s.get("id", "")
            if not sid:
                logger.warning("Series missing id, skipping: %s", s.get("name"))
                continue
            try:
                await pg.execute(
                    text("""
                        INSERT INTO series (id, name, description)
                        VALUES (:id, :name, :description)
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": uuid.UUID(sid),
                        "name": s.get("name", ""),
                        "description": s.get("description"),
                    },
                )
                count += 1
            except (ValueError, AttributeError) as e:
                logger.warning("Skipping series id=%s: %s", sid, e)
        await pg.commit()
    return count


async def migrate_relationships(
    driver: AsyncDriver, session_factory: async_sessionmaker[AsyncSession]
) -> dict[str, int]:
    counts: dict[str, int] = {}

    # WROTE → work_authors
    async with driver.session() as neo:
        result = await neo.run(
            "MATCH (a:Author)-[:WROTE]->(w:Work) RETURN a.id AS author_id, w.id AS work_id"
        )
        rels = [dict(r) async for r in result]

    async with session_factory() as pg:
        migrated = 0
        for r in rels:
            try:
                await pg.execute(
                    text("INSERT INTO work_authors (work_id, author_id) VALUES (:wid, :aid) ON CONFLICT DO NOTHING"),
                    {"wid": uuid.UUID(r["work_id"]), "aid": uuid.UUID(r["author_id"])},
                )
                migrated += 1
            except (ValueError, AttributeError) as e:
                logger.warning("Skipping WROTE rel work=%s author=%s: %s", r.get("work_id"), r.get("author_id"), e)
        await pg.commit()
    counts["work_authors"] = migrated

    # IN_COLLECTION → work_collections (Work)-[:IN_COLLECTION]->(Collection)
    async with driver.session() as neo:
        result = await neo.run(
            "MATCH (w:Work)-[r:IN_COLLECTION]->(c:Collection) RETURN w.id AS work_id, c.id AS collection_id, r.order AS ord"
        )
        rels = [dict(r) async for r in result]

    async with session_factory() as pg:
        migrated = 0
        for r in rels:
            try:
                await pg.execute(
                    text("""
                        INSERT INTO work_collections (work_id, collection_id, "order")
                        VALUES (:wid, :cid, :ord)
                        ON CONFLICT DO NOTHING
                    """),
                    {"wid": uuid.UUID(r["work_id"]), "cid": uuid.UUID(r["collection_id"]), "ord": r.get("ord")},
                )
                migrated += 1
            except (ValueError, AttributeError) as e:
                logger.warning("Skipping IN_COLLECTION rel: %s", e)
        await pg.commit()
    counts["work_collections"] = migrated

    # IN_STREAM → collection_streams (Collection)-[:IN_STREAM]->(Stream)
    async with driver.session() as neo:
        result = await neo.run(
            "MATCH (c:Collection)-[r:IN_STREAM]->(s:Stream) RETURN c.id AS collection_id, s.id AS stream_id, r.order AS ord"
        )
        rels = [dict(r) async for r in result]

    async with session_factory() as pg:
        migrated = 0
        for r in rels:
            try:
                await pg.execute(
                    text("""
                        INSERT INTO collection_streams (collection_id, stream_id, "order")
                        VALUES (:cid, :sid, :ord)
                        ON CONFLICT DO NOTHING
                    """),
                    {"cid": uuid.UUID(r["collection_id"]), "sid": uuid.UUID(r["stream_id"]), "ord": r.get("ord")},
                )
                migrated += 1
            except (ValueError, AttributeError) as e:
                logger.warning("Skipping IN_STREAM rel: %s", e)
        await pg.commit()
    counts["collection_streams"] = migrated

    # BELONGS_TO → work_streams (Work)-[:BELONGS_TO]->(Stream)
    async with driver.session() as neo:
        result = await neo.run(
            "MATCH (w:Work)-[r:BELONGS_TO]->(s:Stream) RETURN w.id AS work_id, s.id AS stream_id, r.position AS position"
        )
        rels = [dict(r) async for r in result]

    async with session_factory() as pg:
        migrated = 0
        for r in rels:
            try:
                await pg.execute(
                    text("""
                        INSERT INTO work_streams (work_id, stream_id, position)
                        VALUES (:wid, :sid, :pos)
                        ON CONFLICT DO NOTHING
                    """),
                    {"wid": uuid.UUID(r["work_id"]), "sid": uuid.UUID(r["stream_id"]), "pos": r.get("position")},
                )
                migrated += 1
            except (ValueError, AttributeError) as e:
                logger.warning("Skipping BELONGS_TO rel: %s", e)
        await pg.commit()
    counts["work_streams"] = migrated

    # PART_OF → work_series (Work)-[:PART_OF]->(Series)
    async with driver.session() as neo:
        result = await neo.run(
            "MATCH (w:Work)-[r:PART_OF]->(s:Series) RETURN w.id AS work_id, s.id AS series_id, r.order AS ord"
        )
        rels = [dict(r) async for r in result]

    async with session_factory() as pg:
        migrated = 0
        for r in rels:
            try:
                await pg.execute(
                    text("""
                        INSERT INTO work_series (work_id, series_id, "order")
                        VALUES (:wid, :sid, :ord)
                        ON CONFLICT DO NOTHING
                    """),
                    {"wid": uuid.UUID(r["work_id"]), "sid": uuid.UUID(r["series_id"]), "ord": r.get("ord")},
                )
                migrated += 1
            except (ValueError, AttributeError) as e:
                logger.warning("Skipping PART_OF rel: %s", e)
        await pg.commit()
    counts["work_series"] = migrated

    return counts


async def validate(driver: AsyncDriver, session_factory: async_sessionmaker[AsyncSession]) -> None:
    checks = [
        ("Author", "authors"),
        ("Work", "works"),
        ("Collection", "collections"),
        ("Stream", "streams"),
        ("Series", "series"),
    ]
    for label, table in checks:
        async with driver.session() as neo:
            result = await neo.run(f"MATCH (n:{label}) RETURN count(n) AS c")
            record = await result.single()
            neo_count = record["c"] if record else 0
        async with session_factory() as pg:
            result = await pg.execute(text(f"SELECT count(*) FROM {table}"))
            pg_count = result.scalar()
        status = "OK" if neo_count == pg_count else "MISMATCH"
        logger.info("%s: Neo4j=%d  PG=%d  [%s]", label, neo_count, pg_count, status)
        if neo_count != pg_count:
            logger.warning("Count mismatch for %s! Neo4j has %d, PG has %d", label, neo_count, pg_count)


async def _main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = load_settings()
    driver = build_driver(settings)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)

    try:
        logger.info("=== Starting Neo4j → PostgreSQL migration ===")

        n = await migrate_authors(driver, session_factory)
        logger.info("Authors: %d migrated", n)

        n = await migrate_works(driver, session_factory)
        logger.info("Works: %d migrated", n)

        n = await migrate_collections(driver, session_factory)
        logger.info("Collections: %d migrated", n)

        n = await migrate_streams(driver, session_factory)
        logger.info("Streams: %d migrated", n)

        n = await migrate_series(driver, session_factory)
        logger.info("Series: %d migrated", n)

        rel_counts = await migrate_relationships(driver, session_factory)
        for name, count in rel_counts.items():
            logger.info("%s: %d relationships migrated", name, count)

        logger.info("=== Validating counts ===")
        await validate(driver, session_factory)

        logger.info("=== Migration complete ===")
    finally:
        await driver.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
