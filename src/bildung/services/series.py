"""Series service — CRUD and work membership."""
from __future__ import annotations

import logging

from neo4j import AsyncDriver

from bildung.ids import series_id as _series_id
from bildung.models.api import (
    CreateSeriesRequest,
    SeriesDetailResponse,
    SeriesMembershipRequest,
    SeriesResponse,
    UpdateSeriesRequest,
)
from bildung.services.works import _record_to_work

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_series_id(name: str) -> str:
    return _series_id(name)


def _build_series(s: dict, work_count: int = 0, read_count: int = 0) -> SeriesResponse:
    return SeriesResponse(
        id=s.get("id", ""),
        name=s.get("name", ""),
        description=s.get("description"),
        work_count=work_count,
        read_count=read_count,
    )


# ---------------------------------------------------------------------------
# Series CRUD
# ---------------------------------------------------------------------------

async def list_series(
    driver: AsyncDriver,
    limit: int = 50,
    offset: int = 0,
) -> list[SeriesResponse]:
    async with driver.session() as session:
        result = await session.run(
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
        return [
            _build_series(r["series"], r["work_count"], r["read_count"])
            async for r in result
        ]


async def get_series(
    driver: AsyncDriver, series_id: str
) -> SeriesDetailResponse | None:
    async with driver.session() as session:
        # Series node
        s_res = await session.run(
            "MATCH (s:Series {id: $id}) RETURN s {.*} AS series",
            id=series_id,
        )
        s_record = await s_res.single()
        if not s_record:
            return None
        s = s_record["series"]

        # Works ordered by position — pull order before aggregating
        w_res = await session.run(
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
        works = []
        read_count = 0
        async for wr in w_res:
            work = _record_to_work(
                wr["work"], wr["authors"], wr["stream_ids"],
                [{"id": series_id, "name": s.get("name", ""), "order": wr["position"]}],
            )
            works.append(work)
            if wr["work"].get("status") == "read":
                read_count += 1

        return SeriesDetailResponse(
            id=s.get("id", ""),
            name=s.get("name", ""),
            description=s.get("description"),
            work_count=len(works),
            read_count=read_count,
            works=works,
        )


async def create_series(
    driver: AsyncDriver, req: CreateSeriesRequest
) -> SeriesResponse:
    series_id = _new_series_id(req.name)
    async with driver.session() as session:
        await session.run(
            """
            MERGE (s:Series {id: $id})
            ON CREATE SET s.name = $name, s.description = $description
            """,
            id=series_id,
            name=req.name,
            description=req.description,
        )
    return SeriesResponse(
        id=series_id,
        name=req.name,
        description=req.description,
        work_count=0,
        read_count=0,
    )


async def update_series(
    driver: AsyncDriver, series_id: str, req: UpdateSeriesRequest
) -> SeriesDetailResponse | None:
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if updates:
        async with driver.session() as session:
            res = await session.run(
                "MATCH (s:Series {id: $id}) SET s += $updates RETURN count(s) AS n",
                id=series_id,
                updates=updates,
            )
            rec = await res.single()
            if not rec or rec["n"] == 0:
                return None
    return await get_series(driver, series_id)


async def delete_series(driver: AsyncDriver, series_id: str) -> bool:
    async with driver.session() as session:
        res = await session.run(
            """
            MATCH (s:Series {id: $id})
            DETACH DELETE s
            RETURN count(s) AS n
            """,
            id=series_id,
        )
        rec = await res.single()
        return bool(rec and rec["n"] > 0)


# ---------------------------------------------------------------------------
# Series membership
# ---------------------------------------------------------------------------

async def assign_work_to_series(
    driver: AsyncDriver,
    work_id: str,
    series_id: str,
    req: SeriesMembershipRequest,
) -> bool:
    async with driver.session() as session:
        res = await session.run(
            """
            MATCH (w:Work {id: $work_id})
            MATCH (s:Series {id: $series_id})
            MERGE (w)-[r:PART_OF]->(s)
            SET r.order = $order
            RETURN count(r) AS n
            """,
            work_id=work_id,
            series_id=series_id,
            order=req.order,
        )
        rec = await res.single()
        return bool(rec and rec["n"] > 0)


async def remove_work_from_series(
    driver: AsyncDriver, work_id: str, series_id: str
) -> bool:
    async with driver.session() as session:
        res = await session.run(
            """
            MATCH (w:Work {id: $work_id})-[r:PART_OF]->(s:Series {id: $series_id})
            DELETE r
            RETURN count(r) AS n
            """,
            work_id=work_id,
            series_id=series_id,
        )
        rec = await res.single()
        return bool(rec and rec["n"] > 0)
