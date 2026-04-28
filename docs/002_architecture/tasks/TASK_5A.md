# Task 5A — YAML Enrichment Data + Deterministic Matching

## Kickoff

### Read Before Starting
1. **This spec** (you're reading it)
2. **Next task spec:** `TASK_5B.md` — OpenLibrary enrichment integration. That task wires up the OpenLibrary client to the enrichment pipeline. It needs the enrichment script to already read YAML and write to PostgreSQL. If enrichments are still Python constants after this task, Task 5B has to handle both the format change and the API integration.
3. **Architecture reference:** `02_target_architecture.md` → target module structure shows `ingestion/data/*.yaml` and `ingestion/enrichments.py`.
4. **Current enrichment code:** `ingestion/seed_enrichments.py` — 500+ lines of Python constants (significance ratings, collection definitions, stream definitions). Read this file carefully to understand what data exists.

### Pre-conditions
- [ ] Task 2C is complete (repositories write to PostgreSQL)
- [ ] Backend starts and reads from PostgreSQL
- [ ] PostgreSQL entity tables have data

### Lessons from Previous Task
_To be populated by Task 2C implementer._

---

## Spec

### Goal

Move the 500+ lines of hardcoded Python enrichment data from `seed_enrichments.py` into structured YAML files. Replace the CONTAINS-based fuzzy matching with deterministic ID lookups using `ids.py`. Rename `seed_enrichments.py` to `enrichments.py` and rewrite it to read YAML and write to PostgreSQL (with Neo4j edge sync).

### What This Enables

Task 5B (OpenLibrary integration) adds API-sourced enrichments to the pipeline. With YAML as the data format, adding new enrichment data is a file edit, not a code change. With deterministic matching, enrichments are idempotent and reliable — no more "Dostoyevsky" matching "Dostoyevski" by accident.

### Files to Create

```
src/bildung/ingestion/data/significance.yaml
src/bildung/ingestion/data/authors.yaml
src/bildung/ingestion/data/streams.yaml
src/bildung/ingestion/data/collections.yaml
```

### Files to Modify

```
src/bildung/ingestion/seed_enrichments.py  — Rename to enrichments.py, rewrite
```

### Files NOT to Modify

```
src/bildung/models/*.py          — DO NOT CHANGE.
src/bildung/repositories/*.py    — DO NOT CHANGE.
src/bildung/services/*.py        — DO NOT CHANGE.
src/bildung/routers/*.py         — DO NOT CHANGE.
src/bildung/ingestion/reading_list.py — DO NOT CHANGE.
```

### Exact Changes

#### YAML Data Files

Convert the Python constants into YAML. The structure should mirror the data exactly — don't reformat, regroup, or "improve" the organization.

##### `data/significance.yaml`

```yaml
# Which works are "major" or "minor" for each author.
# Matched by deterministic IDs: ids.work_id(title, author)

- author: Dostoyevsky
  works:
    - title: "Crime and Punishment"
      significance: major
    - title: "The Idiot"
      significance: major
    - title: "The Brothers Karamazov"
      significance: major
    - title: "Notes from the Underground"
      significance: major
    - title: "Demons"
      significance: major
    - title: "Adolescent"
      significance: major
    - title: "Bobok"
      significance: minor
    - title: "White Nights"
      significance: minor
    # ... all entries from SIGNIFICANCE constant ...

- author: Kafka
  works:
    - title: "The Trial"
      significance: major
    # ... etc ...
```

##### `data/authors.yaml`

```yaml
# Author metadata enrichments — birth_year, death_year, nationality, primary_language.
# Matched by deterministic ID: ids.author_id(name)

- name: Dostoyevsky
  birth_year: 1821
  death_year: 1881
  nationality: Russian
  primary_language: Russian

- name: Kafka
  birth_year: 1883
  death_year: 1924
  nationality: Czech (Bohemian)
  primary_language: German
  # ... all entries from AUTHOR_METADATA constant ...
```

##### `data/streams.yaml`

```yaml
# Reading streams — curated intellectual paths.
# ID generated from: ids.stream_id(name)

- name: Russian Greats
  description: "Deep dive into the Russian literary canon"
  color: "#dc2626"

- name: Existentialist Thread
  description: "From Kierkegaard through Sartre and Camus"
  color: "#7c3aed"
  # ... all entries from STREAMS constant ...
```

##### `data/collections.yaml`

```yaml
# Collections — groupings of works by author.
# ID generated from: ids.collection_id(name)

- name: "Dostoyevsky: Major Works"
  type: major_works
  author: Dostoyevsky
  works:
    - title: "Crime and Punishment"
      order: 1
    - title: "The Idiot"
      order: 2
    # ... all works in this collection ...

- name: "Dostoyevsky: Minor Works"
  type: minor_works
  author: Dostoyevsky
  works:
    - title: "Bobok"
    - title: "White Nights"
    # ... etc ...
```

**Important:** Convert ALL data from `seed_enrichments.py`. Do not skip entries. Count the entries in Python and count them in YAML — they should match.

#### `enrichments.py` (renamed from `seed_enrichments.py`)

Rewrite to:
1. Read YAML files
2. Generate deterministic IDs using `ids.py`
3. Write to PostgreSQL (UPDATE existing rows)
4. Sync Neo4j edges where needed (collection membership, stream assignment)

```python
"""Enrichment pipeline — reads YAML data files, updates PostgreSQL + Neo4j.

Run with:
    uv run python -m bildung.ingestion.enrichments
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bildung.config import load_settings
from bildung.db.neo4j import build_driver
from bildung.db.postgres import build_engine, build_session_factory
from bildung.ids import author_id, collection_id, stream_id, work_id

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"


def _load_yaml(filename: str) -> list[dict]:
    """Load a YAML data file."""
    path = DATA_DIR / filename
    with open(path) as f:
        return yaml.safe_load(f)


async def apply_significance(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Set significance on works."""
    data = _load_yaml("significance.yaml")
    count = 0
    async with session_factory() as pg:
        for group in data:
            author_name = group["author"]
            for entry in group["works"]:
                wid = work_id(entry["title"], author_name)
                await pg.execute(
                    text("UPDATE works SET significance = :sig WHERE id = :id"),
                    {"sig": entry["significance"], "id": wid},
                )
                count += 1
        await pg.commit()
    return count


async def apply_author_metadata(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Update author metadata (birth_year, death_year, etc.)."""
    data = _load_yaml("authors.yaml")
    count = 0
    async with session_factory() as pg:
        for entry in data:
            aid = author_id(entry["name"])
            await pg.execute(
                text("""
                    UPDATE authors SET
                        birth_year = :birth_year,
                        death_year = :death_year,
                        nationality = :nationality,
                        primary_language = :primary_language
                    WHERE id = :id
                """),
                {
                    "id": aid,
                    "birth_year": entry.get("birth_year"),
                    "death_year": entry.get("death_year"),
                    "nationality": entry.get("nationality"),
                    "primary_language": entry.get("primary_language"),
                },
            )
            count += 1
        await pg.commit()
    return count


# ... apply_streams(), apply_collections() follow the same pattern ...
# Each reads YAML, generates IDs, writes to PostgreSQL, syncs Neo4j edges.


async def _main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = load_settings()
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    driver = build_driver(settings)

    try:
        n = await apply_significance(session_factory)
        logger.info("Significance: %d works updated", n)

        n = await apply_author_metadata(session_factory)
        logger.info("Authors: %d updated", n)

        n = await apply_streams(session_factory, driver)
        logger.info("Streams: %d created/updated", n)

        n = await apply_collections(session_factory, driver)
        logger.info("Collections: %d created/updated", n)

        logger.info("Enrichment complete")
    finally:
        await driver.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
```

### Key Design Decisions (and why)

**1. YAML over JSON or TOML.**
YAML supports comments (useful for documenting why a work is "major"), is more readable for nested lists, and is the standard for configuration data. JSON doesn't support comments. TOML is for config files, not data files.

**2. Deterministic IDs, not CONTAINS matching.**
The current script uses `MATCH (w:Work) WHERE w.title CONTAINS $title` — this is fuzzy and fragile. "The Idiot" would match "The Idiot of the Family." Using `ids.work_id(title, author)` generates the exact UUID that the work was created with, so the match is always exact.

**3. UPDATE, not UPSERT for enrichments.**
Enrichments modify existing works/authors, they don't create new ones. If a work doesn't exist in the database, the UPDATE silently affects 0 rows — that's fine. The ingestion pipeline (`reading_list.py`) creates entities; the enrichment pipeline decorates them.

**4. Rename `seed_enrichments.py` → `enrichments.py`.**
"Seed" implies one-shot. This script is idempotent and re-runnable. "Enrichments" better describes its purpose.

### DO NOT

1. **Do not change the data values.** Copy the exact significance ratings, author metadata, stream definitions, and collection definitions from `seed_enrichments.py`. Do not "fix" typos, reorder entries, or update metadata.

2. **Do not add new enrichment data.** Only migrate what exists. New data is a separate concern.

3. **Do not create a generic YAML loader framework.** Each YAML file has a specific schema. Write a specific loader for each, not a generic one.

4. **Do not add YAML schema validation.** The data is hand-curated and small. Schema validation adds complexity without benefit. If YAML is malformed, `yaml.safe_load` will raise a clear error.

5. **Do not install `pyyaml` if it's already a dependency.** Check `pyproject.toml` first. If not present, add it.

6. **Do not delete `seed_enrichments.py` without creating `enrichments.py` first.** Rename, don't delete-and-create.

7. **Do not modify `reading_list.py`.** The ingestion pipeline for reading_list.txt is separate from enrichments.

### Acceptance Criteria

- [ ] 4 YAML files exist in `src/bildung/ingestion/data/`
- [ ] `enrichments.py` exists (renamed from `seed_enrichments.py`)
- [ ] `enrichments.py` reads YAML files and uses deterministic IDs
- [ ] No CONTAINS-based matching anywhere in `enrichments.py`
- [ ] All enrichment data from `seed_enrichments.py` is present in YAML files (count entries)
- [ ] `uv run python -m bildung.ingestion.enrichments` runs without errors
- [ ] After running, works have significance values, authors have metadata
- [ ] Script is idempotent (running twice produces same results)
- [ ] Backend still starts and all endpoints work
- [ ] `pyyaml` is in dependencies (if it wasn't already)

### Verification

```bash
# YAML files exist
ls src/bildung/ingestion/data/
# Expected: significance.yaml, authors.yaml, streams.yaml, collections.yaml

# No fuzzy matching
grep -n "CONTAINS" src/bildung/ingestion/enrichments.py
# Expected: 0 results

# Run enrichments
uv run python -m bildung.ingestion.enrichments

# Verify data was applied
uv run python -c "
from sqlalchemy import create_engine, text
from bildung.config import load_settings
cfg = load_settings()
engine = create_engine(cfg.pg_dsn.replace('+asyncpg', ''))
with engine.connect() as conn:
    sig_count = conn.execute(text('SELECT count(*) FROM works WHERE significance IS NOT NULL')).scalar()
    meta_count = conn.execute(text('SELECT count(*) FROM authors WHERE birth_year IS NOT NULL')).scalar()
    print(f'Works with significance: {sig_count}')
    print(f'Authors with metadata: {meta_count}')
"

# Backend works
curl -s http://localhost:8000/authors | python3 -c "
import json,sys
authors = json.load(sys.stdin)
with_meta = [a for a in authors if a.get('birth_year')]
print(f'{len(with_meta)} authors have metadata')
"
```

---

## Handoff

_Fill in after completing this task:_

### Decisions Made
<!-- E.g., "Added pyyaml to dependencies — it wasn't there before" -->

### Harder Than Expected
<!-- E.g., "Collection YAML needed to include author name for ID generation, not just collection name" -->

### Watch Out (for Task 5B)
<!-- E.g., "enrichments.py expects specific YAML structure — Task 5B needs to match it" -->

### Deviations from Spec
<!-- Did you deviate? Why? -->
