# 02 — Target Architecture

This document describes the architecture Bildung should evolve toward. The design is informed by finalysis patterns, adapted for the dual-database (Neo4j + PostgreSQL) setup, and designed to support Phase 2 (LLM quiz engine) and Phase 3 (graph visualization) without rewrites.

---

## Design Philosophy

### 1. PostgreSQL is the system of record; Neo4j is the relationship engine

This is the most important architectural decision. Today, Work and Author entities live exclusively in Neo4j with 12+ scalar properties each. This is wrong for two reasons:

**Neo4j's strength is traversal, not storage.** Graph databases optimize for following edges — "find all works reachable from this author through shared streams within 3 hops." They are mediocre at property filtering, aggregation, and range queries. Storing `date_read`, `density_rating`, `page_count` as node properties means every list/filter query does a full label scan with property comparisons.

**PostgreSQL's strength is exactly what we need for entities.** Typed columns, B-tree indexes, CHECK constraints, partial indexes, window functions for analytics, JSONB for flexible metadata, proper NULL semantics, and ACID transactions. The XP system, quiz engine, and SRS scheduler all live in PostgreSQL already — they need to join against work/author data that currently lives in a different database.

**Target split:**

| Store | Owns | Examples |
|-------|------|----------|
| **PostgreSQL** | Entity data (scalar properties, metadata) | `works` table, `authors` table, `collections` table, `streams` table |
| **PostgreSQL** | Time-series and event data | `reading_events`, `xp_ledger`, `quiz_*`, `srs_schedule` |
| **PostgreSQL** | Aggregated views for the API | Materialized views or query-time aggregations |
| **Neo4j** | Relationships and graph structure | `(:Author)-[:WROTE]->(:Work)`, `(:Work)-[:IN_COLLECTION]->(:Collection)`, `(:Work)-[:READ_BECAUSE_OF]->(:Work)`, `(:Work)-[:SAME_THREAD_AS]->(:Work)` |
| **Neo4j** | Graph traversal queries | "What connects Stream A to Stream B?", "What's the shortest reading path from Plato to Nietzsche?", subgraph extraction for D3 visualization |

**The bridge:** Work and Author rows in PostgreSQL have UUIDs. Neo4j nodes have the same UUIDs. The graph stores only `{id}` on nodes — all properties are looked up from PostgreSQL when needed. For read-heavy paths (list endpoints), PostgreSQL serves everything directly. For graph-heavy paths (visualization, recommendations, cross-stream queries), Neo4j provides the topology and PostgreSQL provides the node details.

**Why not just PostgreSQL?** Because Phase 2-4 features are genuinely graph problems:
- `READ_BECAUSE_OF` chains form a directed graph of intellectual influence
- `SAME_THREAD_AS` edges create clusters that aren't hierarchical
- "What should I read next?" requires traversing the graph of read/unread works across streams
- The D3 visualization needs a subgraph extraction that's natural in Cypher, painful in SQL
- Cross-stream connection detection is a graph reachability problem

The graph earns its keep — but only for graph operations, not as a property store.

### 2. Events drive state; state is derived

Today, `create_work()` writes the work directly and then maybe writes a reading event as a side-effect. This should be inverted: **the event is the fact; the current state is a projection.**

When a user marks a work as "read," the system should:
1. Write a `reading_event` (the fact: "Sam finished this work on 2024-03-15")
2. Derive the work's current status from its event history
3. Trigger XP calculation from the event
4. Update any caches/views

This makes the system auditable ("why does this work show as read?" → look at the events), replayable (re-derive all state from events), and extensible (new features subscribe to events without modifying existing write paths).

This is not full event sourcing — it's event-driven state updates. The work table still has a `status` column for fast reads. But the event log is the source of truth.

### 3. Thin routers, domain services, repository layer

Three layers with strict dependency direction:

```
Router → Service → Repository
  │         │          │
  │         │          └── Owns: database sessions, queries, record mapping
  │         └── Owns: business logic, validation, cross-repo orchestration
  └── Owns: HTTP concerns (status codes, query params, error responses)
```

**Routers** do not import database drivers, run queries, or contain business logic. They validate input (via Pydantic), call a service method, and return the result. A router is replaceable — you could swap FastAPI for a CLI and only rewrite the router layer.

**Services** contain business logic and orchestrate operations across repositories. They receive repositories via constructor injection (not `Depends`). They don't know about HTTP, Neo4j sessions, or SQLAlchemy engines. They work with domain models.

**Repositories** own the database interaction. A `WorkRepository` knows how to CRUD works in PostgreSQL and how to sync graph relationships in Neo4j. It returns domain models, not raw dicts or ORM objects. Query strings live here and nowhere else.

### 4. Domain models are the contract

Today there are three model layers that don't quite align:
- `models/neo4j.py` — Pydantic models for Neo4j nodes (unused)
- `models/api.py` — Pydantic models for API request/response
- `models/postgres.py` — SQLAlchemy ORM models

The target has a clearer separation:

