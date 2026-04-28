# Task 1C — Service + Dependency + Router Rewiring

## Kickoff

### Read Before Starting
1. **This spec** (you're reading it)
2. **Next task spec:** `TASK_2A.md` — PostgreSQL entity schema. That task creates the PG tables that repositories will eventually read from. The service interfaces you define here must NOT be tied to Neo4j — they work with repositories that could be backed by any database. Keep the service methods database-agnostic.
3. **Architecture reference:** `02_target_architecture.md` → "Thin routers, domain services, repository layer" section, plus the "Data Flow: Write Path" diagram showing Router → Service → Repository.
4. **Repository layer:** Review all files in `repositories/` (created in Task 1B) to understand the method signatures you'll be calling.

### Pre-conditions
- [ ] Task 1B is complete (repositories exist)
- [ ] `python -c "from bildung.repositories.works import WorkRepository"` works
- [ ] Backend starts without import errors
- [ ] All endpoints respond correctly

### Lessons from Previous Task
_To be populated by Task 1B implementer._

---

## Spec

### Goal

Rewire the entire backend stack: services become classes that receive repositories, `dependencies.py` creates the object graph, and routers depend on services (not raw drivers). This is the structural pivot — after this task, the layering is clean and the system is ready for the PostgreSQL migration.

### What This Enables

Task 2A (PG entity schema) and Task 3A (test infrastructure) both depend on this. The test infrastructure needs injectable services (constructor injection, not module-level functions). The PG migration needs repositories that can be swapped from Neo4j to PostgreSQL without touching services.

### Files to Modify

```
src/bildung/services/works.py
src/bildung/services/authors.py
src/bildung/services/streams.py
src/bildung/services/collections.py
src/bildung/services/series.py
src/bildung/services/stats.py
src/bildung/dependencies.py
src/bildung/routers/works.py
src/bildung/routers/authors.py
src/bildung/routers/streams.py
src/bildung/routers/collections.py
src/bildung/routers/series.py
src/bildung/routers/stats.py
```

### Files NOT to Modify

```
src/bildung/models/domain.py     — DO NOT CHANGE.
src/bildung/models/api.py        — DO NOT CHANGE.
src/bildung/repositories/*.py    — DO NOT CHANGE (unless fixing a bug found during integration).
src/bildung/main.py              — DO NOT CHANGE.
src/bildung/app_state.py         — DO NOT CHANGE.
src/bildung/ingestion/*.py       — DO NOT CHANGE.
```

### Exact Changes

The rewiring has three parts, done in order:

#### Part 1: Convert services to classes

Each service module currently has standalone async functions that receive `AsyncDriver` (and sometimes `AsyncSession`). Convert each to a class that receives repositories via `__init__`.

**Pattern for all services:**

```python
class WorkService:
    def __init__(self, work_repo: WorkRepository, pg_session: AsyncSession) -> None:
        self._works = work_repo
        self._pg_session = pg_session

    async def list(self, ...) -> list[WorkResponse]:
        works = await self._works.list(...)
        return [self._to_response(w) for w in works]

    async def get(self, work_id: str) -> WorkResponse | None:
        work = await self._works.get(work_id)
        if not work:
            return None
        return self._to_response(work)
```

**Critical:** Services still return API response models (`WorkResponse`, `AuthorResponse`, etc.), not domain models. Routers expect response models. The conversion from domain → API happens in the service layer.

##### `services/works.py`

```python
"""Work service — business logic for works."""
from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bildung.ids import author_id as _author_id, work_id as _work_id
from bildung.models.api import (
    AuthorSummary as ApiAuthorSummary,
    CollectionSummary,
    CreateWorkRequest,
    UpdateWorkRequest,
    WorkResponse,
)
from bildung.models.domain import Work
from bildung.models.postgres import ReadingEvent
from bildung.repositories.works import WorkRepository

logger = logging.getLogger(__name__)


class WorkService:
    def __init__(self, work_repo: WorkRepository, pg_session: AsyncSession) -> None:
        self._works = work_repo
        self._pg_session = pg_session

    async def list(
        self,
        status: str | None = None,
        author: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WorkResponse]:
        works = await self._works.list(status=status, author=author, limit=limit, offset=offset)
        return [self._work_to_response(w) for w in works]

    async def get(self, work_id: str) -> WorkResponse | None:
        work = await self._works.get(work_id)
        if not work:
            return None
        return self._work_to_response(work)

    async def create(self, req: CreateWorkRequest) -> WorkResponse:
        wid = _work_id(req.title, req.author)
        aid = _author_id(req.author)

        work = await self._works.create(
            work_id=wid,
            title=req.title,
            author_id=aid,
            author_name=req.author,
            status=req.status,
            language_read_in=req.language_read_in,
            date_read=req.date_read,
            density_rating=req.density_rating,
            source_type=req.source_type,
            personal_note=req.personal_note,
            significance=req.significance,
        )

        logger.info("create_work: id=%s title=%r status=%s", wid, req.title, req.status)

        if req.status == "read":
            await self._record_reading_event(wid, "finished", req.date_read)

        return self._work_to_response(work)

    async def update(self, work_id: str, req: UpdateWorkRequest) -> WorkResponse | None:
        current = await self._works.get(work_id)
        if not current:
            return None

        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if not updates:
            return self._work_to_response(current)

        work = await self._works.update(work_id, updates)
        logger.info("update_work: id=%s fields=%s", work_id, list(updates.keys()))

        if req.status == "read" and current.status != "read":
            event_date = req.date_read or current.date_read or str(date.today())
            await self._record_reading_event(work_id, "finished", event_date)

        return self._work_to_response(work) if work else None

    # --- private helpers ---

    async def _record_reading_event(
        self, work_id: str, event_type: str, event_date: str | None,
    ) -> None:
        parsed_date = _parse_date(event_date)
        stmt = insert(ReadingEvent).values(
            id=uuid.uuid4(),
            work_id=uuid.UUID(work_id),
            event_type=event_type,
            event_date=parsed_date,
        )
        await self._pg_session.execute(stmt)
        await self._pg_session.commit()

    @staticmethod
    def _work_to_response(work: Work) -> WorkResponse:
        """Convert domain Work to API WorkResponse."""
        return WorkResponse(
            id=work.id,
            title=work.title,
            status=work.status,
            language_read_in=work.language_read_in,
            date_read=work.date_read,
            density_rating=work.density_rating,
            source_type=work.source_type,
            personal_note=work.personal_note,
            edition_note=work.edition_note,
            significance=work.significance,
            authors=[
                ApiAuthorSummary(id=a.id, name=a.name) for a in work.authors
            ],
            stream_ids=[],  # populated by get_work detail query only
            collections=[
                CollectionSummary(
                    id=c.collection_id,
                    name=c.collection_name,
                    type=c.collection_type,
                    order=c.order,
                )
                for c in work.collections
            ],
        )


def _parse_date(raw: str | None) -> date:
    """Best-effort: '2024', '2024-03', '2024-03-15' -> date. Falls back to today."""
    if not raw:
        return date.today()
    try:
        if len(raw) == 4:
            return date(int(raw), 12, 31)
        if len(raw) == 7:
            y, m = raw.split("-")
            return date(int(y), int(m), 1)
        return date.fromisoformat(raw)
    except (ValueError, AttributeError):
        return date.today()
```

**The same class-based pattern applies to all other services.** Each service:
1. Receives its repository(ies) in `__init__`
2. Calls repository methods
3. Converts domain models to API response models
4. Returns API response models

For AuthorService, StreamService, CollectionService, and SeriesService — follow the exact same pattern. The Cypher queries are gone (they moved to repositories in Task 1B). The service now calls `self._repo.method()` and maps domain → API.

**Important:** The `_record_to_work()` helper that `authors.py`, `streams.py`, `collections.py`, and `series.py` import from `works.py` — this cross-module dependency disappears. Each service uses `WorkService._work_to_response()` or `WorkRepository._to_work()` depending on whether it's building responses. For services that need to convert works (like `AuthorService.get()` which returns works within collections), use `WorkRepository._to_work()` to get domain models and then convert them inline. Do NOT create circular service dependencies.

##### `services/stats.py`

Stats service is the exception — it keeps receiving `AsyncDriver` directly because its queries don't map to any single repository. It uses `async with driver.session()` directly. This is acceptable because stats queries will be rewritten for PostgreSQL in Task 2C.

```python
class StatsService:
    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def get_stats(self) -> Stats:
        async with self._driver.session() as s:
            # ... same 6 queries as current ...
```

#### Part 2: Update `dependencies.py`

Add repository and service factory functions:

```python
from bildung.repositories.works import WorkRepository
from bildung.repositories.authors import AuthorRepository
from bildung.repositories.collections import CollectionRepository
from bildung.repositories.streams import StreamRepository
from bildung.repositories.series import SeriesRepository
from bildung.services.works import WorkService
from bildung.services.authors import AuthorService
# ... etc.


# --- Repositories ---

def get_work_repo(request: Request) -> WorkRepository:
    return WorkRepository(get_app_state(request).neo4j_driver)

def get_author_repo(request: Request) -> AuthorRepository:
    return AuthorRepository(get_app_state(request).neo4j_driver)

# ... same for collections, streams, series


# --- Services ---

async def get_work_service(
    request: Request,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> WorkService:
    return WorkService(
        work_repo=get_work_repo(request),
        pg_session=pg_session,
    )

async def get_author_service(request: Request) -> AuthorService:
    return AuthorService(author_repo=get_author_repo(request))

# ... same for all services
```

**Key:** Only `WorkService` needs `pg_session` (for reading events). The others only need their repository.

#### Part 3: Update routers

Routers depend on services via `Depends`, not on raw drivers:

```python
# Before (current):
@router.get("", response_model=list[WorkResponse])
async def list_works(
    status: StatusLiteral | None = Query(None),
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> list[WorkResponse]:
    return await svc.list_works(driver, status=status)

# After:
@router.get("", response_model=list[WorkResponse])
async def list_works(
    status: StatusLiteral | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    svc: WorkService = Depends(get_work_service),
) -> list[WorkResponse]:
    return await svc.list(status=status, limit=limit, offset=offset)
```

**Every router follows this pattern.** No router imports `AsyncDriver`, `AsyncSession`, `get_neo4j_driver`, or `get_pg_session`. Routers import service classes and `get_*_service` dependency functions.

### Key Design Decisions (and why)

**1. Services return API models, not domain models.**
Routers currently expect `WorkResponse`, `AuthorResponse`, etc. Changing routers to accept domain models and convert them would be a bigger change. The domain → API conversion happens in the service layer, which is the right place for it.

**2. `_work_to_response()` is a static method on `WorkService`, not a standalone function.**
This prevents other services from importing it and creating cross-module dependencies. If `AuthorService` needs to convert works, it should use the `WorkRepository._to_work()` for domain models and do its own conversion to `WorkResponse`.

**3. Stats service keeps `AsyncDriver` directly.**
Its queries don't fit any repository (they're cross-entity aggregations). Wrapping them in a repository would create a `StatsRepository` that violates the "one repository per entity" convention. Task 2C will rewrite them as PostgreSQL queries.

