"""Collection service — the universal grouping unit (major/minor canon, series, anthology)."""
from __future__ import annotations

import logging

from neo4j import AsyncDriver

from bildung.ids import collection_id
from bildung.models.api import (
    CollectionDetailResponse,
    CollectionMembershipRequest,
    CollectionResponse,
    CollectionStreamRequest,
    CreateCollectionRequest,
    UpdateCollectionRequest,
)
from bildung.services.works import _record_to_work

logger = logging.getLogger(__name__)


def _build_response(c: dict, work_count: int = 0, read_count: int = 0) -> CollectionResponse:
    return CollectionResponse(
        id=c.get("id", ""),
        name=c.get("name", ""),
        description=c.get("description"),
        type=c.get("type", "anthology"),
        author_id=c.get("author_id"),
        work_count=work_count,
        read_count=read_count,
    )


# ---------------------------------------------------------------------------
# Collection CRUD
# ---------------------------------------------------------------------------

async def list_collections(
    driver: AsyncDriver,
    author_id: str | None = None,
    type_: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[CollectionResponse]:
    """All collections, optionally filtered by author or type."""
    async with driver.session() as session:
        result = await session.run(
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
        return [
            _build_response(r["col"], r["work_count"], r["read_count"])
            async for r in result
        ]


async def get_collection(
    driver: AsyncDriver, coll_id: str
) -> CollectionDetailResponse | None:
    async with driver.session() as session:
        c_res = await session.run(
            "MATCH (c:Collection {id: $id}) RETURN c {.*} AS col",
            id=coll_id,
        )
        c_record = await c_res.single()
        if not c_record:
            return None
        c = c_record["col"]

        w_res = await session.run(
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
        works = []
        read_count = 0
        async for wr in w_res:
            col_summary = [{"id": coll_id, "name": c.get("name", ""), "type": c.get("type", ""), "order": wr["position"]}]
            works.append(_record_to_work(wr["work"], wr["authors"], wr["stream_ids"], col_summary))
            if wr["work"].get("status") == "read":
                read_count += 1

        return CollectionDetailResponse(
            id=c.get("id", ""),
            name=c.get("name", ""),
            description=c.get("description"),
            type=c.get("type", "anthology"),
            author_id=c.get("author_id"),
            work_count=len(works),
            read_count=read_count,
            works=works,
        )


async def create_collection(
    driver: AsyncDriver, req: CreateCollectionRequest
) -> CollectionResponse:
    coll_id = collection_id(req.name)
    async with driver.session() as session:
        await session.run(
            """
            MERGE (c:Collection {id: $id})
            ON CREATE SET c.name = $name, c.description = $description,
                          c.type = $type, c.author_id = $author_id
            """,
            id=coll_id,
            name=req.name,
            description=req.description,
            type=req.type,
            author_id=req.author_id,
        )
    logger.info("create_collection: id=%s name=%r type=%s", coll_id, req.name, req.type)
    return CollectionResponse(
        id=coll_id,
        name=req.name,
        description=req.description,
        type=req.type,
        author_id=req.author_id,
        work_count=0,
        read_count=0,
    )


async def update_collection(
    driver: AsyncDriver, coll_id: str, req: UpdateCollectionRequest
) -> CollectionDetailResponse | None:
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if updates:
        async with driver.session() as session:
            res = await session.run(
                "MATCH (c:Collection {id: $id}) SET c += $updates RETURN count(c) AS n",
                id=coll_id, updates=updates,
            )
            rec = await res.single()
            if not rec or rec["n"] == 0:
                return None
    return await get_collection(driver, coll_id)


async def delete_collection(driver: AsyncDriver, coll_id: str) -> bool:
    async with driver.session() as session:
        res = await session.run(
            "MATCH (c:Collection {id: $id}) DETACH DELETE c RETURN count(c) AS n",
            id=coll_id,
        )
        rec = await res.single()
        return bool(rec and rec["n"] > 0)


# ---------------------------------------------------------------------------
# Work membership
# ---------------------------------------------------------------------------

async def add_work_to_collection(
    driver: AsyncDriver,
    work_id: str,
    coll_id: str,
    req: CollectionMembershipRequest,
) -> bool:
    async with driver.session() as session:
        res = await session.run(
            """
            MATCH (w:Work {id: $work_id})
            MATCH (c:Collection {id: $coll_id})
            MERGE (w)-[r:IN_COLLECTION]->(c)
            SET r.order = $order
            RETURN count(r) AS n
            """,
            work_id=work_id, coll_id=coll_id, order=req.order,
        )
        rec = await res.single()
        return bool(rec and rec["n"] > 0)


async def remove_work_from_collection(
    driver: AsyncDriver, work_id: str, coll_id: str
) -> bool:
    async with driver.session() as session:
        res = await session.run(
            """
            MATCH (w:Work {id: $work_id})-[r:IN_COLLECTION]->(c:Collection {id: $coll_id})
            DELETE r RETURN count(r) AS n
            """,
            work_id=work_id, coll_id=coll_id,
        )
        rec = await res.single()
        return bool(rec and rec["n"] > 0)


# ---------------------------------------------------------------------------
# Stream assignment
# ---------------------------------------------------------------------------

async def add_collection_to_stream(
    driver: AsyncDriver,
    coll_id: str,
    stream_id: str,
    req: CollectionStreamRequest,
) -> bool:
    async with driver.session() as session:
        res = await session.run(
            """
            MATCH (c:Collection {id: $coll_id})
            MATCH (s:Stream {id: $stream_id})
            MERGE (c)-[r:IN_STREAM]->(s)
            SET r.order = $order
            RETURN count(r) AS n
            """,
            coll_id=coll_id, stream_id=stream_id, order=req.order,
        )
        rec = await res.single()
        return bool(rec and rec["n"] > 0)


async def remove_collection_from_stream(
    driver: AsyncDriver, coll_id: str, stream_id: str
) -> bool:
    async with driver.session() as session:
        res = await session.run(
            """
            MATCH (c:Collection {id: $coll_id})-[r:IN_STREAM]->(s:Stream {id: $stream_id})
            DELETE r RETURN count(r) AS n
            """,
            coll_id=coll_id, stream_id=stream_id,
        )
        rec = await res.single()
        return bool(rec and rec["n"] > 0)