```
models/
├── domain.py        # Core domain: Work, Author, Collection, Stream, Series
│                    #   Pure dataclasses. No DB coupling. Validation rules live here.
├── api.py           # API schemas: CreateWorkRequest, WorkResponse, etc.
│                    #   May re-export domain models or wrap them with API-specific fields.
├── events.py        # Event types: ReadingEvent, XpAward, QuizAttempt
│                    #   Immutable. Timestamped. The "facts" of the system.
└── postgres.py      # SQLAlchemy table definitions (ORM mapped to domain models)
```

Domain models are used everywhere — services work with them, repositories return them, API schemas convert to/from them. This eliminates the current pattern of passing raw dicts through the system.

### 5. Testability is a first-class concern

The finalysis project has a pattern worth copying directly:

- **Session-scoped testcontainers:** One PostgreSQL container for the entire test suite, one Neo4j container.
- **Per-test database wiping:** Each test gets a clean database. For PostgreSQL, truncate tables. For Neo4j, `MATCH (n) DETACH DELETE n`.
- **AppState injection:** `create_app(state=test_state)` skips the lifespan and injects test fixtures directly. The app is already set up for this (`main.py` line 57-58).
- **No mocks for databases:** Real queries against real databases. Mocks hide bugs; real databases expose them.
- **Fixtures build upward:** `pg_container` → `pg_engine` → `pg_session` → `work_repo` → `work_service`. Each fixture layer is independently testable.

---

## Target Module Structure

```
src/bildung/
├── __init__.py
├── main.py                    # FastAPI app creation + lifespan
├── app_state.py               # AppState dataclass (holds all singletons)
├── config.py                  # Settings (pydantic-settings, loaded explicitly)
├── dependencies.py            # FastAPI Depends() functions
├── ids.py                     # Deterministic UUID generation
│
├── models/
│   ├── domain.py              # Core domain models (Work, Author, etc.)
│   ├── api.py                 # Request/response schemas
│   ├── events.py              # Event types
│   └── postgres.py            # SQLAlchemy table definitions
│
├── repositories/
│   ├── base.py                # Base repository with session helpers
│   ├── works.py               # WorkRepository (PG + Neo4j)
│   ├── authors.py             # AuthorRepository
│   ├── collections.py         # CollectionRepository
│   ├── streams.py             # StreamRepository
│   ├── series.py              # SeriesRepository
│   ├── events.py              # ReadingEventRepository (PG only)
│   └── graph.py               # GraphRepository (Neo4j traversal queries)
│
├── services/
│   ├── works.py               # Work business logic
│   ├── authors.py             # Author business logic
│   ├── collections.py         # Collection business logic
│   ├── streams.py             # Stream business logic
│   ├── series.py              # Series business logic
│   ├── stats.py               # Stats aggregation (moved from router)
│   ├── xp.py                  # XP calculation engine
│   ├── openlibrary.py         # External API client (unchanged)
│   └── graph.py               # Graph traversal service (Phase 2+)
│
├── routers/
│   ├── works.py               # /works endpoints
│   ├── authors.py             # /authors endpoints
│   ├── collections.py         # /collections endpoints
│   ├── streams.py             # /streams endpoints
│   ├── series.py              # /series endpoints
│   └── stats.py               # /stats endpoints (thin — delegates to service)
│
└── ingestion/
    ├── reading_list.py        # reading_list.txt parser + loader
    ├── enrichments.py         # Enrichment data loader (reads YAML)
    └── data/                  # YAML data files for enrichments
        ├── significance.yaml
        ├── authors.yaml
        ├── streams.yaml
        └── collections.yaml
```

Key changes from current structure:
1. New `repositories/` layer between services and databases
2. `models/domain.py` as the central type system
3. Enrichment data moved from Python constants to YAML
4. `services/stats.py` extracted from `routers/stats.py`
5. `repositories/graph.py` for Neo4j-only traversal queries (Phase 2+)

---

## Data Flow: Write Path

```
                   ┌──────────────┐
                   │   Router     │  Validates input (Pydantic)
                   └──────┬───────┘
                          │
                   ┌──────▼───────┐
                   │   Service    │  Business logic, cross-repo orchestration
                   └──────┬───────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
       ┌──────▼───┐  ┌───▼────┐  ┌───▼──────┐
       │  PG Repo  │  │Neo4j   │  │ Event    │
       │ (entity)  │  │Repo    │  │ Repo     │
       └──────┬────┘  │(edges) │  │ (PG)     │
              │       └───┬────┘  └───┬──────┘
              │           │           │
         PostgreSQL    Neo4j     PostgreSQL
       (works table)  (graph)   (events table)
```

Example — `create_work()`:
1. Router validates `CreateWorkRequest`
2. Service generates deterministic ID, creates domain `Work` object
3. Service calls `work_repo.create(work)` → INSERT into `works` table
4. Service calls `graph_repo.ensure_author_wrote_work(author_id, work_id)` → MERGE edges
5. If status == "read": service calls `event_repo.record(ReadingFinished(...))` → INSERT event
6. Service returns the created `Work` domain object
7. Router converts to `WorkResponse` and returns 201

