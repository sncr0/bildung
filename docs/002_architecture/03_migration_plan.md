# 03 — Migration Plan

How to get from the current state to the target architecture. Phases are ordered by dependency — each phase builds on the previous one. Within each phase, items are ordered by implementation sequence.

**Ground rule:** Every phase must leave the app fully functional. No "big bang" rewrites. Each change is deployable independently.

---

## Phase 0: Foundation (No Behavior Change)

These are cleanup items that reduce risk for everything that follows. No user-visible changes. No database schema changes. Pure refactoring.

### 0.1 — Extract shared frontend components

**Files touched:** `frontend/src/components/` (new), all pages

Create `components/` directory and extract:
- `WorkRow.tsx` — the work list item (currently duplicated in AuthorDetail, StreamDetail, CollectionDetail)
- `ProgressBar.tsx` — the progress bar (duplicated in AuthorDetail, StreamDetail, CollectionDetail)
- `StatusBadge.tsx` — status label + color mapping
- `constants.ts` — `STATUS_COLORS`, `STATUS_LABELS`, `TYPE_LABELS`, `DENSITY_LABELS`

Update all pages to import from `components/`. This is mechanical — no logic changes.

**Why first:** This makes subsequent frontend changes less risky because you're editing shared code in one place instead of 5.

### 0.2 — Extract stats service from router

**Files touched:** `services/stats.py` (new), `routers/stats.py`

Move the 6 Cypher queries from `routers/stats.py` into a new `services/stats.py` module. The router becomes a thin delegate. This aligns with the project's own convention.

### 0.3 — Fix stream ID generation inconsistency

**Files touched:** `services/streams.py`

`create_stream()` currently uses `uuid.uuid4()` (random). Change to `ids.stream_id(req.name)` (deterministic). This ensures API-created streams match enrichment-created streams with the same name.

Also fix `created_at` — currently uses `datetime.now(timezone.utc).isoformat()` as a string. Neo4j has native datetime; use it or be consistent with how other temporal data is stored.

### 0.4 — Remove dead code

**Files touched:** `services/openlibrary.py`, `ingestion/reading_list.py`

- Delete `ManagedOLClient` and `build_ol_client()` from `openlibrary.py` (unused; `AppState` creates the client directly)
- Delete `_merge_author()` from `reading_list.py` (dead code; actual implementation is `_upsert_author()`)

### 0.5 — Fix Docker Compose port alignment

**Files touched:** `docker-compose.yml` or `config.py`

Either change `docker-compose.yml` to map `5432:5432` (simplest — avoids port confusion) or change `config.py` default to `postgres_port: int = 5433`. The current mismatch is a latent bug.

### 0.6 — Make config loading explicit

**Files touched:** `config.py`, `app_state.py`, `ingestion/reading_list.py`, `ingestion/seed_enrichments.py`

Replace the module-level singleton:
```python
# Before:
settings = Settings()

# After:
def load_settings(env_file: str = ".env") -> Settings:
    return Settings(_env_file=env_file)
```

Update `AppState.create()` to call `load_settings()` if no config is passed. Update ingestion scripts to call `load_settings()` explicitly. This eliminates import-time side effects and enables test configuration.

---

## Phase 1: Repository Layer + Domain Models

This is the core structural change. It introduces the repository pattern and domain models, rewires the service layer, and prepares for the PostgreSQL migration in Phase 2.

### 1.1 — Define domain models

**Files created:** `models/domain.py`

Create pure Pydantic models that represent the domain, independent of any database:

```python
class Work(BaseModel):
    id: str
    title: str
    status: StatusLiteral
    language_read_in: str | None = None
    date_read: str | None = None
    density_rating: DensityLiteral | None = None
    source_type: SourceTypeLiteral = "fiction"
    personal_note: str | None = None
    edition_note: str | None = None
    significance: SignificanceLiteral | None = None
    authors: list[AuthorSummary] = []
    stream_ids: list[str] = []
    collections: list[CollectionMembership] = []

class Author(BaseModel):
    id: str
    name: str
    birth_year: int | None = None
    death_year: int | None = None
    nationality: str | None = None
    primary_language: str | None = None
```

These replace the current practice of passing raw `dict` objects through the system. `models/api.py` response schemas can wrap or re-export these.

### 1.2 — Create base repository

