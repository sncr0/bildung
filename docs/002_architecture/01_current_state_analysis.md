# 01 — Current State Analysis

This document identifies structural problems in the Bildung codebase that will compound as features are added. The issues are grouped by severity and architectural layer.

---

## Critical: Database Architecture

### Neo4j is used as a relational database

This is the single biggest architectural problem. Every service function writes ad-hoc Cypher that does `MATCH (w:Work)` with property filters — this is relational SQL thinking wrapped in graph syntax. The actual graph relationships (`WROTE`, `BELONGS_TO`, `IN_COLLECTION`, `IN_STREAM`) are used as simple foreign key joins, never for the thing that justifies a graph database: **multi-hop traversals, path finding, and pattern matching across relationship chains**.

Example — `list_works()` in `services/works.py`:
```cypher
MATCH (w:Work)
WHERE $status IS NULL OR w.status = $status
OPTIONAL MATCH (a:Author)-[:WROTE]->(w)
```
This is a property filter with a left join. PostgreSQL does this with an index scan. The same query in SQL would be faster and simpler.

**Why this matters for Phase 2+:** When `READ_BECAUSE_OF` and `SAME_THREAD_AS` edges arrive, and when the quiz system needs to find "works in Stream A that connect to works in Stream B via shared authors or personal edges," the graph will finally justify itself. But the current code establishes a pattern where Neo4j is treated as a property store, which will fight the graph-native queries that Phase 2 actually needs.

**The correct split:** Neo4j should own relationships and traversals. PostgreSQL should own entities and their scalar properties. Right now, Work nodes store 12+ scalar properties in Neo4j that would be better served by a SQL table with proper types, constraints, and indexing.

### Dual-database writes have no consistency guarantee

`create_work()` and `update_work()` in `services/works.py` write to both Neo4j and PostgreSQL:

```python
async with driver.session() as session:
    async with await session.begin_transaction() as tx:
        # Neo4j writes...

# ... then separately:
if req.status == "read":
    await _record_reading_event(pg_session, wid, "finished", req.date_read)
```

If Neo4j succeeds but PostgreSQL fails (connection drop, constraint violation), the work exists in the graph but the reading event is lost. There's no saga, no compensation, no outbox pattern. The two writes aren't even in the same try/except block.

**Risk:** Every cross-database operation is a potential consistency hole. As more features add cross-database side-effects (XP ledger entries, quiz generation triggers), this compounds.

### PostgreSQL is 80% dead weight

Five tables exist (`reading_events`, `xp_ledger`, `quiz_questions`, `quiz_attempts`, `srs_schedule`). Only `reading_events` is ever written to. The XP engine, quiz system, and SRS scheduler are unimplemented — the tables are scaffolding with no code behind them.

This isn't inherently a problem (schema-first is fine), but it means:
- Alembic migrations are maintaining phantom tables
- The SQLAlchemy models suggest completeness that doesn't exist
- Test stubs reference "Step 7" and "Step 9" that were never implemented

---

## Critical: Service Layer

### Raw Cypher strings are scattered and duplicated

Every service function contains inline Cypher as multi-line Python strings. There are **30+ Cypher queries** across 5 service files, with no abstraction, no parameterization beyond `$variables`, and no way to test or lint them independently.

The same structural pattern appears everywhere:
```cypher
MATCH (entity:Label {id: $id})
OPTIONAL MATCH (related)-[:REL]->(entity)
WITH entity {.*} AS e, collect({id: related.id, name: related.name}) AS related_list
RETURN e, related_list
```

This is duplicated with slight variations for works, authors, collections, streams, and series. Changes to the Work node schema require grep-and-update across all service files.

### `_record_to_work()` is a public interface pretending to be private

`services/works.py` defines `_record_to_work()` with a leading underscore, signaling "private." But it's imported by 4 other modules:

- `services/authors.py` — `from bildung.services.works import _record_to_work`
- `services/streams.py` — same
- `services/collections.py` — same
- `services/series.py` — same

This function is the central record-to-model mapper for the entire system. It takes raw Neo4j dicts and produces `WorkResponse` objects. Every service depends on it. If it changes signature or behavior, 4 files break.

### No repository abstraction

