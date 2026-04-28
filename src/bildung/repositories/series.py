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
