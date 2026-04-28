# Task 2C — Repository + Ingestion Migration to PostgreSQL

## Kickoff

### Read Before Starting
1. **This spec** (you're reading it)
2. **Next task spec:** `TASK_5A.md` — YAML enrichment data. That task rewrites the enrichment pipeline to read YAML and write to PostgreSQL. It depends on the ingestion script already writing to PostgreSQL. If the `reading_list.py` ingestion is still Neo4j-only after this task, Task 5A can't build on it.
3. **Architecture reference:** `02_target_architecture.md` → "Data Flow: Read Path" (PostgreSQL for 95% of reads, Neo4j for graph traversals only) + "Data Flow: Write Path" (write PG first, sync graph edges to Neo4j).
4. **Migration data:** Verify `migrate_neo4j_to_pg.py` has been run and PG tables have data.

### Pre-conditions
- [ ] Task 2B is complete (data migrated to PG)
- [ ] PostgreSQL entity tables have data (run count checks)
- [ ] Backend starts and all endpoints work (still reading from Neo4j)

### Lessons from Previous Task
_To be populated by Task 2B implementer._

---

## Spec

### Goal

Switch repository reads from Neo4j to PostgreSQL. Update repository writes to write PostgreSQL first (system of record), then sync graph edges to Neo4j. Update the ingestion pipeline to write to both stores. After this task, PostgreSQL is the system of record and Neo4j is the relationship engine.

### What This Enables

This completes the database architecture migration. PostgreSQL handles all entity reads (fast, indexed, joinable). Neo4j handles only graph traversals (which don't exist yet — Phase 2+ features). Task 5A can build the enrichment pipeline on PostgreSQL.

### Files to Modify

```
src/bildung/repositories/base.py
src/bildung/repositories/works.py
src/bildung/repositories/authors.py
src/bildung/repositories/collections.py
src/bildung/repositories/streams.py
src/bildung/repositories/series.py
src/bildung/services/stats.py
src/bildung/dependencies.py
src/bildung/app_state.py          — (maybe — if repos need session_factory)
src/bildung/ingestion/reading_list.py
src/bildung/ingestion/seed_enrichments.py
```

### Files NOT to Modify

```
src/bildung/models/domain.py     — DO NOT CHANGE.
src/bildung/models/api.py        — DO NOT CHANGE.
src/bildung/models/postgres.py   — DO NOT CHANGE (unless adding a missing column found during migration).
src/bildung/routers/*.py         — DO NOT CHANGE.
src/bildung/main.py              — DO NOT CHANGE.
```

### Exact Changes

#### Part 1: Update Base Repository

The base repository needs to support both Neo4j (for graph edge writes) and PostgreSQL (for entity reads/writes):

```python
"""Base repositories — Neo4j for graph, PostgreSQL for entities."""
from __future__ import annotations

from neo4j import AsyncDriver, Record
from sqlalchemy.ext.asyncio import AsyncSession


class NeoRepository:
    """Base for repositories that talk to Neo4j (graph edges only)."""
    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def _run(self, query: str, **params: object) -> list[Record]:
        async with self._driver.session() as session:
            result = await session.run(query, params)
            return [r async for r in result]

    async def _run_single(self, query: str, **params: object) -> Record | None:
        async with self._driver.session() as session:
            result = await session.run(query, params)
            return await result.single()


class PgRepository:
    """Base for repositories that read/write PostgreSQL."""
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
```

#### Part 2: Rewrite Entity Repositories

Each entity repository changes from `NeoRepository` subclass to a class that uses both `PgRepository` (for reads/writes) and `NeoRepository` (for graph edge management).

**Pattern:**

```python
class WorkRepository:
    def __init__(self, pg_session: AsyncSession, neo4j_driver: AsyncDriver) -> None:
        self._pg = pg_session
        self._neo = neo4j_driver

    async def list(self, ...) -> list[Work]:
        # PostgreSQL query with JOINs
        result = await self._pg.execute(
            text("""
                SELECT w.*, array_agg(DISTINCT jsonb_build_object('id', a.id::text, 'name', a.name))
                    FILTER (WHERE a.id IS NOT NULL) AS authors
                FROM works w
                LEFT JOIN work_authors wa ON wa.work_id = w.id
                LEFT JOIN authors a ON a.id = wa.author_id
                WHERE (:status IS NULL OR w.status = :status)
                GROUP BY w.id
                ORDER BY w.title
                LIMIT :limit OFFSET :offset
            """),
            {"status": status, "limit": limit, "offset": offset},
        )
        return [self._row_to_work(row) for row in result]

    async def create(self, ...) -> Work:
        # 1. INSERT into works table
        # 2. INSERT into work_authors junction
        # 3. MERGE graph edges in Neo4j (WROTE relationship)
        ...

    @staticmethod
    def _row_to_work(row) -> Work:
        """Map a PostgreSQL row to domain Work."""
        ...
```

**Critical detail:** The `list()` and `get()` methods now use SQL `SELECT` with JOINs instead of Cypher `MATCH`. The `create()` and `update()` methods write PostgreSQL first, then sync Neo4j edges.

**For Neo4j edge sync on writes:**
```python
async def _sync_wrote_edge(self, author_id: str, work_id: str) -> None:
    """Ensure WROTE edge exists in Neo4j."""
    async with self._neo.session() as session:
        await session.run(
            """
            MERGE (a:Author {id: $aid})
            MERGE (w:Work {id: $wid})
            MERGE (a)-[:WROTE]->(w)
            """,
            aid=author_id, wid=work_id,
        )
```

Neo4j edge sync is fire-and-forget. If it fails, log a warning — PostgreSQL is the system of record.

#### Part 3: Rewrite Stats Service

`services/stats.py` currently runs 6 Cypher queries. Rewrite them as PostgreSQL queries:

```python
class StatsService:
    def __init__(self, pg_session: AsyncSession) -> None:
        self._pg = pg_session

    async def get_stats(self) -> Stats:
        # total_works: SELECT count(*) FROM works
        # total_authors: SELECT count(*) FROM authors
        # total_streams: SELECT count(*) FROM streams
        # by_status: SELECT status, count(*) FROM works GROUP BY status
        # by_year: SELECT date_read, count(*) FROM works WHERE date_read IS NOT NULL GROUP BY ...
        # by_language: SELECT language_read_in, count(*) FROM works WHERE language_read_in IS NOT NULL GROUP BY ...
        ...
```

#### Part 4: Update `dependencies.py`

Repository factories need to provide both `AsyncSession` and `AsyncDriver`:

```python
async def get_work_repo(
    request: Request,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> WorkRepository:
    driver = get_app_state(request).neo4j_driver
    return WorkRepository(pg_session=pg_session, neo4j_driver=driver)
```

#### Part 5: Update Ingestion Scripts

`ingestion/reading_list.py` currently writes only to Neo4j. Update it to write to both PostgreSQL and Neo4j:

1. INSERT entity rows into PostgreSQL
2. MERGE nodes and edges in Neo4j (for graph structure)

`ingestion/seed_enrichments.py` — same pattern: update PostgreSQL rows AND Neo4j node properties.

### Key Design Decisions (and why)

**1. PostgreSQL for reads, dual-write for mutations.**
Reads come from PostgreSQL (fast, indexed, JOIN-capable). Writes go to PostgreSQL first (system of record), then Neo4j (for graph edges). This matches the target architecture.

**2. Raw SQL with `text()`, not ORM queries.**
The repository queries involve JOINs, aggregations, and array construction that are cleaner in raw SQL than in SQLAlchemy ORM query syntax. ORM would add complexity without benefit.

**3. Neo4j sync failures are logged, not raised.**
If the PostgreSQL write succeeds but the Neo4j edge sync fails, the data is still correct — it's just not in the graph yet. A background reconciliation job could fix drift, but for a single-user app, manual re-running of the migration is sufficient.

**4. `by_year` stats query parses `date_read` strings.**
The current Neo4j query extracts year from `date_read`. In PostgreSQL, this is `LEFT(date_read, 4)` since `date_read` is a VARCHAR storing "2024", "2024-03", or "2024-03-15".

### DO NOT

1. **Do not change API response shapes.** Every endpoint must return the exact same JSON structure as before. Test by comparing responses before and after.

2. **Do not remove Neo4j writes.** The graph still needs edge data for future Phase 2+ features. Write to both stores.

3. **Do not add caching.** PostgreSQL with indexes is fast enough for a single-user app. No Redis, no in-memory cache, no query result caching.

4. **Do not create PostgreSQL views or materialized views.** Inline SQL in repositories is clearer for this scale.

5. **Do not change the `models/postgres.py` ORM models** unless you discover a missing column that prevents the migration from working. Document any changes in the handoff.

6. **Do not remove Neo4j node properties.** Nodes in Neo4j should retain their properties for now. Stripping them to ID-only is a later optimization.

7. **Do not change router files.** Routers depend on services. Services depend on repositories. Only repositories and services change.

### Acceptance Criteria

- [ ] All `list()` and `get()` repository methods query PostgreSQL, not Neo4j
- [ ] All `create()` and `update()` methods write PostgreSQL first, then sync Neo4j edges
- [ ] Stats service queries PostgreSQL, not Neo4j
- [ ] `dependencies.py` provides both `AsyncSession` and `AsyncDriver` to repositories
- [ ] All endpoints return the same data as before (compare JSON field by field)
- [ ] `ingestion/reading_list.py` writes to both PostgreSQL and Neo4j
- [ ] `ingestion/seed_enrichments.py` updates both PostgreSQL and Neo4j
- [ ] Backend starts without errors
- [ ] Performance is comparable (no noticeable slowdown on any endpoint)

### Verification

```bash
# Save current responses for comparison
curl -s http://localhost:8000/works > /tmp/works_before.json
curl -s http://localhost:8000/authors > /tmp/authors_before.json
curl -s http://localhost:8000/streams > /tmp/streams_before.json
curl -s http://localhost:8000/stats > /tmp/stats_before.json

# After implementation: compare
curl -s http://localhost:8000/works > /tmp/works_after.json
curl -s http://localhost:8000/authors > /tmp/authors_after.json

# Compare key fields (exact JSON comparison may differ on ordering)
python3 -c "
import json
before = json.load(open('/tmp/works_before.json'))
after = json.load(open('/tmp/works_after.json'))
print(f'Before: {len(before)} works, After: {len(after)} works')
# Check first work matches
if before and after:
    b0 = before[0]
    a0 = next((w for w in after if w['id'] == b0['id']), None)
    if a0:
        for key in b0:
            if b0[key] != a0.get(key):
                print(f'  DIFF {key}: {b0[key]!r} -> {a0.get(key)!r}')
"

# Backend health
curl -s http://localhost:8000/health

# All endpoints respond
for endpoint in works authors streams stats; do
    code=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/$endpoint)
    echo "$endpoint: $code"
done
```

---

## Handoff

_Fill in after completing this task:_

### Decisions Made
<!-- E.g., "Used LEFT(date_read, 4) for year extraction in stats" -->

### Harder Than Expected
<!-- E.g., "Author detail query with nested collections was complex in SQL" -->

### Watch Out (for Task 5A)
<!-- E.g., "Ingestion now uses both PG session and Neo4j driver — seed_enrichments needs both" -->

### Deviations from Spec
<!-- Did you deviate? Why? -->
