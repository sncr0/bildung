# Task 2A — PostgreSQL Entity Schema

## Kickoff

### Read Before Starting
1. **This spec** (you're reading it)
2. **Next task spec:** `TASK_2B.md` — Data migration from Neo4j to PostgreSQL. That task will read from Neo4j and INSERT into the tables you create here. Column names, types, and constraints must match the domain models exactly. Get the schema right — the migration script will fail silently on type mismatches.
3. **Architecture reference:** `02_target_architecture.md` → "PostgreSQL is the system of record" section + the CREATE TABLE statements in Section 2.1.
4. **Current PG models:** `models/postgres.py` — already has `ReadingEvent`, `XpLedger`, `QuizQuestion`, `QuizAttempt`, `SrsSchedule`. The new entity tables go in the same file, using the same `Base`.

### Pre-conditions
- [ ] Task 1C is complete (services use repositories)
- [ ] Backend starts and all endpoints work
- [ ] PostgreSQL is running: `docker compose up -d` and `uv run alembic upgrade head`

### Lessons from Previous Task
_To be populated by Task 1C implementer._

---

## Spec

### Goal

Create PostgreSQL tables for works, authors, collections, streams, and series — the entity tables that will replace Neo4j as the system of record for scalar data. This includes the Alembic migration, SQLAlchemy models, and the junction tables for many-to-many relationships.

### What This Enables

Task 2B (data migration) needs tables to write into. Without this, the migration script has nowhere to put the data. The schema also enables Task 3A (test infrastructure) because integration tests need real tables.

### Files to Create

```
alembic/versions/002_entity_tables.py   — Alembic migration
```

### Files to Modify

```
src/bildung/models/postgres.py           — Add SQLAlchemy ORM models
```

### Files NOT to Modify

```
src/bildung/repositories/*.py   — DO NOT CHANGE. Task 2C switches repos to PG.
src/bildung/services/*.py       — DO NOT CHANGE.
src/bildung/models/domain.py    — DO NOT CHANGE.
src/bildung/models/api.py       — DO NOT CHANGE.
alembic/versions/001_*.py       — DO NOT CHANGE the existing migration.
```

### Exact Changes

#### `models/postgres.py` — New ORM Models

Add these after the existing models (keep `ReadingEvent`, `XpLedger`, etc. untouched):

```python
class WorkEntity(Base):
    """Work entity — scalar properties stored in PostgreSQL."""
    __tablename__ = "works"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(TEXT, nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR, nullable=False, server_default="to_read")
    language_read_in: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    date_read: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    density_rating: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    source_type: Mapped[str] = mapped_column(VARCHAR, nullable=False, server_default="fiction")
    personal_note: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    edition_note: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    significance: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    page_count: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    year_published: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    original_language: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    original_title: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    openlibrary_id: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    isbn: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuthorEntity(Base):
    __tablename__ = "authors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(TEXT, nullable=False)
    birth_year: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    death_year: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    nationality: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    primary_language: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    openlibrary_id: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CollectionEntity(Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(TEXT, nullable=False)
    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    type: Mapped[str] = mapped_column(VARCHAR, nullable=False, server_default="anthology")
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("authors.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StreamEntity(Base):
    __tablename__ = "streams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(TEXT, nullable=False)
    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    color: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SeriesEntity(Base):
    __tablename__ = "series"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(TEXT, nullable=False)
    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# --- Junction tables ---

class WorkAuthor(Base):
    __tablename__ = "work_authors"

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("works.id"), primary_key=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("authors.id"), primary_key=True
    )


class WorkCollection(Base):
    __tablename__ = "work_collections"

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("works.id"), primary_key=True
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id"), primary_key=True
    )
    order: Mapped[int | None] = mapped_column(INTEGER, nullable=True)


class WorkStream(Base):
    __tablename__ = "work_streams"

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("works.id"), primary_key=True
    )
    stream_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("streams.id"), primary_key=True
    )
    position: Mapped[int | None] = mapped_column(INTEGER, nullable=True)


class CollectionStream(Base):
    __tablename__ = "collection_streams"

    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id"), primary_key=True
    )
    stream_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("streams.id"), primary_key=True
    )
    order: Mapped[int | None] = mapped_column(INTEGER, nullable=True)


class WorkSeries(Base):
    __tablename__ = "work_series"

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("works.id"), primary_key=True
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id"), primary_key=True
    )
    order: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
```

**Note on column types:**
- `date_read` is `VARCHAR`, not `DATE` — the current system stores flexible date formats ("2024", "2024-03", "2024-03-15"). Parsing to a proper date would change behavior.
- `id` columns are `UUID`, not `VARCHAR` — domain models use `str`, but PostgreSQL should use native UUID for indexing and storage efficiency. The repository layer converts.
- Entity names use `*Entity` suffix to avoid collision with domain model names (`Work` vs `WorkEntity`).

#### Alembic Migration

Generate with: `uv run alembic revision --autogenerate -m "entity_tables"`

Or write manually. The migration should create:
1. All 5 entity tables
2. All 5 junction tables
3. Indexes on frequently queried columns

```python
"""Entity tables for works, authors, collections, streams, series.

Revision ID: 002
"""
# ... standard alembic header ...

def upgrade() -> None:
    # Entity tables
    op.create_table("works", ...)
    op.create_table("authors", ...)
    op.create_table("collections", ...)
    op.create_table("streams", ...)
    op.create_table("series", ...)

    # Junction tables
    op.create_table("work_authors", ...)
    op.create_table("work_collections", ...)
    op.create_table("work_streams", ...)
    op.create_table("collection_streams", ...)
    op.create_table("work_series", ...)

    # Indexes
    op.create_index("idx_works_status", "works", ["status"])
    op.create_index("idx_works_title", "works", ["title"])
    op.create_index("idx_authors_name", "authors", ["name"])
    op.create_index("idx_collections_type", "collections", ["type"])
    op.create_index("idx_collections_author", "collections", ["author_id"])


def downgrade() -> None:
    # Drop in reverse order (junctions first, then entities)
    op.drop_table("work_series")
    op.drop_table("collection_streams")
    op.drop_table("work_streams")
    op.drop_table("work_collections")
    op.drop_table("work_authors")
    op.drop_table("series")
    op.drop_table("streams")
    op.drop_table("collections")
    op.drop_table("authors")
    op.drop_table("works")
```

**Prefer `alembic revision --autogenerate`** if it works — it reads the SQLAlchemy models and generates the migration. Only write manually if autogenerate fails or produces incorrect output.

### Key Design Decisions (and why)

**1. `UUID` columns, not `VARCHAR` for IDs.**
Domain models use `str` for IDs. PostgreSQL should use native `UUID` for proper indexing, comparison, and storage (16 bytes vs 36+ bytes). The repository layer converts `str` ↔ `UUID`.

**2. `*Entity` suffix for ORM models.**
`WorkEntity` (ORM) vs `Work` (domain). This prevents import collisions and makes the distinction clear.

**3. No ORM relationships (no `relationship()` declarations).**
SQLAlchemy `relationship()` adds lazy loading, which is an anti-pattern with async. We use explicit JOINs in the repository layer. Adding relationships now would tempt the repository to use them, which makes queries implicit and hard to optimize.

**4. Junction table for series (`work_series`) not a collection type.**
Series has its own relationship type (`:PART_OF` in Neo4j) with its own `order` property. Representing it as a collection with `type='series'` would conflate two concepts and complicate the migration.

**5. `date_read` stays as `VARCHAR`.**
The system accepts "2024", "2024-03", "2024-03-15". Converting to `DATE` would require a parsing/normalization step that changes behavior. Phase 5 can standardize dates.

### DO NOT

1. **Do not add ORM relationships.** No `authors = relationship("AuthorEntity", secondary=...)`. Use explicit JOINs in repositories.

2. **Do not add CHECK constraints on enum-like columns.** `status`, `density_rating`, `source_type`, etc. are validated at the Pydantic layer. PostgreSQL CHECK constraints would need to be updated whenever a Literal type changes. Keep validation in one place.

3. **Do not modify the existing migration (`001_*`).** The existing tables (reading_events, xp_ledger, etc.) are production data. Create a new migration.

4. **Do not add triggers or stored procedures.** All logic lives in Python. The database is storage only.

5. **Do not add `updated_at` auto-update triggers.** The application layer will set `updated_at` explicitly. Triggers hide behavior.

6. **Do not create views or materialized views yet.** Those come in Task 2C when repositories switch to PostgreSQL reads.

7. **Do not change the existing `ReadingEvent` model.** Its `work_id` column currently stores a `uuid.UUID` without a foreign key to `works` (because the `works` table doesn't exist yet). Adding the FK is a separate concern for Task 2C.

8. **Do not seed any data.** The tables should be empty after migration. Task 2B populates them.

### Acceptance Criteria

- [ ] `models/postgres.py` has ORM models for all 5 entities and 5 junction tables
- [ ] All entity models extend the existing `Base`
- [ ] Alembic migration file exists in `alembic/versions/`
- [ ] `uv run alembic upgrade head` runs without errors
- [ ] All 10 tables exist in PostgreSQL (verify with `\dt` or equivalent)
- [ ] Junction tables have composite primary keys
- [ ] Foreign keys exist on junction tables
- [ ] Indexes exist on `works.status`, `works.title`, `authors.name`, `collections.type`, `collections.author_id`
- [ ] No ORM `relationship()` declarations
- [ ] Backend still starts (new models don't break existing code)
- [ ] Existing endpoints still work (the new tables are empty but don't interfere)

### Verification

```bash
# Migration runs
uv run alembic upgrade head

# Tables exist
uv run python -c "
from sqlalchemy import create_engine, inspect
from bildung.config import load_settings
cfg = load_settings()
engine = create_engine(cfg.pg_dsn.replace('+asyncpg', ''))
tables = inspect(engine).get_table_names()
expected = ['works', 'authors', 'collections', 'streams', 'series',
            'work_authors', 'work_collections', 'work_streams',
            'collection_streams', 'work_series']
for t in expected:
    assert t in tables, f'Missing table: {t}'
print(f'All {len(expected)} entity tables exist')
"

# Models importable
uv run python -c "
from bildung.models.postgres import WorkEntity, AuthorEntity, CollectionEntity, StreamEntity, SeriesEntity
from bildung.models.postgres import WorkAuthor, WorkCollection, WorkStream, CollectionStream, WorkSeries
print('All ORM models importable')
"

# Backend starts
uv run uvicorn src.bildung.main:app --reload &
sleep 3
curl -s http://localhost:8000/health
# Expected: {"status":"ok"}

# Existing endpoints unaffected
curl -s http://localhost:8000/works | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d)} works')"
```

---

## Handoff

_Fill in after completing this task:_

### Decisions Made
<!-- E.g., "Used autogenerate for migration — worked without manual edits" -->

### Harder Than Expected
<!-- E.g., "Had to add imports for INTEGER, TEXT to postgres.py" -->

### Watch Out (for Task 2B)
<!-- E.g., "UUID columns expect uuid.UUID objects, not strings — migration script needs to convert" -->

### Deviations from Spec
<!-- Did you deviate? Why? -->