**4. No `EventRepository` class — just inline SQLAlchemy.**
The reading event write is one `INSERT` statement used in one place (`WorkService`). Creating a full repository class for it adds abstraction without benefit. If it's needed later (Task 2C), it can be extracted then.

### DO NOT

1. **Do not change the API response shapes.** `WorkResponse`, `AuthorResponse`, etc. must return the exact same JSON as before. If a field was `null` before, it stays `null`. If `stream_ids` was `[]` for list but populated for detail, keep that behavior.

2. **Do not change URL paths or HTTP methods.** The frontend depends on these.

3. **Do not add new endpoints.** No `/works/search`, no `/health/detailed`, no batch endpoints.

4. **Do not change `models/api.py`.** The request/response schemas stay exactly as they are.

5. **Do not modify repository files.** If you find a bug in a repository method during integration, note it in the handoff section. Only fix it if the bug prevents the endpoint from working.

6. **Do not add middleware, exception handlers, or request hooks.** The error handling pattern (services return `None`, routers raise `HTTPException`) stays as-is.

7. **Do not rename the service module files.** `services/works.py` stays `services/works.py`. The file contains a class now instead of functions, but the filename doesn't change.

8. **Do not create a base service class.** No `BaseService`, no `CrudService[T]`. Five concrete service classes are better.

