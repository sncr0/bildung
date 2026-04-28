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