**Transaction boundary:** Steps 3 and 5 share a PostgreSQL transaction (same session, committed together). Step 4 is a separate Neo4j transaction. If step 4 fails, the PG transaction rolls back. If PG commits but Neo4j fails, we log a warning and the graph is eventually consistent (a background reconciliation job can fix it).

This is a pragmatic choice: PostgreSQL is the system of record, Neo4j is eventually consistent. For a single-user personal app, this is perfectly acceptable. For multi-user, you'd want an outbox pattern.

---

## Data Flow: Read Path

```
        ┌──────────────┐
        │   Router     │
        └──────┬───────┘
               │
        ┌──────▼───────┐
        │   Service    │
        └──────┬───────┘
               │
    ┌──────────┼──────────┐
    │                     │
┌───▼────────┐    ┌───────▼──────┐
│  PG Repo   │    │  Graph Repo  │
│ (entities) │    │ (traversals) │
└───┬────────┘    └───────┬──────┘
    │                     │
PostgreSQL             Neo4j
```

**For list/detail endpoints** (95% of reads): PostgreSQL only. JOIN works + authors + collections in SQL. No Neo4j round-trip needed. Fast, cacheable, paginated natively.

**For graph endpoints** (Phase 2+): Neo4j returns topology (node IDs + edge types), then PostgreSQL hydrates the node details in a single batch query. Two round-trips, but the graph query is small (just IDs) and the PG query is an `IN (...)` lookup on indexed UUIDs.

**For stats:** PostgreSQL aggregation queries or materialized views. No Neo4j needed — all the data lives in PG.

---

## Frontend Target Architecture

### Data layer: TanStack Query (React Query)

Replace raw `useEffect` + `useState` with a proper data fetching library:

```typescript
// Before (current):
useEffect(() => {
    getWorks({ status }).then(setWorks).finally(() => setLoading(false));
}, [status]);

// After (target):
const { data: works, isLoading, error } = useQuery({
    queryKey: ['works', { status }],
    queryFn: () => getWorks({ status }),
});
```

Benefits:
- Automatic caching and deduplication (two components requesting the same data → one fetch)
- Background refetching (stale-while-revalidate)
- Loading/error states built in
- Optimistic updates for mutations
- Cache invalidation when data changes

### Shared components

Extract duplicated UI into `components/`:

```
frontend/src/
├── components/
│   ├── WorkRow.tsx           # Extracted from 4 pages
│   ├── ProgressBar.tsx       # Extracted from 3 pages
│   ├── StatusBadge.tsx       # Status label + color mapping
│   ├── CollectionBlock.tsx   # Collection with progress + work list
│   ├── ErrorFallback.tsx     # Error boundary fallback
│   └── constants.ts          # STATUS_COLORS, TYPE_LABELS, etc.
├── hooks/
│   ├── useWorks.ts           # TanStack Query wrapper
│   ├── useAuthors.ts
│   ├── useStreams.ts
│   └── useCollections.ts
├── pages/                    # (existing, but thinner)
└── services/
    └── api.ts                # (existing, unchanged)
```

### Error handling

- React Error Boundaries at the route level
- TanStack Query's `error` state for per-component errors
- Toast notifications for mutation failures
- Retry buttons where appropriate

---

## Configuration Target

### Explicit construction, no module-level singletons

```python
# Current (anti-pattern):
settings = Settings()  # Runs at import time

# Target:
def load_settings(env_file: str = ".env") -> Settings:
    return Settings(_env_file=env_file)
```

Benefits:
- Tests can call `load_settings(".env.test")` or construct `Settings()` with explicit values
- No import-time side effects
- Multiple configurations can coexist (dev settings + test settings in the same process)

### Docker Compose port alignment

Fix the mismatch: either map to 5432:5432 (simplest) or update the config default to match.

---

## What This Architecture Enables

| Future Feature | How the architecture supports it |
|---|---|
| **XP Engine** (Phase 1 completion) | Events in PG trigger XP calculation. XP service reads from `works` table (PG) for page count, density, language. No Neo4j needed for XP math. |
| **Quiz System** (Phase 2) | Quiz generator reads from PG (works, reading events, past attempts). Graph repo provides "related works across streams" for cross-stream questions. Quiz storage is PG-only. |
| **Graph Visualization** (Phase 3) | Graph repo returns the full subgraph as `{nodes: [{id}], edges: [{source, target, type}]}`. Frontend hydrates node details from a batch PG endpoint. D3 renders the topology. |
| **Recommendations** (Phase 4) | Graph repo does multi-hop traversal to find reading paths. LLM receives structured context from PG (work details, quiz performance, stream levels). |
| **Full-text search** | PostgreSQL `tsvector` index on works.title + authors.name. No Neo4j involvement. |
| **Analytics dashboard** | SQL window functions, GROUP BY, materialized views. All data in PG. |