9. **Do not change `main.py` or `app_state.py`.** The lifespan and AppState creation stay the same. The object graph is assembled in `dependencies.py`, not in startup.

### Acceptance Criteria

- [ ] Every service module contains a class instead of standalone functions
- [ ] Every service class receives repositories in `__init__`, not `AsyncDriver`
- [ ] `dependencies.py` has factory functions for all repositories and services
- [ ] Every router depends on a service class via `Depends(get_*_service)`
- [ ] No router imports `AsyncDriver`, `AsyncSession`, `get_neo4j_driver`, or `get_pg_session`
- [ ] No service imports `AsyncDriver` (except `StatsService`)
- [ ] All endpoints return the same JSON as before (field names, types, values)
- [ ] Backend starts without errors
- [ ] All endpoints respond correctly:
  - `GET /works` — list with filters
  - `GET /works/{id}` — detail
  - `POST /works` — create
  - `PATCH /works/{id}` — update
  - `GET /authors` — list
  - `GET /authors/{id}` — detail with collections
  - `GET /streams` — list
  - `GET /streams/{id}` — detail with collections and works
  - `POST /streams` — create
  - `GET /collections` — list
  - `GET /collections/{id}` — detail
  - `GET /stats` — dashboard stats
  - `GET /health` — health check

### Verification