**Files created:** `repositories/__init__.py`, `repositories/base.py`

```python
class NeoRepository:
    """Base for repositories that talk to Neo4j."""
    def __init__(self, driver: AsyncDriver):
        self._driver = driver

    async def _run(self, query: str, **params) -> list[Record]:
        async with self._driver.session() as session:
            result = await session.run(query, params)
            return [r async for r in result]

    async def _run_single(self, query: str, **params) -> Record | None:
        async with self._driver.session() as session:
            result = await session.run(query, params)
            return await result.single()
```

This eliminates the `async with driver.session() as session:` boilerplate from every function.

### 1.3 — Create work repository

**Files created:** `repositories/works.py`

Move all Work-related Cypher queries from `services/works.py` into `WorkRepository`. The repository returns domain `Work` objects, not raw dicts. The `_record_to_work()` mapping function moves here and becomes a private method of the repository.

```python
class WorkRepository(NeoRepository):
    async def list(self, status=None, author=None, limit=50, offset=0) -> list[Work]:
        ...
    async def get(self, work_id: str) -> Work | None:
        ...
    async def create(self, work: Work) -> Work:
        ...
    async def update(self, work_id: str, updates: dict) -> Work | None:
        ...
```

### 1.4 — Create remaining repositories

**Files created:** `repositories/authors.py`, `repositories/collections.py`, `repositories/streams.py`, `repositories/series.py`, `repositories/events.py`

Same pattern as 1.3 for each entity. `EventRepository` wraps the PostgreSQL reading event operations currently in `services/works.py`.

### 1.5 — Rewire services to use repositories

**Files modified:** All service files

Services no longer receive `AsyncDriver` and `AsyncSession` directly. Instead, they receive repositories:

```python
# Before:
async def create_work(driver: AsyncDriver, pg_session: AsyncSession, req: CreateWorkRequest) -> WorkResponse:

# After:
class WorkService:
    def __init__(self, work_repo: WorkRepository, event_repo: EventRepository):
        self._works = work_repo
        self._events = event_repo

    async def create(self, req: CreateWorkRequest) -> Work:
```

### 1.6 — Update dependencies.py

**Files modified:** `dependencies.py`

Add repository factory functions:
```python
def get_work_repo(request: Request) -> WorkRepository:
    return WorkRepository(get_app_state(request).neo4j_driver)

def get_work_service(request: Request) -> WorkService:
    return WorkService(
        work_repo=get_work_repo(request),
        event_repo=get_event_repo(request),
    )
```

Routers depend on services, not drivers.

### 1.7 — Update routers

**Files modified:** All router files

Routers depend on service classes via `Depends`, not on raw drivers/sessions:

```python
@router.get("", response_model=list[WorkResponse])
async def list_works(
    status: StatusLiteral | None = Query(None),
    svc: WorkService = Depends(get_work_service),
) -> list[WorkResponse]:
    return await svc.list(status=status)
```

---

## Phase 2: PostgreSQL as System of Record

This is the database migration that moves entity storage from Neo4j to PostgreSQL, making Neo4j the relationship-only store.

### 2.1 — Create PostgreSQL entity tables

**Files created:** New Alembic migration

```sql
CREATE TABLE works (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'to_read',
    language_read_in VARCHAR,
    date_read VARCHAR,              -- kept as string for flexible formats
    density_rating VARCHAR,
    source_type VARCHAR NOT NULL DEFAULT 'fiction',
    personal_note TEXT,
    edition_note TEXT,
    significance VARCHAR,
    page_count INT,
    year_published INT,
    original_language VARCHAR,
    openlibrary_id VARCHAR,
    cover_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE authors (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    birth_year INT,
    death_year INT,
    nationality VARCHAR,
    primary_language VARCHAR,
    openlibrary_id VARCHAR,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE work_authors (
    work_id UUID REFERENCES works(id),
    author_id UUID REFERENCES authors(id),
    PRIMARY KEY (work_id, author_id)
);

CREATE TABLE collections (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    type VARCHAR NOT NULL DEFAULT 'anthology',
    author_id UUID REFERENCES authors(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE streams (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    color VARCHAR,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE work_collections (
    work_id UUID REFERENCES works(id),
    collection_id UUID REFERENCES collections(id),
    "order" INT,
    PRIMARY KEY (work_id, collection_id)
);

CREATE TABLE work_streams (
    work_id UUID REFERENCES works(id),
    stream_id UUID REFERENCES streams(id),
    position INT,
    PRIMARY KEY (work_id, stream_id)
);

CREATE TABLE collection_streams (
    collection_id UUID REFERENCES collections(id),
    stream_id UUID REFERENCES streams(id),
    "order" INT,
    PRIMARY KEY (collection_id, stream_id)
);

CREATE INDEX idx_works_status ON works(status);
CREATE INDEX idx_works_title ON works(title);
CREATE INDEX idx_authors_name ON authors(name);
CREATE INDEX idx_collections_type ON collections(type);
CREATE INDEX idx_collections_author ON collections(author_id);
```

