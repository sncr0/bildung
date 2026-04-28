# Task 3A — Test Infrastructure (Testcontainers + Conftest)

## Kickoff

### Read Before Starting
1. **This spec** (you're reading it)
2. **Next task spec:** `TASK_3B.md` — Test suites. That task writes the actual tests using the fixtures you create here. If fixtures are wrong (wrong session scope, missing cleanup, broken AppState injection), every test in Task 3B fails and you'll be debugging infrastructure instead of writing tests.
3. **Architecture reference:** `02_target_architecture.md` → "Testability is a first-class concern" section. Key patterns: session-scoped testcontainers, per-test cleanup, AppState injection, no mocks for databases.
4. **Finalysis reference:** The finalysis project uses the same testcontainers pattern. If you need to understand how `create_app(state=test_state)` works, look at `main.py:create_app()` which already accepts an optional `state` parameter.

### Pre-conditions
- [ ] Task 1C is complete (services are classes with constructor injection)
- [ ] Backend starts and all endpoints work
- [ ] Docker is available (testcontainers needs Docker to spin up containers)

### Lessons from Previous Task
_To be populated by Task 1C implementer._

---

## Spec

### Goal

Set up the test infrastructure: add testcontainer dependencies, create `conftest.py` with database fixtures, and verify that a minimal test can run against real databases. No actual feature tests in this task — just the plumbing.

### What This Enables

Task 3B (test suites) writes service tests, API integration tests, and XP calculation tests. All of those depend on working database fixtures and AppState injection. Building the infrastructure separately ensures Task 3B can focus on test logic, not fixture debugging.

### Files to Modify

```
pyproject.toml                    — Add test dependencies
```

### Files to Create

```
tests/conftest.py                 — Database fixtures + AppState injection
tests/test_smoke.py               — Minimal smoke test proving the infrastructure works
```

### Files NOT to Modify

```
src/bildung/**                    — DO NOT CHANGE any application code.
tests/test_works.py               — DO NOT CHANGE existing test stubs (Task 3B replaces them).
tests/test_ingestion.py           — DO NOT CHANGE.
tests/test_xp.py                  — DO NOT CHANGE.
tests/test_openlibrary.py         — DO NOT CHANGE (this is a real test).
```

### Exact Changes

#### `pyproject.toml` — Test Dependencies

Add to the dev dependency group:

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "testcontainers[postgres,neo4j]>=4.0",
    "httpx>=0.27",
]
```

Install with: `uv sync --group dev`

**Note:** Check if `pytest-asyncio` and `httpx` are already in the dependencies. If so, don't add duplicates. Only add what's missing.

#### `tests/conftest.py`

```python
"""Shared test fixtures — database containers, sessions, AppState, test client."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from neo4j import AsyncGraphDatabase
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.neo4j import Neo4jContainer
from testcontainers.postgres import PostgresContainer

from bildung.app_state import AppState
from bildung.config import Settings
from bildung.main import create_app
from bildung.models.postgres import Base


# ---------------------------------------------------------------------------
# Event loop — single loop for the entire test session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for all async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Containers — session-scoped (one per test run, not per test)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def pg_container():
    """Start a PostgreSQL container for the test session."""
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def neo4j_container():
    """Start a Neo4j container for the test session."""
    with Neo4jContainer("neo4j:5") as neo:
        yield neo


# ---------------------------------------------------------------------------
# Database engines/drivers — session-scoped
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def pg_engine(pg_container) -> AsyncEngine:
    url = pg_container.get_connection_url().replace("psycopg2", "asyncpg")
    return create_async_engine(url)


@pytest.fixture(scope="session")
def pg_session_factory(pg_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(pg_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session")
async def _create_tables(pg_engine):
    """Create all tables once at the start of the session."""
    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture(scope="session")
async def neo4j_driver(neo4j_container):
    uri = neo4j_container.get_connection_url()
    driver = AsyncGraphDatabase.driver(uri, auth=("neo4j", "test"))
    yield driver
    await driver.close()


# ---------------------------------------------------------------------------
# Per-test fixtures — clean state for each test
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def pg_session(
    pg_session_factory, _create_tables
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh PG session and clean up after each test."""
    async with pg_session_factory() as session:
        yield session
        await session.rollback()
    # Truncate all tables after each test
    async with pg_session_factory() as cleanup:
        for table in reversed(Base.metadata.sorted_tables):
            await cleanup.execute(text(f"TRUNCATE {table.name} CASCADE"))
        await cleanup.commit()


@pytest_asyncio.fixture
async def clean_neo4j(neo4j_driver):
    """Wipe Neo4j after each test."""
    yield
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")


# ---------------------------------------------------------------------------
# Test settings + AppState
# ---------------------------------------------------------------------------

@pytest.fixture
def test_settings(pg_container, neo4j_container) -> Settings:
    """Create Settings pointing at test containers."""
    pg_url = pg_container.get_connection_url().replace("psycopg2", "asyncpg")
    neo_url = neo4j_container.get_connection_url()
    return Settings(
        pg_dsn=pg_url,
        neo4j_uri=neo_url,
        neo4j_user="neo4j",
        neo4j_password="test",
    )