Services open Neo4j sessions directly, run queries, and map results manually. There's no intermediate layer that owns "how to talk to Neo4j." Compare to finalysis, which has `BaseRepository` providing `conn` and `query_df()`, with specific repositories inheriting domain logic.

The consequence: every service function has 3 concerns tangled together:
1. Session lifecycle management (`async with driver.session() as session:`)
2. Query construction (inline Cypher strings)
3. Result mapping (manual `.get()` calls on raw dicts)

### `routers/stats.py` bypasses the service layer

The stats router contains 6 raw Cypher queries directly in the endpoint handler — no service function, no separation of concerns. This violates the project's own convention from CLAUDE.md: "Neo4j queries in Cypher, keep them in service functions not inline in routers."

```python
# In routers/stats.py — Cypher directly in the handler:
total_works = (await (await s.run(
    "MATCH (w:Work) RETURN count(w) AS n"
)).single())["n"]
```

### Update operations are non-atomic

`update_work()` does read-then-write:
```python
current = await get_work(driver, work_id)  # READ
# ...
await session.run("MATCH (w:Work {id: $id}) SET w += $updates", ...)  # WRITE
# ...
return await get_work(driver, work_id)  # READ again
```

Three database round-trips, no optimistic concurrency, no transaction wrapping the read+write. If two clients update the same work simultaneously, the second write silently wins. The final read returns fresh data that may not match what was written.

The same pattern exists in `update_stream()`, `update_collection()`, `update_series()`.

---

## High: Frontend Architecture

### No data layer or caching

Every page component independently fetches data with `useEffect` + `useState`:

```typescript
useEffect(() => {
    getWorks({ status, author }).then(setWorks).finally(() => setLoading(false));
}, [status, author]);
```

Consequences:
- Navigate to WorkList (fetches 50 works), click a work (fetches work detail + author detail + streams), press back — WorkList refetches all 50 works
- `getStreams()` is called independently by WorkList, WorkDetail, and StreamList — 3 identical requests if the user visits all three pages
- No stale-while-revalidate, no background refetch, no cache invalidation
- Every page starts with "Loading..." on every navigation

### Duplicated UI components

The following are copy-pasted across 4-5 files with minor variations:

| Component | Duplicated in |
|-----------|--------------|
| `STATUS_COLORS` (Record) | WorkList, WorkDetail, AuthorDetail, StreamDetail, CollectionDetail |
| `WorkRow` component | AuthorDetail, StreamDetail, CollectionDetail |
| `ProgressBar` component | AuthorDetail, StreamDetail, CollectionDetail |
| `TYPE_LABEL` / `COLLECTION_TYPE_LABEL` | AuthorDetail, StreamDetail, CollectionDetail |

There is no `components/` directory despite `BILDUNG.md` specifying one in the project structure.

### No error handling for the user

Failed API calls are handled with `.catch(console.error)` — the error goes to the browser console, the user sees a perpetual "Loading..." or stale data. There are no:
- Error boundaries
- Error states in the UI
- Retry buttons
- Toast notifications
- Fallback rendering

### No pagination in the frontend

The API supports `limit` and `offset`, but the frontend never sends them. `getWorks()`, `getAuthors()`, `getStreams()` all fetch everything in one call. At 85 works this is fine; at 500+ it won't be.

---

## High: Testing

### 3 of 4 test files are empty stubs

```python
# tests/test_works.py
# Works API tests — implemented in Step 9

# tests/test_ingestion.py
# Ingestion pipeline tests — implemented in Step 9

# tests/test_xp.py
# XP calculation tests — implemented in Step 7
```

"Step 7" and "Step 9" were never implemented. The only real test file (`test_openlibrary.py`) hits the live OpenLibrary API with no mocking — it fails if the machine is offline.

There are **zero tests** for:
- Service functions (the core business logic)
- Router endpoints
- XP calculation (which BILDUNG.md calls "the core game mechanic")
- Ingestion pipeline correctness
- ID generation parity between ingestion and API
- Cross-database consistency
- Neo4j query correctness

### No test infrastructure

No `conftest.py`. No test fixtures. No database containers (no testcontainers). No factory functions for test data. Compare to finalysis, which has session-scoped PostgreSQL containers, per-test database wiping, and AppState injection for API tests.

