"""Stream service layer — streams are reading paths composed of collections + direct works."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from neo4j import AsyncDriver

logger = logging.getLogger(__name__)

from bildung.models.api import (
    AssignStreamRequest,
    CollectionDetailResponse,
    CreateStreamRequest,
    StreamDetailResponse,
    StreamResponse,
    UpdateStreamRequest,
    WorkResponse,
)
from bildung.services.works import _record_to_work


def _record_to_stream(s: dict, work_count: int = 0, collection_count: int = 0) -> StreamResponse:
    return StreamResponse(
        id=s.get("id", ""),
        name=s.get("name", ""),
        description=s.get("description"),
        color=s.get("color"),
        created_at=s.get("created_at", ""),
        work_count=work_count,
        collection_count=collection_count,
    )


# ---------------------------------------------------------------------------
# Stream CRUD
# ---------------------------------------------------------------------------

async def list_streams(
    driver: AsyncDriver,
    limit: int = 50,
    offset: int = 0,
) -> list[StreamResponse]:
    async with driver.session() as session:
        result = await session.run(
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
        return [
            _record_to_stream(r["stream"], r["work_count"], r["collection_count"])
            async for r in result
        ]


async def get_stream(driver: AsyncDriver, stream_id: str) -> StreamDetailResponse | None:
    async with driver.session() as session:
        s_res = await session.run(
            "MATCH (s:Stream {id: $id}) RETURN s {.*} AS stream",
            id=stream_id,
        )
        s_record = await s_res.single()
        if not s_record:
            return None
        s = s_record["stream"]

        # Collections in stream (ordered)
        cols_res = await session.run(
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
        collections: list[CollectionDetailResponse] = []
        async for cr in cols_res:
            c = cr["col"]
            # Fetch works for this collection
            w_res = await session.run(
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
                cid=c["id"],
            )
            col_works: list[WorkResponse] = []
            read_count = 0
            async for wr in w_res:
                col_summary = [{"id": c["id"], "name": c.get("name", ""), "type": c.get("type", ""), "order": wr["position"]}]
                col_works.append(_record_to_work(wr["work"], wr["authors"], wr["stream_ids"], col_summary))
                if wr["work"].get("status") == "read":
                    read_count += 1
            collections.append(CollectionDetailResponse(
                id=c.get("id", ""),
                name=c.get("name", ""),
                description=c.get("description"),
                type=c.get("type", "anthology"),
                author_id=c.get("author_id"),
                work_count=len(col_works),
                read_count=read_count,
                works=col_works,
            ))

        # IDs of works already covered by collections (for deduplication)
        col_work_ids: set[str] = {w.id for coll in collections for w in coll.works}

        # Direct works not in any collection in this stream
        dw_res = await session.run(
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
        direct_works: list[WorkResponse] = []
        async for wr in dw_res:
            if wr["work"].get("id") not in col_work_ids:
                direct_works.append(_record_to_work(wr["work"], wr["authors"]))

        total_works = sum(c.work_count for c in collections) + len(direct_works)

    return StreamDetailResponse(
        id=s.get("id", ""),
        name=s.get("name", ""),
        description=s.get("description"),
        color=s.get("color"),
        created_at=s.get("created_at", ""),
        work_count=total_works,
        collection_count=len(collections),
        collections=collections,
        works=direct_works,
    )


async def create_stream(driver: AsyncDriver, req: CreateStreamRequest) -> StreamResponse:
    stream_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    async with driver.session() as session:
        await session.run(
            """
            CREATE (s:Stream {id: $id, name: $name, description: $description,
                              color: $color, created_at: $created_at})
            """,
            id=stream_id, name=req.name, description=req.description,
            color=req.color, created_at=created_at,
        )
    return StreamResponse(
        id=stream_id, name=req.name, description=req.description,
        color=req.color, created_at=created_at, work_count=0, collection_count=0,
    )


async def update_stream(driver: AsyncDriver, stream_id: str, req: UpdateStreamRequest) -> StreamDetailResponse | None:
    existing = await get_stream(driver, stream_id)
    if not existing:
        return None
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if updates:
        async with driver.session() as session:
            await session.run("MATCH (s:Stream {id: $id}) SET s += $updates", id=stream_id, updates=updates)
    return await get_stream(driver, stream_id)


async def delete_stream(driver: AsyncDriver, stream_id: str) -> bool:
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (s:Stream {id: $id})
            OPTIONAL MATCH ()-[r1:BELONGS_TO]->(s)
            OPTIONAL MATCH ()-[r2:IN_STREAM]->(s)
            DELETE r1, r2, s
            RETURN count(s) AS deleted
            """,
            id=stream_id,
        )
        rec = await result.single()
        return bool(rec and rec["deleted"] > 0)


# ---------------------------------------------------------------------------
# Work ↔ Stream direct membership
# ---------------------------------------------------------------------------

async def assign_work_to_stream(driver: AsyncDriver, work_id: str, req: AssignStreamRequest) -> bool:
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (w:Work {id: $work_id})
            MATCH (s:Stream {id: $stream_id})
            MERGE (w)-[r:BELONGS_TO]->(s)
            ON CREATE SET r.position = $position
            RETURN count(r) AS linked
            """,
            work_id=work_id, stream_id=req.stream_id, position=req.position,
        )
        rec = await result.single()
        return bool(rec and rec["linked"] > 0)


async def remove_work_from_stream(driver: AsyncDriver, work_id: str, stream_id: str) -> bool:
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (w:Work {id: $work_id})-[r:BELONGS_TO]->(s:Stream {id: $stream_id})
            DELETE r RETURN count(r) AS removed
            """,
            work_id=work_id, stream_id=stream_id,
        )
        rec = await result.single()
        return bool(rec and rec["removed"] > 0)