### 2.2 — Add SQLAlchemy models for new tables

**Files modified:** `models/postgres.py`

Add SQLAlchemy ORM models for the new tables. These complement the existing event/XP tables.

### 2.3 — Write data migration script

**Files created:** `ingestion/migrate_neo4j_to_pg.py`

One-shot script that reads all nodes and relationships from Neo4j and writes them to PostgreSQL. Validates counts match. This is the bridge — run once, verify, then switch the read path.

### 2.4 — Update repositories to use PostgreSQL for reads

**Files modified:** All repository files

Change `WorkRepository.list()` and `WorkRepository.get()` to query PostgreSQL instead of Neo4j. Graph repositories still use Neo4j for relationship queries.

### 2.5 — Update repositories to write both stores

**Files modified:** Repository write methods

Write path writes to PostgreSQL first (system of record), then syncs the graph edges to Neo4j. If the Neo4j write fails, log a warning — the PG data is authoritative.

### 2.6 — Update ingestion pipeline

**Files modified:** `ingestion/reading_list.py`, `ingestion/seed_enrichments.py` (renamed to `enrichments.py`)

Ingestion writes to PostgreSQL tables and syncs graph edges to Neo4j.

---

## Phase 3: Test Infrastructure

### 3.1 — Add testcontainers dependencies

**Files modified:** `pyproject.toml`

```toml
[dependency-groups]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=1.3.0",
    "testcontainers[postgres,neo4j]>=4.0",
    "httpx>=0.27",
]
```

### 3.2 — Create conftest.py with database fixtures

**Files created:** `tests/conftest.py`

Session-scoped containers, per-test database wiping, AppState injection:

```python
@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

@pytest.fixture(scope="session")
def neo4j_container():
    with Neo4jContainer("neo4j:5") as neo:
        yield neo

@pytest.fixture
async def pg_session(pg_engine):
    async with async_sessionmaker(pg_engine)() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def test_state(pg_session, neo4j_driver):
    return AppState(settings=test_settings, pg_engine=..., neo4j_driver=..., ...)

@pytest.fixture
async def client(test_state):
    app = create_app(state=test_state)
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c
```

### 3.3 — Write service tests

**Files created:** `tests/test_work_service.py`, `tests/test_author_service.py`, etc.

Test each service function against real databases. Test cross-database consistency. Test error paths.

### 3.4 — Write API integration tests

**Files created:** `tests/test_api_works.py`, etc.

End-to-end tests: create a work via POST, verify it appears in GET, update via PATCH, verify the event was recorded in PostgreSQL.

### 3.5 — Write XP calculation tests

**Files created:** `tests/test_xp.py` (replace the stub)

Test the XP formula with known inputs and expected outputs. These are pure unit tests — no database needed.

---

## Phase 4: Frontend Hardening

### 4.1 — Add TanStack Query

**Files modified:** `frontend/package.json`, `frontend/src/main.tsx`

Install `@tanstack/react-query`. Add `QueryClientProvider` to the app root.

### 4.2 — Create custom hooks

**Files created:** `frontend/src/hooks/useWorks.ts`, etc.

Wrap API calls in TanStack Query hooks:
```typescript
export function useWorks(params?: { status?: string; author?: string }) {
    return useQuery({
        queryKey: ['works', params],
        queryFn: () => getWorks(params),
    });
}
```

### 4.3 — Update pages to use hooks

**Files modified:** All page components

Replace `useEffect` + `useState` patterns with custom hooks. Remove manual loading/error state management.

### 4.4 — Add error boundaries

