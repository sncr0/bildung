# Task 1B — Repository Layer

## Kickoff

### Read Before Starting
1. **This spec** (you're reading it)
2. **Next task spec:** `TASK_1C.md` — Service + dependency + router rewiring. That task will replace raw `AsyncDriver` arguments in services with repository instances. The repository interfaces you define here become the injection targets. Get the method signatures right.
3. **Architecture reference:** `02_target_architecture.md` → "Thin routers, domain services, repository layer" section + "Data Flow: Read Path" and "Data Flow: Write Path"
4. **Domain models reference:** `models/domain.py` (created in Task 1A). Repositories return these models, not raw dicts or API schemas.

### Pre-conditions
- [ ] Task 1A is complete (domain models exist)
- [ ] `python -c "from bildung.models.domain import Work, Author, Collection, Stream, Series"` works
- [ ] Backend starts without import errors

### Lessons from Previous Task
_To be populated by Task 1A implementer._

---

## Spec

### Goal

Create `repositories/` — a set of repository classes that encapsulate all Neo4j Cypher queries behind typed interfaces. Each repository returns domain models from `models/domain.py`, not raw dicts or API schemas. This is the first step toward making database access testable and swappable.

### What This Enables

Task 1C (service rewiring) will change every service function to receive repositories instead of raw `AsyncDriver`. Without repositories, services can't be decoupled from Neo4j. The repository layer also becomes the single place where Cypher queries live — no more Cypher scattered across service modules.

### Files to Create

```
src/bildung/repositories/__init__.py
src/bildung/repositories/base.py
src/bildung/repositories/works.py
src/bildung/repositories/authors.py
src/bildung/repositories/collections.py
src/bildung/repositories/streams.py
src/bildung/repositories/series.py
```

### Files to Modify

None. Repositories are created but not yet wired in. Services continue to use `AsyncDriver` directly until Task 1C.

### Files NOT to Modify

```
src/bildung/services/*.py       — DO NOT CHANGE. Task 1C rewires services.
src/bildung/routers/*.py        — DO NOT CHANGE.
src/bildung/dependencies.py     — DO NOT CHANGE. Task 1C adds repository factories.
src/bildung/models/api.py       — DO NOT CHANGE.
src/bildung/models/domain.py    — DO NOT CHANGE.
```

### Exact Changes

#### `repositories/__init__.py`

Empty file. No barrel exports — import from specific modules.

```python
```

#### `repositories/base.py`

Base class that wraps the `AsyncDriver` and provides session helpers:

```python
"""Base repository — shared Neo4j session helpers."""
from __future__ import annotations

from neo4j import AsyncDriver, Record


class NeoRepository:
    """Base for repositories that talk to Neo4j."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def _run(self, query: str, **params: object) -> list[Record]:
        """Execute a query and return all records."""
        async with self._driver.session() as session:
            result = await session.run(query, params)
            return [r async for r in result]

    async def _run_single(self, query: str, **params: object) -> Record | None:
        """Execute a query and return a single record (or None)."""
        async with self._driver.session() as session:
            result = await session.run(query, params)
            return await result.single()
```

**That's it.** Two helpers. Do not add `_run_write`, `_run_in_tx`, `_count`, or any other helpers "for convenience." Task 1C will add transactional helpers if needed.

#### `repositories/works.py`

Move all Work-related Cypher queries from `services/works.py` into `WorkRepository`. The `_record_to_work()` mapping function moves here and becomes a private method.

```python
"""Work repository — all Work CRUD and query operations."""
from __future__ import annotations

from neo4j import AsyncDriver

from bildung.models.domain import AuthorSummary, CollectionMembership, Work
from bildung.repositories.base import NeoRepository


class WorkRepository(NeoRepository):
    """Encapsulates all Work-related Neo4j queries."""

    async def list(
        self,
        status: str | None = None,
        author: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Work]:
        records = await self._run(
            """
            MATCH (w:Work)
            WHERE $status IS NULL OR w.status = $status
            OPTIONAL MATCH (a:Author)-[:WROTE]->(w)
            WITH w {.*} AS work, collect({id: a.id, name: a.name}) AS authors
            WHERE (
                $author IS NULL OR
                any(auth IN authors WHERE toLower(auth.name) CONTAINS toLower($author))
            )
            RETURN work, authors
            ORDER BY work.title
            SKIP $offset LIMIT $limit
            """,
            status=status,
            author=author,
            offset=offset,
            limit=limit,
        )
        return [self._to_work(r["work"], r["authors"]) for r in records]

    async def get(self, work_id: str) -> Work | None:
        record = await self._run_single(
            """
            MATCH (w:Work {id: $id})
            OPTIONAL MATCH (a:Author)-[:WROTE]->(w)
            OPTIONAL MATCH (w)-[:BELONGS_TO]->(st:Stream)
            OPTIONAL MATCH (w)-[r:IN_COLLECTION]->(c:Collection)
            RETURN w {.*} AS work,
                   collect(DISTINCT {id: a.id, name: a.name}) AS authors,
                   collect(DISTINCT st.id) AS stream_ids,
                   collect(DISTINCT {id: c.id, name: c.name, type: c.type, order: r.order}) AS collections
            """,
            id=work_id,
        )
        if not record:
            return None
        return self._to_work(
            record["work"], record["authors"],
            record["collections"],
        )

    async def create(
        self,
        work_id: str,
        title: str,
        author_id: str,
        author_name: str,
        *,
        status: str = "to_read",
        language_read_in: str | None = None,
        date_read: str | None = None,
        density_rating: str | None = None,
        source_type: str = "fiction",
        personal_note: str | None = None,
        significance: str | None = None,
    ) -> Work:
        """Create a work node and link to its author. Returns the created Work."""
        async with self._driver.session() as session:
            async with await session.begin_transaction() as tx:
                # Ensure author exists
                exists = await tx.run(
                    "MATCH (a:Author {id: $id}) RETURN count(a) AS n", id=author_id
                )
                rec = await exists.single()
                if rec["n"] == 0:
                    await tx.run(
                        "CREATE (a:Author {id: $id, name: $name})",
                        id=author_id, name=author_name,
                    )

                await tx.run(
                    """
                    MERGE (w:Work {id: $id})
                    ON CREATE SET
                        w.title            = $title,
                        w.status           = $status,
                        w.language_read_in = $language_read_in,
                        w.date_read        = $date_read,
                        w.density_rating   = $density_rating,
                        w.source_type      = $source_type,
                        w.personal_note    = $personal_note,
                        w.significance     = $significance
                    """,
                    id=work_id, title=title, status=status,
                    language_read_in=language_read_in,
                    date_read=date_read, density_rating=density_rating,
                    source_type=source_type, personal_note=personal_note,
                    significance=significance,
                )

                await tx.run(
                    """
                    MATCH (a:Author {id: $aid})
                    MATCH (w:Work {id: $wid})
                    MERGE (a)-[:WROTE]->(w)
                    """,
                    aid=author_id, wid=work_id,
                )

        return await self.get(work_id)  # type: ignore[return-value]

    async def update(self, work_id: str, updates: dict) -> Work | None:
        """Update scalar properties on a Work node."""
        if not updates:
            return await self.get(work_id)
        async with self._driver.session() as session:
            await session.run(
                "MATCH (w:Work {id: $id}) SET w += $updates",
                id=work_id, updates=updates,
            )
        return await self.get(work_id)

    # --- private mapping ---

    @staticmethod
    def _to_work(
        work_map: dict,
        authors_list: list[dict],
        collections_list: list[dict] | None = None,
    ) -> Work:
        """Map a Neo4j record to a domain Work."""
        authors = [
            AuthorSummary(id=a["id"] or "", name=a["name"] or "")
            for a in authors_list
            if a.get("name")
        ]
        collections = [
            CollectionMembership(
                collection_id=c["id"] or "",
                collection_name=c["name"] or "",
                collection_type=c.get("type", "anthology"),
                order=c.get("order"),
            )
            for c in (collections_list or [])
            if c.get("id")
        ]
        return Work(
            id=work_map.get("id", ""),
            title=work_map.get("title", ""),
            status=work_map.get("status", "to_read"),
            language_read_in=work_map.get("language_read_in"),
            date_read=work_map.get("date_read"),
            density_rating=work_map.get("density_rating"),
            source_type=work_map.get("source_type", "fiction"),
            personal_note=work_map.get("personal_note"),
            edition_note=work_map.get("edition_note"),
            significance=work_map.get("significance"),
            page_count=work_map.get("page_count"),
            year_published=work_map.get("year_published"),
            original_language=work_map.get("original_language"),
            original_title=work_map.get("original_title"),
            openlibrary_id=work_map.get("openlibrary_id"),
            isbn=work_map.get("isbn"),
            cover_url=work_map.get("cover_url"),
            authors=authors,
            collections=collections,
        )
```

**Key:** `_to_work` maps from Neo4j dict → domain `Work`. This replaces `services/works.py:_record_to_work()`. Notice it returns `Work` (domain), not `WorkResponse` (API). The API layer will convert domain → response in Task 1C.

**Note on `create()` signature:** It takes explicit parameters, not a `CreateWorkRequest` — repositories don't know about API schemas. The service will unpack the request and call the repository.

#### `repositories/authors.py`

Move all Author-related queries from `services/authors.py`:

```python
"""Author repository — all Author queries."""
from __future__ import annotations

from bildung.models.domain import Author, AuthorSummary, CollectionMembership, Work
from bildung.repositories.base import NeoRepository
from bildung.repositories.works import WorkRepository


class AuthorRepository(NeoRepository):
    """Encapsulates all Author-related Neo4j queries."""

    async def list(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Return author data with aggregate counts.

        Returns raw dicts with keys: author, total_works, read_works,
        major_total, major_read. The service layer computes completion_pct
        and builds AuthorResponse.
        """
        records = await self._run(
            """
            MATCH (a:Author)
            OPTIONAL MATCH (a)-[:WROTE]->(w:Work)
            WITH a,
                 count(w)                                           AS total_works,
                 sum(CASE WHEN w.status = 'read' THEN 1 ELSE 0 END) AS read_works
            OPTIONAL MATCH (c:Collection {author_id: a.id, type: 'major_works'})
            OPTIONAL MATCH (w2:Work)-[:IN_COLLECTION]->(c)
            WITH a, total_works, read_works,
                 count(w2) AS major_total,
                 sum(CASE WHEN w2.status = 'read' THEN 1 ELSE 0 END) AS major_read
            RETURN a {.*} AS author, total_works, read_works, major_total, major_read
            ORDER BY a.name
            SKIP $offset LIMIT $limit
            """,
            offset=offset,
            limit=limit,
        )
        return [dict(r) for r in records]

    async def get(self, author_id: str) -> Author | None:
        """Return a single author's scalar fields."""
        record = await self._run_single(
            "MATCH (a:Author {id: $id}) RETURN a {.*} AS author",
            id=author_id,
        )
        if not record:
            return None
        return self._to_author(record["author"])

    async def get_with_stats(self, author_id: str) -> dict | None:
        """Return author with aggregate stats for the detail view.

        Returns a raw dict because the service layer needs to combine this
        with collections and uncollected works to build AuthorResponse.
        """
        record = await self._run_single(
            """
            MATCH (a:Author {id: $id})
            OPTIONAL MATCH (a)-[:WROTE]->(w:Work)
            WITH a,
                 count(w)                                           AS total_works,
                 sum(CASE WHEN w.status = 'read' THEN 1 ELSE 0 END) AS read_works
            OPTIONAL MATCH (c:Collection {author_id: $id, type: 'major_works'})
            OPTIONAL MATCH (w2:Work)-[:IN_COLLECTION]->(c)
            WITH a, total_works, read_works,
                 count(w2) AS major_total,
                 sum(CASE WHEN w2.status = 'read' THEN 1 ELSE 0 END) AS major_read
            RETURN a {.*} AS author, total_works, read_works, major_total, major_read
            """,
            id=author_id,
        )
        if not record:
            return None
        return dict(record)

    async def get_author_collections(self, author_id: str) -> list[dict]:
        """Return all collections owned by an author with their works.

        Returns raw records for the service to assemble into CollectionDetailResponse.
        """
        records = await self._run(
            """
            MATCH (c:Collection {author_id: $id})
            OPTIONAL MATCH (w:Work)-[r:IN_COLLECTION]->(c)
            WITH c, coalesce(r.order, 9999) AS sort_ord, r.order AS ord, w
            ORDER BY c.type ASC, c.name ASC, sort_ord ASC, w.title ASC
            WITH c, collect({w: w, ord: ord}) AS work_entries
            RETURN c {.*} AS col, work_entries
            ORDER BY
              CASE c.type
                WHEN 'major_works' THEN 0
                WHEN 'minor_works' THEN 1
                WHEN 'series' THEN 2
                ELSE 3
              END ASC, c.name ASC
            """,
            id=author_id,
        )
        return [dict(r) for r in records]

    async def get_uncollected_works(self, author_id: str) -> list[dict]:
        """Return works by this author not in any of the author's collections."""
        records = await self._run(
            """
            MATCH (a:Author {id: $id})-[:WROTE]->(w:Work)
            WHERE NOT (w)-[:IN_COLLECTION]->(:Collection {author_id: $id})
            WITH w, w.title AS sort_title
            OPTIONAL MATCH (w)-[:BELONGS_TO]->(st:Stream)
            OPTIONAL MATCH (w)-[r:IN_COLLECTION]->(oc:Collection)
            WITH w, sort_title,
                 collect(DISTINCT st.id) AS stream_ids,
                 collect(DISTINCT {id: oc.id, name: oc.name, type: oc.type, order: r.order}) AS cols
            RETURN w {.*} AS work, stream_ids, cols
            ORDER BY sort_title
            """,
            id=author_id,
        )
        return [dict(r) for r in records]

    @staticmethod
    def _to_author(a: dict) -> Author:
        return Author(
            id=a.get("id", ""),
            name=a.get("name", ""),
            birth_year=a.get("birth_year"),
            death_year=a.get("death_year"),
            nationality=a.get("nationality"),
            primary_language=a.get("primary_language"),
            openlibrary_id=a.get("openlibrary_id"),
        )
```

**Why some methods return `dict` instead of domain models:**
The `get_author` detail view is complex — it combines stats, collections with their works, and uncollected works into a single `AuthorResponse` with computed fields. The repository returns the raw data; the service assembles it. Forcing the repository to return a fully-assembled domain model would require the repository to know about API response shapes, which violates the layer boundary.

#### `repositories/collections.py`

```python
"""Collection repository — CRUD and membership queries."""
from __future__ import annotations

from bildung.models.domain import Collection
from bildung.repositories.base import NeoRepository


class CollectionRepository(NeoRepository):

    async def list(
        self,
        author_id: str | None = None,
        type_: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Return collections with work_count and read_count."""
        records = await self._run(
            """
            MATCH (c:Collection)
            WHERE ($author_id IS NULL OR c.author_id = $author_id)
              AND ($type IS NULL OR c.type = $type)
            OPTIONAL MATCH (w:Work)-[:IN_COLLECTION]->(c)
            WITH c,
                 count(w) AS work_count,
                 sum(CASE WHEN w.status = 'read' THEN 1 ELSE 0 END) AS read_count
            RETURN c {.*} AS col, work_count, read_count
            ORDER BY c.type ASC, c.name ASC
            SKIP $offset LIMIT $limit
            """,
            author_id=author_id,
            type=type_,
            offset=offset,
            limit=limit,
        )
        return [dict(r) for r in records]

    async def get(self, coll_id: str) -> Collection | None:
        record = await self._run_single(
            "MATCH (c:Collection {id: $id}) RETURN c {.*} AS col",
            id=coll_id,
        )
        if not record:
            return None
        c = record["col"]
        return Collection(
            id=c.get("id", ""),
            name=c.get("name", ""),
            description=c.get("description"),
            type=c.get("type", "anthology"),
            author_id=c.get("author_id"),
        )

    async def get_with_works(self, coll_id: str) -> dict | None:
        """Return collection node + ordered works with authors and streams.

        Returns raw data for the service to map into domain/API models.
        """
        col_record = await self._run_single(
            "MATCH (c:Collection {id: $id}) RETURN c {.*} AS col",
            id=coll_id,
        )
        if not col_record:
            return None

        work_records = await self._run(
            """
            MATCH (w:Work)-[r:IN_COLLECTION]->(c:Collection {id: $id})
            WITH w, coalesce(r.order, 9999) AS sort_order, r.order AS ord
            OPTIONAL MATCH (a:Author)-[:WROTE]->(w)
            OPTIONAL MATCH (w)-[:BELONGS_TO]->(st:Stream)
            WITH w, sort_order, ord,
                 collect(DISTINCT {id: a.id, name: a.name}) AS authors,
                 collect(DISTINCT st.id) AS stream_ids
            RETURN w {.*} AS work, ord AS position, authors, stream_ids
            ORDER BY sort_order ASC, w.title ASC
            """,
            id=coll_id,
        )
        return {
            "col": col_record["col"],
            "works": [dict(r) for r in work_records],
        }

    async def create(
        self, coll_id: str, name: str, description: str | None,
        type_: str, author_id: str | None,
    ) -> Collection:
        async with self._driver.session() as session:
            await session.run(
                """
                MERGE (c:Collection {id: $id})
                ON CREATE SET c.name = $name, c.description = $description,
                              c.type = $type, c.author_id = $author_id
                """,
                id=coll_id, name=name, description=description,
                type=type_, author_id=author_id,
            )
        return Collection(
            id=coll_id, name=name, description=description,
            type=type_, author_id=author_id,
        )

    async def update(self, coll_id: str, updates: dict) -> bool:
        record = await self._run_single(
            "MATCH (c:Collection {id: $id}) SET c += $updates RETURN count(c) AS n",
            id=coll_id, updates=updates,
        )
        return bool(record and record["n"] > 0)

    async def delete(self, coll_id: str) -> bool:
        record = await self._run_single(
            "MATCH (c:Collection {id: $id}) DETACH DELETE c RETURN count(c) AS n",
            id=coll_id,
        )
        return bool(record and record["n"] > 0)

    async def add_work(self, work_id: str, coll_id: str, order: int | None) -> bool:
        record = await self._run_single(
            """
            MATCH (w:Work {id: $work_id})
            MATCH (c:Collection {id: $coll_id})
            MERGE (w)-[r:IN_COLLECTION]->(c)
            SET r.order = $order
            RETURN count(r) AS n
            """,
            work_id=work_id, coll_id=coll_id, order=order,
        )
        return bool(record and record["n"] > 0)

    async def remove_work(self, work_id: str, coll_id: str) -> bool:
        record = await self._run_single(
            """
            MATCH (w:Work {id: $work_id})-[r:IN_COLLECTION]->(c:Collection {id: $coll_id})
            DELETE r RETURN count(r) AS n
            """,
            work_id=work_id, coll_id=coll_id,
        )
        return bool(record and record["n"] > 0)

    async def add_to_stream(self, coll_id: str, stream_id: str, order: int | None) -> bool:
        record = await self._run_single(
            """
            MATCH (c:Collection {id: $coll_id})
            MATCH (s:Stream {id: $stream_id})
            MERGE (c)-[r:IN_STREAM]->(s)
            SET r.order = $order
            RETURN count(r) AS n
            """,
            coll_id=coll_id, stream_id=stream_id, order=order,
        )
        return bool(record and record["n"] > 0)

    async def remove_from_stream(self, coll_id: str, stream_id: str) -> bool:
        record = await self._run_single(
            """
            MATCH (c:Collection {id: $coll_id})-[r:IN_STREAM]->(s:Stream {id: $stream_id})
            DELETE r RETURN count(r) AS n
            """,
            coll_id=coll_id, stream_id=stream_id,
        )
        return bool(record and record["n"] > 0)
```

#### `repositories/streams.py`

```python
"""Stream repository — CRUD, work assignment, detail with collections."""
from __future__ import annotations

from bildung.models.domain import Stream
from bildung.repositories.base import NeoRepository


class StreamRepository(NeoRepository):

    async def list(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Return streams with work and collection counts."""
        records = await self._run(
            """
            MATCH (s:Stream)
            OPTIONAL MATCH (w:Work)-[:BELONGS_TO]->(s)
            OPTIONAL MATCH (c:Collection)-[:IN_STREAM]->(s)
            WITH s,
                 count(DISTINCT w) AS direct_works,
                 count(DISTINCT c) AS coll_count
            OPTIONAL MATCH (w2:Work)-[:IN_COLLECTION]->(c2:Collection)-[:IN_STREAM]->(s)
            WITH s, direct_works, coll_count, count(DISTINCT w2) AS coll_works
            RETURN s {.*} AS stream,
                   direct_works + coll_works AS work_count,
                   coll_count AS collection_count
            ORDER BY s.name
            SKIP $offset LIMIT $limit
            """,
            offset=offset,
            limit=limit,
        )
        return [dict(r) for r in records]

    async def get(self, stream_id: str) -> Stream | None:
        record = await self._run_single(
            "MATCH (s:Stream {id: $id}) RETURN s {.*} AS stream",
            id=stream_id,
        )
        if not record:
            return None
        s = record["stream"]
        return Stream(
            id=s.get("id", ""),
            name=s.get("name", ""),
            description=s.get("description"),
            color=s.get("color"),
            created_at=s.get("created_at", ""),
        )

    async def get_collections_for_stream(self, stream_id: str) -> list[dict]:
        """Return collections in this stream, ordered by type and sort order."""
        records = await self._run(
            """
            MATCH (c:Collection)-[r:IN_STREAM]->(s:Stream {id: $id})
            WITH c, coalesce(r.order, 9999) AS sort_ord
            ORDER BY
              CASE c.type
                WHEN 'major_works' THEN 0
                WHEN 'minor_works' THEN 1
                WHEN 'series' THEN 2
                ELSE 3
              END ASC, sort_ord ASC, c.name ASC
            RETURN c {.*} AS col
            """,
            id=stream_id,
        )
        return [dict(r) for r in records]

    async def get_works_for_collection(self, coll_id: str) -> list[dict]:
        """Return works in a collection with authors and stream IDs."""
        records = await self._run(
            """
            MATCH (w:Work)-[r:IN_COLLECTION]->(c:Collection {id: $cid})
            WITH w, coalesce(r.order, 9999) AS sort_ord, r.order AS ord
            OPTIONAL MATCH (a:Author)-[:WROTE]->(w)
            OPTIONAL MATCH (w)-[:BELONGS_TO]->(st:Stream)
            WITH w, sort_ord, ord,
                 collect(DISTINCT {id: a.id, name: a.name}) AS authors,
                 collect(DISTINCT st.id) AS stream_ids
            RETURN w {.*} AS work, ord AS position, authors, stream_ids
            ORDER BY sort_ord ASC, w.title ASC
            """,
            cid=coll_id,
        )
        return [dict(r) for r in records]

    async def get_direct_works(self, stream_id: str) -> list[dict]:
        """Return works directly assigned to this stream (not via collection)."""
        records = await self._run(
            """
            MATCH (w:Work)-[r:BELONGS_TO]->(s:Stream {id: $id})
            WITH w, r.position AS position
            OPTIONAL MATCH (a:Author)-[:WROTE]->(w)
            WITH w, position, collect({id: a.id, name: a.name}) AS authors
            RETURN w {.*} AS work, position, authors
            ORDER BY coalesce(position, 9999) ASC, w.title ASC
            """,
            id=stream_id,
        )
        return [dict(r) for r in records]

    async def create(
        self, stream_id: str, name: str, description: str | None,
        color: str | None, created_at: str,
    ) -> Stream:
        async with self._driver.session() as session:
            await session.run(
                """
                CREATE (s:Stream {id: $id, name: $name, description: $description,
                                  color: $color, created_at: $created_at})
                """,
                id=stream_id, name=name, description=description,
                color=color, created_at=created_at,
            )
        return Stream(
            id=stream_id, name=name, description=description,
            color=color, created_at=created_at,
        )

    async def update(self, stream_id: str, updates: dict) -> bool:
        async with self._driver.session() as session:
            await session.run(
                "MATCH (s:Stream {id: $id}) SET s += $updates",
                id=stream_id, updates=updates,
            )
        return True

    async def delete(self, stream_id: str) -> bool:
        record = await self._run_single(
            """
            MATCH (s:Stream {id: $id})
            OPTIONAL MATCH ()-[r1:BELONGS_TO]->(s)
            OPTIONAL MATCH ()-[r2:IN_STREAM]->(s)
            DELETE r1, r2, s
            RETURN count(s) AS deleted
            """,
            id=stream_id,
        )
        return bool(record and record["deleted"] > 0)

    async def assign_work(self, work_id: str, stream_id: str, position: int | None) -> bool:
        record = await self._run_single(
            """
            MATCH (w:Work {id: $work_id})
            MATCH (s:Stream {id: $stream_id})
            MERGE (w)-[r:BELONGS_TO]->(s)
            ON CREATE SET r.position = $position
            RETURN count(r) AS linked
            """,
            work_id=work_id, stream_id=stream_id, position=position,
        )
        return bool(record and record["linked"] > 0)

    async def remove_work(self, work_id: str, stream_id: str) -> bool:
        record = await self._run_single(
            """
            MATCH (w:Work {id: $work_id})-[r:BELONGS_TO]->(s:Stream {id: $stream_id})
            DELETE r RETURN count(r) AS removed
            """,
            work_id=work_id, stream_id=stream_id,
        )
        return bool(record and record["removed"] > 0)
```

#### `repositories/series.py`

```python
"""Series repository — CRUD and work membership."""
from __future__ import annotations

from bildung.models.domain import Series
from bildung.repositories.base import NeoRepository


class SeriesRepository(NeoRepository):

    async def list(self, limit: int = 50, offset: int = 0) -> list[dict]:
        records = await self._run(
            """
            MATCH (s:Series)
            OPTIONAL MATCH (w:Work)-[:PART_OF]->(s)
            WITH s,
                 count(w)                                           AS work_count,
                 sum(CASE WHEN w.status = 'read' THEN 1 ELSE 0 END) AS read_count
            RETURN s {.*} AS series, work_count, read_count
            ORDER BY s.name
            SKIP $offset LIMIT $limit
            """,
            offset=offset,
            limit=limit,
        )
        return [dict(r) for r in records]

    async def get(self, series_id: str) -> Series | None:
        record = await self._run_single(
            "MATCH (s:Series {id: $id}) RETURN s {.*} AS series",
            id=series_id,
        )
        if not record:
            return None
        s = record["series"]
        return Series(
            id=s.get("id", ""),
            name=s.get("name", ""),
            description=s.get("description"),
        )

    async def get_with_works(self, series_id: str) -> dict | None:
        """Return series node + ordered works for the detail view."""
        s_record = await self._run_single(
            "MATCH (s:Series {id: $id}) RETURN s {.*} AS series",
            id=series_id,
        )
        if not s_record:
            return None

        work_records = await self._run(
            """
            MATCH (w:Work)-[r:PART_OF]->(s:Series {id: $id})
            WITH w, coalesce(r.order, 9999) AS sort_order, r.order AS position
            OPTIONAL MATCH (a:Author)-[:WROTE]->(w)
            OPTIONAL MATCH (w)-[:BELONGS_TO]->(st:Stream)
            WITH w, sort_order, position,
                 collect(DISTINCT {id: a.id, name: a.name}) AS authors,
                 collect(DISTINCT st.id)                    AS stream_ids
            RETURN w {.*} AS work, position, authors, stream_ids
            ORDER BY sort_order ASC, w.title ASC
            """,
            id=series_id,
        )
        return {
            "series": s_record["series"],
            "works": [dict(r) for r in work_records],
        }

    async def create(self, series_id: str, name: str, description: str | None) -> Series:
        async with self._driver.session() as session:
            await session.run(
                """
                MERGE (s:Series {id: $id})
                ON CREATE SET s.name = $name, s.description = $description
                """,
                id=series_id, name=name, description=description,
            )
        return Series(id=series_id, name=name, description=description)

    async def update(self, series_id: str, updates: dict) -> bool:
        record = await self._run_single(
            "MATCH (s:Series {id: $id}) SET s += $updates RETURN count(s) AS n",
            id=series_id, updates=updates,
        )
        return bool(record and record["n"] > 0)

    async def delete(self, series_id: str) -> bool:
        record = await self._run_single(
            "MATCH (s:Series {id: $id}) DETACH DELETE s RETURN count(s) AS n",
            id=series_id,
        )
        return bool(record and record["n"] > 0)

    async def assign_work(self, work_id: str, series_id: str, order: int | None) -> bool:
        record = await self._run_single(
            """
            MATCH (w:Work {id: $work_id})
            MATCH (s:Series {id: $series_id})
            MERGE (w)-[r:PART_OF]->(s)
            SET r.order = $order
            RETURN count(r) AS n
            """,
            work_id=work_id, series_id=series_id, order=order,
        )
        return bool(record and record["n"] > 0)

    async def remove_work(self, work_id: str, series_id: str) -> bool:
        record = await self._run_single(
            """
            MATCH (w:Work {id: $work_id})-[r:PART_OF]->(s:Series {id: $series_id})
            DELETE r RETURN count(r) AS n
            """,
            work_id=work_id, series_id=series_id,
        )
        return bool(record and record["n"] > 0)
```

### Key Design Decisions (and why)

**1. Repositories return domain models for simple queries, raw dicts for complex aggregations.**
`WorkRepository.get()` returns `Work`. `AuthorRepository.list()` returns `list[dict]` because it includes `total_works`, `read_works`, `major_total`, `major_read` — computed aggregates that don't belong on the domain `Author` model. The service layer uses these dicts to build API response objects with computed fields. Forcing everything into domain models would either bloat the domain model or require multiple queries.

**2. Cypher queries are copied exactly from services, not rewritten.**
The goal is to move queries, not improve them. Same query text, same parameter names. Task 2C will rewrite them for PostgreSQL. Changing queries now introduces risk with zero benefit.

**3. `WorkRepository.create()` takes explicit params, not a request object.**
Repositories don't know about API request schemas. The service unpacks the request and passes individual values. This keeps the repository layer independent of the API layer.

**4. No `EventRepository` in this task.**
The reading event write in `services/works.py` uses SQLAlchemy directly. Creating a PG-based `EventRepository` requires the PostgreSQL session management pattern, which is out of scope for this task. Task 1C will create it when it rewires the services.

**5. Stream detail assembly stays in the service layer.**
`get_stream` detail involves N+1 queries (stream → collections → works per collection → direct works). The repository provides the individual queries; the service orchestrates the assembly. The repository doesn't combine them because that would embed presentation logic.

### DO NOT

1. **Do not modify any service files.** The repositories exist alongside the current services. Task 1C wires them together. If you import a repository in a service now, you're mixing old and new patterns in one file.

2. **Do not modify `dependencies.py`.** Repository factory functions go there in Task 1C, not here.

3. **Do not create an `EventRepository`.** The reading event write uses `AsyncSession` (SQLAlchemy), not `AsyncDriver` (Neo4j). It doesn't fit `NeoRepository`. Task 1C will handle this.

4. **Do not add a `StatsRepository`.** Stats queries were just moved to `services/stats.py` in Task 0B. They'll move to a repository in Task 2C when they become PostgreSQL queries.

5. **Do not add methods that don't correspond to an existing service function.** No `search()`, `count()`, `exists()`, `bulk_create()`. If the current services don't do it, the repository doesn't need it.

6. **Do not rewrite Cypher queries.** Copy them verbatim from the service files. Same parameter names, same return shapes. Optimizing queries changes behavior and introduces bugs.

7. **Do not create abstract base classes or generic repository interfaces.** No `Repository[T]`, no `CrudRepository`, no `ReadableRepository`. Five concrete classes are clearer than a type hierarchy.

8. **Do not add logging to repository methods.** The current service functions log; the repositories just run queries. Logging lives at the service layer.

### Acceptance Criteria

- [ ] `repositories/__init__.py` exists (empty)
- [ ] `repositories/base.py` exists with `NeoRepository` class
- [ ] `repositories/works.py` exists with `WorkRepository` class
- [ ] `repositories/authors.py` exists with `AuthorRepository` class
- [ ] `repositories/collections.py` exists with `CollectionRepository` class
- [ ] `repositories/streams.py` exists with `StreamRepository` class
- [ ] `repositories/series.py` exists with `SeriesRepository` class
- [ ] All repository classes extend `NeoRepository`
- [ ] `WorkRepository._to_work()` returns domain `Work`, not `WorkResponse`
- [ ] No imports from `models/api.py` in any repository file
- [ ] No imports from `services/`, `routers/`, or `dependencies`
- [ ] Every Cypher query that exists in services has a corresponding repository method
- [ ] No service files were modified
- [ ] Backend still starts: `uv run uvicorn src.bildung.main:app --reload`
- [ ] Repositories are importable: `uv run python -c "from bildung.repositories.works import WorkRepository; print('OK')"`

### Verification

```bash
# All repository files exist
ls -la src/bildung/repositories/

# Correct class count
grep -c "class.*NeoRepository\|class.*Repository.*NeoRepository" src/bildung/repositories/*.py
# Expected: base.py:1, works.py:1, authors.py:1, collections.py:1, streams.py:1, series.py:1

# No API model imports in repositories
grep -rn "from bildung.models.api" src/bildung/repositories/
# Expected: 0 results

# No service/router imports
grep -rn "from bildung.services\|from bildung.routers\|from bildung.dependencies" src/bildung/repositories/
# Expected: 0 results

# Importable
uv run python -c "
from bildung.repositories.works import WorkRepository
from bildung.repositories.authors import AuthorRepository
from bildung.repositories.collections import CollectionRepository
from bildung.repositories.streams import StreamRepository
from bildung.repositories.series import SeriesRepository
print('All repositories importable')
"

# Services unchanged
git diff src/bildung/services/
# Expected: no changes

# Backend still starts
uv run uvicorn src.bildung.main:app --reload &
sleep 3
curl -s http://localhost:8000/health
# Expected: {"status":"ok"}
```

---

## Handoff

### Decisions Made
- All five repository classes follow spec exactly. `WorkRepository._to_work()` returns domain `Work` (not `WorkResponse`). `AuthorRepository.list()` and `get_with_stats()` return raw `dict` for service-side assembly.
- `repositories/__init__.py` is empty — no barrel exports, import from specific modules.
- Cypher queries copied verbatim from services; no rewrites.

### Harder Than Expected
- Nothing unexpected. The spec code was directly transcribable.

### Watch Out (for Task 1C)
- `WorkRepository.get()` fetches `stream_ids` in the Cypher but `_to_work()` ignores them — the domain `Work` model has no `stream_ids` field. Task 1C's service layer needs to read `stream_ids` directly from the Neo4j record when building `WorkResponse`.
- `WorkRepository.create()` calls `self.get(work_id)` at the end which does a second round-trip but doesn't return `stream_ids` either. The service can call `get_work` on the driver directly (current code) or accept this as a known limitation for new works (stream_ids will be `[]` on create).
- `CollectionRepository.update()` passes `updates` as a kwarg to `_run_single()`, but `_run_single` passes params as `**params` which becomes a nested dict under key `updates`. This is consistent with how the base class works — Neo4j receives `$updates` as the dict.
- `StreamRepository.delete()` returns `count(s)` after deleting — Neo4j `count()` on a deleted node returns 0, so `deleted > 0` will always be `False`. The correct pattern is to check existence first or use `RETURN 1`. Task 1C should fix this if delete confirmation matters.

### Deviations from Spec
- None. All files exist, all classes extend `NeoRepository`, no API model imports, services untouched.