---

## Medium: Ingestion Pipeline

### Fuzzy matching in `seed_enrichments.py`

The enrichment script matches works/authors using `toLower(w.title) CONTAINS toLower($title)`:

```cypher
MATCH (a:Author)-[:WROTE]->(w:Work)
WHERE toLower(a.name) CONTAINS toLower($author)
  AND toLower(w.title) CONTAINS toLower($title)
SET w.significance = $sig
```

"The Trial" matches both "The Trial" and "The Trial of Socrates." "Mann" matches both "Thomas Mann" and "Hofmannsthal." The system already has deterministic UUIDs for exactly this purpose — the enrichment script should use `_work_id()` and `_author_id()` for exact matching.

### 500+ lines of hardcoded Python data

`seed_enrichments.py` has significance markings, author metadata, stream definitions, collection definitions, and stream-collection assignments all as Python list/dict constants. This should be structured data files (YAML or TOML) that the ingestion script reads, not executable code.

The data is tightly coupled to the execution logic. Adding a new stream or collection means editing Python code, not a data file.

---

## Medium: Configuration & Infrastructure

### Docker Compose port mismatch

`docker-compose.yml` maps PostgreSQL to host port 5433:
```yaml
ports:
  - "5433:5432"
```

But `config.py` defaults to port 5432:
```python
postgres_port: int = 5432
```

This works because `.env` presumably has the right port, but anyone cloning the repo without copying `.env.example` first gets a silent connection failure.

### No environment separation

A single `.env` file with no mechanism to distinguish dev, test, or production. Tests share the dev database by default. There's no `Settings` subclass for testing, no `TEST_` prefix convention, no separate docker-compose for tests.

### Module-level singleton in `config.py`

```python
settings = Settings()  # Module-level instantiation
```

This runs at import time, reads `.env`, and creates a global singleton. Any module that imports from `config.py` triggers settings loading as a side-effect. This makes testing harder (you can't override settings before import) and makes the import graph order-dependent.

Compare to finalysis, where `load_config()` is a function called explicitly, and the config is passed through the call chain.

---

## Medium: API Design

### Inconsistent router patterns

- `works` and `authors` use `APIRouter(prefix="/works")` — paths are relative
- `streams`, `collections`, and `series` use `APIRouter(tags=["streams"])` with absolute paths like `@router.get("/streams")`

This means:
- `works_router` endpoints are `/works`, `/works/{id}` (prefix-based)
- `streams_router` endpoints are `/streams`, `/streams/{id}` (hardcoded)
- Mixed patterns within the same codebase

### No API versioning

All endpoints live at the root: `/works`, `/authors`, `/streams`. When the quiz system arrives (Phase 2), backwards-incompatible changes to the stats endpoint or work response format will break the frontend with no migration path.

### Stream creation uses random UUIDs; everything else uses deterministic IDs

```python
# streams.py — random UUID
stream_id = str(uuid.uuid4())

# collections.py — deterministic from ids.py
coll_id = collection_id(req.name)
```

Streams created via the API get random UUIDs. Streams created by the enrichment script get deterministic UUIDs via `ids.stream_id()`. If the same stream is created via both paths, it gets two different nodes.

---

## Low: Code Quality

### Pydantic models in `models/neo4j.py` are unused

`WorkNode`, `AuthorNode`, `StreamNode`, `CollectionNode` are defined but never instantiated anywhere. The service layer works with raw dicts from Neo4j. These models are aspirational — they document the schema but don't enforce it.

### No structured logging

`logging.info("create_work: id=%s title=%r", wid, req.title)` — unstructured string formatting. No JSON logging, no request correlation IDs, no log levels configuration. When something goes wrong in production, logs are unsearchable.

### `ManagedOLClient` in `openlibrary.py` is unused

`build_ol_client()` returns a `ManagedOLClient` context manager, but `AppState.create()` creates the `httpx.AsyncClient` and `OpenLibraryClient` directly. The managed client is dead code.

### `_merge_author()` in `reading_list.py` is dead code

Lines 114-130 define `_merge_author()` which is never called — the actual implementation is `_upsert_author()` at line 133. The dead function has a `return False  # placeholder` that makes it non-functional.
