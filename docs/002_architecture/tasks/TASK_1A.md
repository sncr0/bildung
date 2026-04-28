# Task 1A — Domain Models

## Kickoff

### Read Before Starting
1. **This spec** (you're reading it)
2. **Next task spec:** `TASK_1B.md` — Repository layer. Repositories will return these domain models, not raw dicts. The field names, types, and optionality you define here become the contract that repositories implement. Get the types right.
3. **Architecture reference:** `02_target_architecture.md` → "Domain models are the contract" section. Key principle: domain models are used everywhere — services work with them, repositories return them, API schemas convert to/from them.
4. **Current state reference:** `01_current_state_analysis.md` → "`_record_to_work()` is a public interface pretending to be private" — understand the problem this task solves.

### Pre-conditions
- [ ] Task 0C is complete (config singleton removed)
- [ ] Backend starts without import errors
- [ ] You have read `models/api.py`, `models/neo4j.py`, and `models/postgres.py` to understand the current model landscape

### Lessons from Previous Task
_To be populated by Task 0C implementer._

---

## Spec

### Goal

Create `models/domain.py` — a set of pure Pydantic models that represent the core domain entities (Work, Author, Collection, Stream, Series) independently of any database. These models will become the internal contract that repositories return and services work with.

### What This Enables

Task 1B (repository layer) needs typed return values. Currently repositories don't exist and services return either raw dicts or `WorkResponse` API models. Domain models give the repository layer a return type that is:
- Independent of Neo4j record format
- Independent of API response shape (no `stream_ids` list in the domain — that's an API convenience)
- Usable by services without importing API schemas

### Files to Create

```
src/bildung/models/domain.py
```

### Files to Modify

```
src/bildung/models/__init__.py  — add domain model re-exports (if the file exists and has exports)
```

### Files NOT to Modify

```
src/bildung/models/api.py       — DO NOT CHANGE. API schemas stay as-is for now.
src/bildung/models/neo4j.py     — DO NOT CHANGE. Will be cleaned up in a later task.
src/bildung/models/postgres.py  — DO NOT CHANGE.
src/bildung/services/*.py       — DO NOT CHANGE. Task 1C will rewire services.
src/bildung/routers/*.py        — DO NOT CHANGE.
```

### Exact Changes

#### `models/domain.py`

The domain models should:
1. Use Pydantic `BaseModel` (not dataclasses — we want validation and serialization)
2. Import Literal types from `models/neo4j.py` (these are the canonical enum definitions)
3. Represent the **domain truth**, not the API shape or the database shape

```python
"""Core domain models — the internal contract for repositories and services.

These models represent the domain entities independent of any database or API format.
Repositories return them. Services work with them. API schemas convert to/from them.

Rules:
- No SQLAlchemy imports
- No Neo4j driver imports
- No FastAPI imports
- Literal types come from models/neo4j.py (the canonical source)
"""
from __future__ import annotations

from pydantic import BaseModel

from bildung.models.neo4j import (
    CollectionTypeLiteral,
    DensityLiteral,
    SignificanceLiteral,
    SourceTypeLiteral,
    StatusLiteral,
)


class AuthorSummary(BaseModel):
    """Minimal author reference embedded in other models."""
    id: str
    name: str


class CollectionMembership(BaseModel):
    """A work's membership in a collection, with optional ordering."""
    collection_id: str
    collection_name: str
    collection_type: CollectionTypeLiteral
    order: int | None = None


class Work(BaseModel):
    """A literary work — the central entity of the system."""
    id: str
    title: str
    status: StatusLiteral = "to_read"
    language_read_in: str | None = None
    date_read: str | None = None
    density_rating: DensityLiteral | None = None
    source_type: SourceTypeLiteral = "fiction"
    personal_note: str | None = None
    edition_note: str | None = None
    significance: SignificanceLiteral | None = None
    # Enrichment fields (from OpenLibrary)
    page_count: int | None = None
    year_published: int | None = None
    original_language: str | None = None
    original_title: str | None = None
    openlibrary_id: str | None = None
    isbn: str | None = None
    cover_url: str | None = None
    # Relationships (populated by repository when needed)
    authors: list[AuthorSummary] = []
    collections: list[CollectionMembership] = []


class Author(BaseModel):
    """A literary author."""
    id: str
    name: str
    birth_year: int | None = None
    death_year: int | None = None
    nationality: str | None = None
    primary_language: str | None = None
    openlibrary_id: str | None = None


class Collection(BaseModel):
    """A named grouping of works (major works, minor works, series, anthology)."""
    id: str
    name: str
    description: str | None = None
    type: CollectionTypeLiteral = "anthology"
    author_id: str | None = None


class Stream(BaseModel):
    """A personal reading path — a curated intellectual storyline."""
    id: str
    name: str
    description: str | None = None
    color: str | None = None
    created_at: str = ""


class Series(BaseModel):
    """An ordered series of works (e.g., The Sea of Fertility tetralogy)."""
    id: str
    name: str
    description: str | None = None
```

### Key Design Decisions (and why)

**1. `Work.authors` is a list, not a set of IDs.**
The API response includes author names, so the domain model should too. Repositories will populate this by joining. This avoids a second lookup at the API layer.

**2. `Work.collections` uses `CollectionMembership`, not `CollectionSummary`.**
The domain cares about "which collection, what type, what order" — not "how many works are in that collection." Read counts and work counts are API/stats concerns, not domain concerns.

**3. No `stream_ids` field on `Work`.**
The current API response has `stream_ids: list[str]`. This is an API convenience for the frontend. The domain model doesn't need it — the relationship lives in the graph. The API layer can add it when constructing the response.

**4. `Stream.created_at` is `str`, not `datetime`.**
Currently stored as an ISO string in Neo4j. Once we migrate to PostgreSQL (Phase 2), this becomes a proper `datetime`. For now, match the existing storage format.

**5. No `total_works`, `read_works`, `completion_pct`, `work_count`, `read_count` fields.**
These are computed aggregates for the API response. They don't belong in the domain model. The API schemas (`AuthorResponse`, `CollectionResponse`, etc.) add them.

**6. The models mirror the `WorkNode`/`AuthorNode` in `models/neo4j.py` but are NOT the same.**
`WorkNode` uses `uuid.UUID` for `id`; domain `Work` uses `str`. `WorkNode` has `cover_url`; domain `Work` has it too. The difference is purpose: `WorkNode` is aspirational documentation that's never used; domain `Work` is the actual internal contract.

### DO NOT

1. **Do not add methods to the models.** No `Work.is_read()`, no `Author.full_name()`, no `Collection.progress()`. Domain models are data containers. Logic lives in services.

2. **Do not add validators beyond type checking.** No `@field_validator` that normalizes titles, strips whitespace, or validates date formats. The current system doesn't do this, and adding validation changes behavior. That's a separate task.

3. **Do not create response models here.** `WorkResponse`, `AuthorResponse`, etc. already exist in `api.py` and have different shapes (they include computed fields like `work_count`). Do not duplicate them.

4. **Do not modify `models/api.py`.** The API schemas will be wired to use domain models in Task 1C. For now, both exist independently.

5. **Do not create inheritance hierarchies.** No `BaseEntity` with `id: str`. No `HasTimestamps` mixin. Five flat models are clearer than a class hierarchy.

6. **Do not import from `services/`, `routers/`, `repositories/`, or `db/`.** Domain models depend on nothing except `models/neo4j.py` (for Literal types) and Pydantic.

### Acceptance Criteria

- [ ] `models/domain.py` exists with 6 model classes: `AuthorSummary`, `CollectionMembership`, `Work`, `Author`, `Collection`, `Stream`, `Series`
- [ ] No imports from `sqlalchemy`, `neo4j`, `fastapi`, or any `services`/`routers`/`db` module
- [ ] All models are Pydantic `BaseModel` subclasses
- [ ] `Work` has all scalar fields that currently exist on Neo4j Work nodes (check against `models/neo4j.py:WorkNode`)
- [ ] `Author` has all scalar fields that currently exist on Neo4j Author nodes
- [ ] Types match the existing Literal types from `models/neo4j.py`
- [ ] No computed/aggregate fields (no `work_count`, `read_count`, `completion_pct`)
- [ ] Backend still starts (the new file should not break existing imports)
- [ ] The module can be imported standalone: `python -c "from bildung.models.domain import Work, Author; print('OK')"`

### Verification

```bash
# File exists with correct classes
grep -c "class.*BaseModel" src/bildung/models/domain.py
# Expected: 7 (AuthorSummary, CollectionMembership, Work, Author, Collection, Stream, Series)

# No forbidden imports
grep -n "sqlalchemy\|neo4j import\|fastapi\|from bildung.services\|from bildung.routers\|from bildung.db" src/bildung/models/domain.py
# Expected: 0 results

# Importable
uv run python -c "from bildung.models.domain import Work, Author, Collection, Stream, Series; print('All domain models importable')"

# Backend still starts
uv run uvicorn src.bildung.main:app --reload &
sleep 3
curl -s http://localhost:8000/health
# Expected: {"status":"ok"}
```

---

## Handoff

_Fill in after completing this task:_

### Decisions Made
<!-- E.g., "Included openlibrary_id on Author but not on Collection — collections don't have OL entries" -->

### Harder Than Expected
<!-- E.g., "Had to check which fields Work nodes actually have in Neo4j vs what WorkNode documents" -->

### Watch Out (for Task 1B)
<!-- E.g., "Work.collections uses CollectionMembership which has collection_type — repos need to join the collection node to get this" -->

### Deviations from Spec
<!-- Did you deviate? Why? -->