@pytest_asyncio.fixture
async def app_state(
    test_settings, pg_engine, pg_session_factory, neo4j_driver
) -> AppState:
    """Create an AppState with test containers — no lifespan needed."""
    import httpx
    from bildung.services.openlibrary import OpenLibraryClient

    http = httpx.AsyncClient()
    ol = OpenLibraryClient(http)
    state = AppState(
        settings=test_settings,
        pg_engine=pg_engine,
        pg_session_factory=pg_session_factory,
        neo4j_driver=neo4j_driver,
        ol_client=ol,
        _http_client=http,
    )
    yield state
    await http.aclose()


@pytest_asyncio.fixture
async def client(app_state, _create_tables, clean_neo4j) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with injected AppState — tests hit real databases."""
    app = create_app(state=app_state)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

**Key design points:**

1. **Session-scoped containers.** Starting a PostgreSQL and Neo4j container takes 5-10 seconds each. Session scope means they start once for the entire test run, not once per test.

2. **Per-test cleanup.** Each test gets a clean database via `TRUNCATE ... CASCADE` (PG) and `MATCH (n) DETACH DELETE n` (Neo4j). This is fast (milliseconds) and ensures test isolation.

3. **AppState injection via `create_app(state=...)`**. The `main.py:create_app()` function already supports this pattern — it skips the lifespan and uses the provided state directly.

4. **`httpx.AsyncClient` with `ASGITransport`** — sends requests directly to the ASGI app without a real HTTP server. Fast, no port conflicts.

5. **Tables created via `Base.metadata.create_all`**, not Alembic. This is simpler for tests and ensures the schema matches the ORM models exactly.

#### `tests/test_smoke.py`

A minimal test proving the infrastructure works:

```python
"""Smoke test — verify test infrastructure works."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    """Health endpoint responds through test client."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_empty_works_list(client: AsyncClient):
    """Works endpoint returns empty list with clean database."""
    response = await client.get("/works")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_empty_authors_list(client: AsyncClient):
    """Authors endpoint returns empty list with clean database."""
    response = await client.get("/authors")
    assert response.status_code == 200
    assert response.json() == []
```

### Key Design Decisions (and why)

**1. `Base.metadata.create_all`, not Alembic for test tables.**
Alembic requires migration history and ordering. `create_all` creates all tables from the current ORM models — simpler, faster, and always in sync.

**2. TRUNCATE CASCADE, not DROP/CREATE per test.**
Dropping and recreating tables is slow. Truncating is fast and achieves the same isolation. CASCADE handles FK constraints.

**3. No mocks for databases.**
The architecture doc is explicit: "No mocks for databases. Real queries against real databases. Mocks hide bugs; real databases expose them."

**4. `event_loop` fixture at session scope.**
`pytest-asyncio` needs a compatible event loop. Session-scoped ensures all async fixtures share the same loop.

**5. Settings constructed with explicit values, not `.env` file.**
Test settings point at container URLs, not the dev environment. No `.env` file is loaded during tests.

### DO NOT

1. **Do not use `unittest.mock` or `pytest-mock` for database access.** Real databases via testcontainers. Period.

2. **Do not add `monkeypatch` for settings.** Construct `Settings` directly with test values.

3. **Do not change application code to make it more testable.** The `create_app(state=...)` pattern already exists. If something is hard to test, note it in the handoff for a later task.

4. **Do not write feature tests.** This task creates infrastructure only. `test_smoke.py` proves the plumbing works. Task 3B writes real tests.

5. **Do not add test utility functions or factories.** No `create_test_work()`, no `WorkFactory`, no `seed_test_data()`. Task 3B will add what it needs. Keep this task minimal.

6. **Do not install `factory_boy`, `faker`, or other test data libraries.** Plain fixtures are sufficient for this scale.

7. **Do not modify existing test files.** `test_works.py`, `test_ingestion.py`, `test_xp.py` are stubs that Task 3B will rewrite. `test_openlibrary.py` is a real test — leave it alone.

### Acceptance Criteria

- [ ] `pyproject.toml` has testcontainers, pytest-asyncio, and httpx in dev dependencies
- [ ] `uv sync --group dev` installs all test dependencies
- [ ] `tests/conftest.py` exists with all fixtures
- [ ] `tests/test_smoke.py` exists with 3 smoke tests
- [ ] `uv run pytest tests/test_smoke.py -v` passes all 3 tests
- [ ] Tests use real PostgreSQL and Neo4j containers (not mocks)
- [ ] Tests do not require a `.env` file or running Docker Compose services
- [ ] Each test gets a clean database (run two tests that both insert data — they shouldn't interfere)
- [ ] No application code was modified

### Verification

```bash
# Install dependencies
uv sync --group dev

# Run smoke tests
uv run pytest tests/test_smoke.py -v
# Expected: 3 passed

# Run with output to verify containers start
uv run pytest tests/test_smoke.py -v -s
# Expected: see container startup logs, then 3 passed

# Verify test isolation
uv run pytest tests/test_smoke.py tests/test_smoke.py -v
# Expected: 6 passed (each test still sees empty database)
```

---

## Handoff

_Fill in after completing this task:_

### Decisions Made
<!-- E.g., "Used neo4j:5-community image instead of neo4j:5 — smaller, same API" -->

### Harder Than Expected
<!-- E.g., "pytest-asyncio event loop scoping required specific config in pyproject.toml" -->

### Watch Out (for Task 3B)
<!-- E.g., "The client fixture depends on clean_neo4j — tests that don't use Neo4j still wipe it" -->

### Deviations from Spec
<!-- Did you deviate? Why? -->
