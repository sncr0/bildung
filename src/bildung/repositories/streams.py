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
