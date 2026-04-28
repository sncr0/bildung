# Task 3B — Test Suites (Service, API, XP)

## Kickoff

### Read Before Starting
1. **This spec** (you're reading it)
2. **No next task spec** — this is the end of Chain 3 (Tests). These tests protect everything built so far and everything built after.
3. **Architecture reference:** `02_target_architecture.md` → "Testability is a first-class concern" section.
4. **Test infrastructure:** `tests/conftest.py` (created in Task 3A). Understand every fixture before writing tests. The `client` fixture gives you a full HTTP test client with real databases.

### Pre-conditions
- [ ] Task 3A is complete (test infrastructure exists)
- [ ] `uv run pytest tests/test_smoke.py -v` passes
- [ ] Docker is available (testcontainers needs it)

### Lessons from Previous Task
_To be populated by Task 3A implementer._

---

## Spec

### Goal

Write real tests that replace the empty stubs in `tests/`. Cover three layers: service logic (unit-ish tests with real databases), API integration (HTTP round-trips), and XP calculations (pure unit tests). The goal is confidence that the system works, not 100% coverage.

### What This Enables

Tests protect against regressions as the system evolves. Without tests, every future task risks silently breaking existing functionality. The XP tests are especially important because XP calculations are the core game mechanic — they must be deterministic and well-documented through test cases.

### Files to Modify

```
tests/test_works.py        — Replace stub with real tests
tests/test_xp.py           — Replace stub with real tests
```

### Files to Create

```
tests/test_api_works.py    — HTTP integration tests for /works endpoints
tests/test_api_authors.py  — HTTP integration tests for /authors endpoints
tests/test_services.py     — Service-layer tests (work creation, status transitions)
```

### Files NOT to Modify

```
tests/conftest.py          — DO NOT CHANGE (unless fixing a bug from Task 3A).
tests/test_openlibrary.py  — DO NOT CHANGE (already a real test).
src/bildung/**             — DO NOT CHANGE any application code.
```

### Exact Changes

#### `tests/test_api_works.py` — API Integration Tests

Test the work endpoints via HTTP:

```python
"""API integration tests for /works endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_work(client: AsyncClient):
    """Create a work via POST, retrieve it via GET."""
    resp = await client.post("/works", json={
        "title": "Crime and Punishment",
        "author": "Dostoyevsky",
        "status": "read",
        "date_read": "2024-01",
        "source_type": "fiction",
    })
    assert resp.status_code == 201
    work = resp.json()
    assert work["title"] == "Crime and Punishment"
    assert work["status"] == "read"
    assert len(work["authors"]) == 1
    assert work["authors"][0]["name"] == "Dostoyevsky"

    # GET should return the same work
    get_resp = await client.get(f"/works/{work['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "Crime and Punishment"


@pytest.mark.asyncio
async def test_list_works_empty(client: AsyncClient):
    """Empty database returns empty list."""
    resp = await client.get("/works")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_works_with_status_filter(client: AsyncClient):
    """Filter works by status."""
    # Create two works with different statuses
    await client.post("/works", json={"title": "Book A", "author": "Author A", "status": "read"})
    await client.post("/works", json={"title": "Book B", "author": "Author B", "status": "to_read"})

    # Filter by "read"
    resp = await client.get("/works", params={"status": "read"})
    works = resp.json()
    assert len(works) == 1
    assert works[0]["title"] == "Book A"


@pytest.mark.asyncio
async def test_update_work_status(client: AsyncClient):
    """PATCH a work's status."""
    create_resp = await client.post("/works", json={
        "title": "The Idiot", "author": "Dostoyevsky", "status": "to_read",
    })
    work_id = create_resp.json()["id"]

    patch_resp = await client.patch(f"/works/{work_id}", json={"status": "reading"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "reading"


@pytest.mark.asyncio
async def test_get_nonexistent_work(client: AsyncClient):
    """GET a work that doesn't exist returns 404."""
    resp = await client.get("/works/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_duplicate_work_is_idempotent(client: AsyncClient):
    """Creating the same work twice doesn't duplicate it (MERGE behavior)."""
    for _ in range(2):
        await client.post("/works", json={
            "title": "Brothers Karamazov", "author": "Dostoyevsky",
        })
    resp = await client.get("/works")
    titles = [w["title"] for w in resp.json()]
    assert titles.count("Brothers Karamazov") == 1
```

#### `tests/test_api_authors.py` — Author API Tests

```python
"""API integration tests for /authors endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_author_created_with_work(client: AsyncClient):
    """Creating a work auto-creates the author."""
    await client.post("/works", json={
        "title": "The Trial", "author": "Kafka",
    })
    resp = await client.get("/authors")
    assert resp.status_code == 200
    authors = resp.json()
    assert len(authors) == 1
    assert authors[0]["name"] == "Kafka"


@pytest.mark.asyncio
async def test_author_detail(client: AsyncClient):
    """Author detail includes works and completion stats."""
    await client.post("/works", json={
        "title": "The Castle", "author": "Kafka", "status": "read",
    })
    await client.post("/works", json={
        "title": "The Trial", "author": "Kafka", "status": "to_read",
    })

    authors = (await client.get("/authors")).json()
    author_id = authors[0]["id"]

    detail = (await client.get(f"/authors/{author_id}")).json()
    assert detail["total_works"] == 2
    assert detail["read_works"] == 1


@pytest.mark.asyncio
async def test_nonexistent_author(client: AsyncClient):
    resp = await client.get("/authors/nonexistent-id")
    assert resp.status_code == 404
```

#### `tests/test_services.py` — Service-Layer Tests

Test business logic at the service layer (below HTTP, above database):

```python
"""Service-layer tests — test business logic with real databases."""
import pytest

# Import service classes and repositories
# Use fixtures from conftest to create service instances with real DB connections
# Test:
# - Work creation generates deterministic IDs
# - Status transition from to_read → read creates a reading event
# - Author completion percentage calculation
# - Duplicate work creation is idempotent
```

The exact imports and fixture usage depend on how Task 1C structured the services. Read the service classes and adapt.

#### `tests/test_xp.py` — XP Calculation Tests

Replace the stub with real tests. XP calculations are pure functions — no database needed:

```python
"""XP calculation tests — these are the core game mechanic.

XP tests are pure unit tests: no database, no fixtures, just input → output.
"""
import pytest

# Import the XP calculation functions
# Test each factor:
# - Base XP for completing a work
# - Page count multiplier
# - Density multiplier (light → grueling)
# - Language multiplier (reading in a non-native language)
# - Significance bonus (major vs minor)
# - Streak bonuses
```

**Note:** The XP system may not be fully implemented yet. If XP functions don't exist, write tests that document the expected behavior (test-driven development). Mark them with `@pytest.mark.skip(reason="XP engine not implemented yet")` so they don't fail the suite but serve as a specification.

### Key Design Decisions (and why)

**1. API tests over service tests for most coverage.**
API tests exercise the full stack: routing, dependency injection, service logic, repository queries, database. They give the most confidence per test. Service tests are for logic that's hard to trigger via HTTP.

**2. Real data in tests, not random/generated.**
Use recognizable titles and authors (Dostoyevsky, Kafka, etc.) that match the project's domain. This makes test output readable and catches domain-specific edge cases.

**3. Each test is self-contained.**
Tests create their own data, assert their own expectations, and don't depend on other tests. The per-test cleanup in conftest ensures isolation.

**4. No test data factories.**
At this scale (<20 tests), inline `client.post()` calls are clearer than factory abstractions. If the test suite grows past 50 tests, factories become worth it.

### DO NOT

1. **Do not mock databases.** Use the testcontainer fixtures from conftest.

2. **Do not test internal implementation details.** Test behavior (create a work, verify it appears in list), not implementation (verify a specific SQL query was called).

3. **Do not test framework behavior.** Don't test "does FastAPI validate Pydantic models" — that's FastAPI's job. Test your business logic.

4. **Do not add test utilities, factories, or helpers.** Keep tests self-contained.

5. **Do not modify application code to make it more testable.** If something is hard to test, note it in the handoff.

6. **Do not aim for 100% coverage.** Cover the critical paths: CRUD operations, status transitions, filtering, edge cases (404s, duplicates). Skip testing trivial getters or obvious pass-through functions.

7. **Do not write performance tests or load tests.** This is a personal single-user app.

### Acceptance Criteria

- [ ] `tests/test_api_works.py` has at least 6 tests covering create, get, list, filter, update, 404
- [ ] `tests/test_api_authors.py` has at least 3 tests covering auto-creation, detail, 404
- [ ] `tests/test_services.py` has at least 3 tests covering business logic
- [ ] `tests/test_xp.py` has XP calculation tests (or documented skipped tests if engine isn't implemented)
- [ ] `uv run pytest -v` passes all tests (excluding skipped)
- [ ] No mocks for database access anywhere
- [ ] Tests are isolated (running them in any order produces the same results)
- [ ] No application code was modified

### Verification

```bash
# Run all tests
uv run pytest -v

# Run with parallel output
uv run pytest -v --tb=short

# Run specific suites
uv run pytest tests/test_api_works.py -v
uv run pytest tests/test_api_authors.py -v
uv run pytest tests/test_xp.py -v

# Verify isolation — run twice, same results
uv run pytest -v && uv run pytest -v
```

---

## Handoff

_Fill in after completing this task:_

### Decisions Made
<!-- E.g., "Skipped XP tests because engine isn't implemented — left specs as skipped tests" -->

### Harder Than Expected
<!-- E.g., "Status filter test required understanding the Cypher NULL handling" -->

### Watch Out
<!-- E.g., "test_create_duplicate relies on MERGE behavior — if repo changes to INSERT, it'll fail" -->

### Deviations from Spec
<!-- Did you deviate? Why? -->