**Files created:** `frontend/src/components/ErrorBoundary.tsx`

Route-level error boundaries that show a fallback UI and a retry button.

### 4.5 — Add pagination

**Files modified:** WorkList, AuthorList

The API already supports `limit` + `offset`. Add infinite scroll or page controls to the frontend.

---

## Phase 5: Data Quality & Enrichment

### 5.1 — Move enrichment data to YAML

**Files created:** `ingestion/data/*.yaml`
**Files modified:** `ingestion/enrichments.py` (rename from `seed_enrichments.py`)

Move the 500+ lines of Python constants into structured YAML files. The enrichment script reads YAML and executes.

### 5.2 — Replace fuzzy matching with deterministic ID lookups

**Files modified:** `ingestion/enrichments.py`

Use `ids.work_id(title, author)` for exact matching instead of `CONTAINS` substring queries.

### 5.3 — Add OpenLibrary enrichment to ingestion

Wire up the existing `OpenLibraryClient` to the ingestion pipeline. After creating a work from `reading_list.txt`, look it up on OpenLibrary and backfill page count, year published, cover URL, ISBN.

---

## Dependency Graph

```
Phase 0 (Foundation)
    │
    ├── 0.1 Frontend components ──────────────────┐
    ├── 0.2 Stats service extraction              │
    ├── 0.3 Stream ID fix                         │
    ├── 0.4 Dead code removal                     │
    ├── 0.5 Port alignment                        │
    └── 0.6 Config loading fix                    │
         │                                        │
Phase 1 (Repository Layer) ←── depends on 0.6    │
    │                                             │
    ├── 1.1 Domain models                         │
    ├── 1.2 Base repository                       │
    ├── 1.3-1.4 Entity repositories               │
    ├── 1.5 Rewire services                       │
    ├── 1.6 Update dependencies                   │
    └── 1.7 Update routers                        │
         │                                        │
Phase 2 (PG Migration) ←── depends on Phase 1    │
    │                                             │
    ├── 2.1 PG entity tables                      │
    ├── 2.2 SQLAlchemy models                     │
    ├── 2.3 Data migration script                 │
    ├── 2.4-2.5 Repository updates                │
    └── 2.6 Ingestion updates                     │
         │                                        │
Phase 3 (Tests) ←── depends on Phase 1           │
    │                                             │
    ├── 3.1 Testcontainers setup                  │
    ├── 3.2 conftest.py                           │
    ├── 3.3-3.5 Test suites                       │
    │                                             │
Phase 4 (Frontend) ←── depends on 0.1 ───────────┘
    │
    ├── 4.1 TanStack Query
    ├── 4.2 Custom hooks
    ├── 4.3 Page updates
    ├── 4.4 Error boundaries
    └── 4.5 Pagination
         │
Phase 5 (Data Quality) ←── depends on Phase 2
    │
    ├── 5.1 YAML data files
    ├── 5.2 Deterministic matching
    └── 5.3 OpenLibrary enrichment
```

**Phases 0, 3, and 4 are parallelizable.** Phase 0 has no dependencies. Phase 3 can start as soon as Phase 1 is done (in parallel with Phase 2). Phase 4 can start as soon as Phase 0.1 is done (in parallel with everything else). Phase 5 requires Phase 2 to be complete.

---

## What Not To Do

### Don't migrate to PostgreSQL-only

The graph database is justified — just not yet. Phases 2-4 of BILDUNG.md describe features (cross-stream connections, reading path visualization, LLM-powered recommendations) that are genuinely graph problems. The architecture should support both stores cleanly, not eliminate one.

### Don't add GraphQL

The API surface is manageable with REST. The frontend makes ~3 API calls per page. GraphQL adds complexity (schema definition, resolver layer, client-side cache normalization) that doesn't pay off at this scale.

### Don't add a message queue

Event-driven doesn't mean event bus. At single-user scale, "write event, then run side-effects synchronously" is fine. A message queue (Redis Streams, RabbitMQ) adds operational complexity with no benefit. If the side-effects become slow (LLM calls for quiz generation), run them in a background task, not a separate service.

### Don't over-abstract the repository layer

The repository pattern should make database access testable and swappable, not create an ORM on top of an ORM. Keep queries as plain Cypher/SQL strings in the repository methods. Don't build a query builder.