```bash
# No raw driver imports in routers
grep -rn "AsyncDriver\|get_neo4j_driver\|get_pg_session" src/bildung/routers/
# Expected: 0 results

# Services are classes
grep -n "class.*Service" src/bildung/services/*.py
# Expected: WorkService, AuthorService, StreamService, CollectionService, SeriesService, StatsService

# Dependencies exist
grep -n "def get_.*service\|def get_.*repo" src/bildung/dependencies.py
# Expected: multiple results

# Backend starts
uv run uvicorn src.bildung.main:app --reload &
sleep 3

# All endpoints work
curl -s http://localhost:8000/health
curl -s http://localhost:8000/works | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d)} works')"
curl -s http://localhost:8000/authors | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d)} authors')"
curl -s http://localhost:8000/streams | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d)} streams')"
curl -s http://localhost:8000/stats | python3 -m json.tool
```

---

## Handoff

### Decisions Made
- All services converted to classes. `WorkService` takes `WorkRepository + AsyncSession`; `StatsService` takes `AsyncDriver` directly (as spec).
- `_raw_to_work_response()` is a module-level function (not a static method on WorkService) in `authors.py`, `streams.py`, `collections.py`, `series.py`. It calls `WorkRepository._to_work()` (a static method) and then constructs `WorkResponse` with `stream_ids` from the raw record. This avoids cross-service imports.
- `dependencies.py` retains `get_neo4j_driver`, `get_pg_session`, `get_ol_client` for backward compatibility (openlibrary router may still use them).
- Moved the `AssignStreamRequest` import to the top-level in `routers/streams.py` (it was a local import before).

### Harder Than Expected
- `WorkService._work_to_response()` has `stream_ids=[]` because the domain `Work` model has no `stream_ids` field. This is a known regression: `GET /works/{id}` now returns `stream_ids: []` always. The stream checkboxes on the work detail page will be unchecked. Fix in Task 2A or Task 3A by extending WorkRepository to return stream_ids alongside the domain Work, or by exposing a separate method.
- `AuthorService.get()` constructs `work_entries` from raw Neo4j maps (Neo4j Node objects that support `.get()`) — same as before. The `{w: node, ord: int}` dict shape from `get_author_collections()` is preserved.

### Watch Out (for Task 2A / Task 3A)
- `stream_ids` regression in `WorkService.get()` — fix by either: (a) adding `get_stream_ids(work_id) -> list[str]` to WorkRepository and calling it in `WorkService.get()`, or (b) changing WorkRepository.get() to return a tuple `(Work, list[str])`.
- `StatsService` still uses `AsyncDriver` directly. Task 2C rewrites these as PG queries.
- `CollectionService.update()` now calls `self._collections.update()` which uses `_run_single()` with SET — the `count(c)` after DETACH DELETE returns 0. Soft 404 if the collection node exists but update is a no-op on unchanged fields. Check this behavior in integration testing.

### Deviations from Spec
- `_raw_to_work_response` is a standalone module-level function in each service (not a static method on the service class). Functionally equivalent, avoids namespace pollution on the class.
- The `AssignStreamRequest` import was a local import inside the endpoint in the old router — moved to top-level for cleanliness.
