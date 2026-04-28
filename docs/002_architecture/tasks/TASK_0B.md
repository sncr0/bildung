# Task 0B — Extract Stats Service from Router

## Kickoff

### Read Before Starting
1. **This spec** (you're reading it)
2. **Next task spec:** `TASK_0C.md` — Backend fixes. That task will change how config is loaded. If you import `settings` directly from `config.py` here, Task 0C will have to update your new file. Use the same dependency injection pattern as other services.
3. **Architecture reference:** `02_target_architecture.md` → "Thin routers, domain services, repository layer" section. The key principle: routers own HTTP concerns, services own business logic, no Cypher in routers.

### Pre-conditions
- [ ] Backend starts: `uv run uvicorn src.bildung.main:app --reload`
- [ ] Stats endpoint works: `curl http://localhost:8000/stats` returns JSON

### Lessons from Previous Task
_This is the first task in the backend chain. No prior context._

---

## Spec

### Goal

Move the 6 Cypher queries from `routers/stats.py` into a new `services/stats.py` module. The router becomes a thin delegate that calls the service. This aligns the stats endpoint with the convention used by all other endpoints.

### What This Enables

Task 0C (backend fixes) and Task 1B (repository layer) will assume every database query lives in the service layer. If stats queries remain in the router, Task 1B has to handle the router as a special case when extracting queries into repositories.

### Files to Create

```
src/bildung/services/stats.py
```

### Files to Modify

```
src/bildung/routers/stats.py  — gut the query logic, delegate to service
```

### Exact Changes

#### `services/stats.py`

Create a new service module with a single function. The function should:
1. Accept an `AsyncDriver` parameter (matching the pattern in `services/works.py`, `services/authors.py`, etc.)
2. Execute the same 6 Cypher queries currently in the router
3. Return the `Stats` Pydantic model

```python
"""Stats service — aggregation queries for the dashboard."""
from __future__ import annotations

import logging
from neo4j import AsyncDriver
from bildung.models.api import Stats  # Move the Stats model here? No — see note below.

logger = logging.getLogger(__name__)


async def get_stats(driver: AsyncDriver) -> Stats:
    """Aggregate stats across all works, authors, and streams."""
    async with driver.session() as s:
        # ... same 6 queries as currently in routers/stats.py ...

    return Stats(
        total_works=total_works,
        total_authors=total_authors,
        total_streams=total_streams,
        by_status=by_status,
        by_year=by_year,
        by_language=by_language,
    )
```

**Note on the `Stats` model:** Currently `Stats` is defined inside `routers/stats.py`. Move it to `models/api.py` where all other response models live. Add it right after the `SeriesMembershipRequest` class (at the end of the file).

#### `routers/stats.py`

Reduce to a thin delegate:

```python
"""Stats router — /stats endpoint."""
from fastapi import APIRouter, Depends
from neo4j import AsyncDriver

from bildung.dependencies import get_neo4j_driver
from bildung.models.api import Stats
from bildung.services import stats as svc

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=Stats)
async def get_stats(driver: AsyncDriver = Depends(get_neo4j_driver)) -> Stats:
    return await svc.get_stats(driver)
```

#### `models/api.py`

Add the `Stats` model (moved from `routers/stats.py`):

```python
class Stats(BaseModel):
    total_works: int
    total_authors: int
    total_streams: int
    by_status: dict[str, int]
    by_year: dict[str, int]
    by_language: dict[str, int]
```

### DO NOT

1. **Do not change the Cypher queries.** Copy them exactly. Do not optimize, rewrite, or add new stats. The goal is to move code, not improve it.

2. **Do not change the response schema.** The `Stats` model fields must remain identical. The frontend depends on this exact shape.

3. **Do not add parameters to the service function.** `get_stats(driver)` is sufficient. Do not add `limit`, `offset`, `date_range`, or any other filter "for future use."

4. **Do not make `StatsService` a class.** The other services in this codebase are module-level async functions, not classes. Match the existing pattern. (Task 1C will convert to classes later.)

5. **Do not import `settings` or `config` in the new service.** The service receives what it needs as function arguments.

### Acceptance Criteria

- [ ] `services/stats.py` exists with `get_stats()` function
- [ ] `routers/stats.py` contains zero Cypher queries
- [ ] `routers/stats.py` contains zero direct Neo4j session usage
- [ ] `Stats` model lives in `models/api.py`, not in `routers/stats.py`
- [ ] `curl http://localhost:8000/stats` returns the same JSON as before (compare field names and value types)
- [ ] Backend starts without import errors

### Verification

```bash
# Start the backend
uv run uvicorn src.bildung.main:app --reload

# Verify stats endpoint
curl -s http://localhost:8000/stats | python3 -m json.tool

# Verify no Cypher remains in router
grep -n "MATCH\|RETURN\|count(" src/bildung/routers/stats.py
# Expected: 0 results

# Verify Stats model moved
grep -n "class Stats" src/bildung/models/api.py
# Expected: 1 result

grep -n "class Stats" src/bildung/routers/stats.py
# Expected: 0 results
```

---

## Handoff

_Fill in after completing this task:_

### Decisions Made
<!-- E.g., "Placed Stats model at end of api.py after SeriesMembershipRequest" -->

### Harder Than Expected
<!-- E.g., "The `by_year` query returns mixed types — some years are strings, some ints" -->

### Watch Out (for Task 0C)
<!-- E.g., "services/stats.py imports logger but doesn't use it yet — that's intentional for parity with other services" -->

### Deviations from Spec
<!-- Did you deviate? Why? -->
