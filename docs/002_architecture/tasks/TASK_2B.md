# Task 2B — Neo4j → PostgreSQL Data Migration

## Kickoff

### Read Before Starting
1. **This spec** (you're reading it)
2. **Next task spec:** `TASK_2C.md` — Repository + ingestion migration to PG. That task switches repository reads from Neo4j to PostgreSQL. It assumes the data is already in PostgreSQL. If the migration script misses data or maps fields incorrectly, Task 2C will serve stale/wrong data and every endpoint will be subtly broken.
3. **Architecture reference:** `02_target_architecture.md` → "PostgreSQL is the system of record" section + "The bridge: Work and Author rows in PostgreSQL have UUIDs. Neo4j nodes have the same UUIDs."
4. **Schema reference:** `models/postgres.py` — know the exact column names, types, and constraints.

### Pre-conditions
- [ ] Task 2A is complete (entity tables exist in PostgreSQL)
- [ ] `uv run alembic upgrade head` has been run
- [ ] All 10 tables exist in PostgreSQL (5 entities + 5 junctions)
- [ ] Neo4j is running and contains data
- [ ] Both databases are reachable

### Lessons from Previous Task
_To be populated by Task 2A implementer._

---

## Spec

### Goal

Create a one-shot migration script that reads all nodes and relationships from Neo4j and writes them to the corresponding PostgreSQL tables. After running, PostgreSQL has a complete copy of all entity data and relationship data. Neo4j retains its data (it's still the active read source until Task 2C switches repositories).

### What This Enables

Task 2C will switch repository reads from Neo4j to PostgreSQL. Without data in PostgreSQL, those reads return empty results and every endpoint breaks.

### Files to Create

```
src/bildung/ingestion/migrate_neo4j_to_pg.py
```

### Files NOT to Modify

```
src/bildung/models/postgres.py      — DO NOT CHANGE.
src/bildung/repositories/*.py       — DO NOT CHANGE.
src/bildung/services/*.py           — DO NOT CHANGE.
alembic/versions/*.py               — DO NOT CHANGE.
```

### Exact Changes

#### `ingestion/migrate_neo4j_to_pg.py`

A standalone async script that:
1. Connects to Neo4j (reads)
2. Connects to PostgreSQL (writes)
3. Migrates all entities in dependency order
4. Migrates all relationships (junction tables)
5. Validates counts match

```python
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
    """Migrate Author nodes."""
    async with driver.session() as neo:
        result = await neo.run("MATCH (a:Author) RETURN a {.*} AS author")
        authors = [r["author"] async for r in result]

    count = 0
    async with session_factory() as pg:
        for a in authors:
            aid = a.get("id", "")
            if not aid:
                continue
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
        await pg.commit()
    return count


async def migrate_works(driver: AsyncDriver, session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Migrate Work nodes."""
    async with driver.session() as neo:
        result = await neo.run("MATCH (w:Work) RETURN w {.*} AS work")
        works = [r["work"] async for r in result]

    count = 0
    async with session_factory() as pg:
        for w in works:
            wid = w.get("id", "")
            if not wid:
                continue
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
        await pg.commit()
    return count


# ... same pattern for collections, streams, series ...
# Each reads MATCH (n:Label) RETURN n {.*} and INSERTs into the PG table.


async def migrate_relationships(driver: AsyncDriver, session_factory: async_sessionmaker[AsyncSession]) -> dict[str, int]:
    """Migrate all relationship types to junction tables."""
    counts = {}

    # WROTE → work_authors
    async with driver.session() as neo:
        result = await neo.run(
            "MATCH (a:Author)-[:WROTE]->(w:Work) RETURN a.id AS author_id, w.id AS work_id"
        )
        rels = [dict(r) async for r in result]

    async with session_factory() as pg:
        for r in rels:
            await pg.execute(
                text("INSERT INTO work_authors (work_id, author_id) VALUES (:wid, :aid) ON CONFLICT DO NOTHING"),
                {"wid": uuid.UUID(r["work_id"]), "aid": uuid.UUID(r["author_id"])},
            )
        await pg.commit()
    counts["work_authors"] = len(rels)

    # IN_COLLECTION → work_collections (with order)
    # IN_STREAM → collection_streams (with order)
    # BELONGS_TO → work_streams (with position)
    # PART_OF → work_series (with order)
    # ... same pattern for each relationship type ...

    return counts


async def validate(driver: AsyncDriver, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Compare Neo4j and PostgreSQL counts."""
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
            neo_count = (await result.single())["c"]
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

        # Entities (order matters: authors before works, authors before collections)
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

        # Relationships
        rel_counts = await migrate_relationships(driver, session_factory)
        for name, count in rel_counts.items():
            logger.info("%s: %d relationships migrated", name, count)

        # Validate
        logger.info("=== Validating counts ===")
        await validate(driver, session_factory)

        logger.info("=== Migration complete ===")
    finally:
        await driver.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
```

The code above is illustrative — implement the full version with all 5 entity migration functions and all 5 relationship migration functions.

### Key Design Decisions (and why)

**1. `ON CONFLICT DO NOTHING` makes the script idempotent.**
Running it twice doesn't duplicate data. This is critical for a migration script — if it fails halfway, you can re-run without cleaning up.

**2. Raw SQL (`text()`) instead of ORM `insert()`.**
The ORM models exist but using raw SQL here is simpler and more explicit. The migration is a one-shot script, not production code. Clarity over elegance.

**3. Entities are migrated in dependency order.**
Authors before collections (because `collections.author_id` is a FK to `authors.id`). Works before junction tables (because junction tables FK to `works.id`).

**4. IDs are converted from `str` to `uuid.UUID`.**
Neo4j stores IDs as strings. PostgreSQL columns are `UUID`. The migration script does `uuid.UUID(str_id)` for every ID. If an ID is not a valid UUID, the script should log a warning and skip that record.

**5. Validation compares counts, not individual records.**
A full record-by-record comparison is overkill for a personal project. Count matching catches the common failure modes (missed labels, FK violations, type conversion errors).

### DO NOT

1. **Do not delete Neo4j data.** The migration copies data; it does not move it. Neo4j is still the active read source until Task 2C switches repositories.

2. **Do not modify the PostgreSQL schema.** If a Neo4j property doesn't have a matching column, log a warning and skip it. Do not add columns on the fly.

3. **Do not use the ORM models for insertion.** Use raw `text()` SQL. The ORM models may have defaults or server_defaults that interfere with migrating exact values (e.g., `created_at` should come from Neo4j if available, not from `server_default=func.now()`).

4. **Do not handle `created_at` from Neo4j specially.** Most Neo4j nodes don't have `created_at` (only Streams do). For nodes without it, let the PostgreSQL `server_default=func.now()` fill it in. For Streams, migrate the `created_at` string.

5. **Do not batch inserts.** With <500 works and <100 authors, row-by-row insertion is fast enough. Batch optimization adds complexity for zero benefit.

6. **Do not add a "rollback" function.** If the migration is wrong, `TRUNCATE` the tables and re-run. A programmatic rollback is over-engineering.

7. **Do not modify any repository, service, or router files.** This is a standalone script.

### Acceptance Criteria

- [ ] `ingestion/migrate_neo4j_to_pg.py` exists and is runnable
- [ ] Script migrates all Authors, Works, Collections, Streams, Series
- [ ] Script migrates all relationships: WROTE, IN_COLLECTION, IN_STREAM, BELONGS_TO, PART_OF
- [ ] Uses `ON CONFLICT DO NOTHING` for idempotency
- [ ] Validates counts after migration (Neo4j count == PG count for each entity)
- [ ] IDs are proper UUIDs in PostgreSQL
- [ ] Script can be re-run without errors
- [ ] Neo4j data is untouched after running
- [ ] Backend still works after running (Neo4j is still the active source)

### Verification

```bash
# Run the migration
uv run python -m bildung.ingestion.migrate_neo4j_to_pg

# Check counts
uv run python -c "
from sqlalchemy import create_engine, text
from bildung.config import load_settings
cfg = load_settings()
engine = create_engine(cfg.pg_dsn.replace('+asyncpg', ''))
with engine.connect() as conn:
    for table in ['works', 'authors', 'collections', 'streams', 'series',
                  'work_authors', 'work_collections', 'work_streams',
                  'collection_streams', 'work_series']:
        count = conn.execute(text(f'SELECT count(*) FROM {table}')).scalar()
        print(f'{table}: {count} rows')
"

# Re-run should be safe (idempotent)
uv run python -m bildung.ingestion.migrate_neo4j_to_pg
# Expected: same counts, no errors

# Backend still works
curl -s http://localhost:8000/works | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d)} works')"
curl -s http://localhost:8000/authors | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d)} authors')"
```

---

## Handoff

_Fill in after completing this task:_

### Decisions Made
<!-- E.g., "Streams have created_at as ISO string — stored in PG as VARCHAR, not TIMESTAMP" -->

### Harder Than Expected
<!-- E.g., "Some Neo4j nodes had null IDs — had to skip them" -->

### Watch Out (for Task 2C)
<!-- E.g., "collection_streams table has X rows — verify repos return the right count" -->

### Deviations from Spec
<!-- Did you deviate? Why? -->
