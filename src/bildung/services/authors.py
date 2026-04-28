"""Author service — list, detail, collections, completion stats."""
from __future__ import annotations

import logging

from neo4j import AsyncDriver

logger = logging.getLogger(__name__)

from bildung.models.api import (
    AuthorResponse,
    CollectionDetailResponse,
    CollectionSummary,
    WorkResponse,
)
from bildung.services.works import _record_to_work


async def list_authors(
    driver: AsyncDriver,
    limit: int = 50,
    offset: int = 0,
) -> list[AuthorResponse]:
    """All authors with work counts and completion stats derived from collections."""
    async with driver.session() as session:
        result = await session.run(
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
        out: list[AuthorResponse] = []
        async for r in result:
            out.append(_build_author_summary(r))
        return out


async def get_author(driver: AsyncDriver, author_id: str) -> AuthorResponse | None:
    """Single author with all collections (each containing their works) + uncollected works."""
    async with driver.session() as session:
        # Stats
        stats_res = await session.run(
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
        stats = await stats_res.single()
        if not stats:
            return None

        a = stats["author"]
        author_summary = [{"id": a.get("id", ""), "name": a.get("name", "")}]

        # All collections owned by this author
        cols_res = await session.run(
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

        collections: list[CollectionDetailResponse] = []
        all_collected_work_ids: set[str] = set()

        async for cr in cols_res:
            c = cr["col"]
            entries = cr["work_entries"]
            works: list[WorkResponse] = []
            read_count = 0
            for entry in entries:
                wm = entry.get("w")
                if not wm:
                    continue
                wid = wm.get("id", "")
                all_collected_work_ids.add(wid)
                col_summary = [{
                    "id": c.get("id", ""),
                    "name": c.get("name", ""),
                    "type": c.get("type", ""),
                    "order": entry.get("ord"),
                }]
                works.append(_record_to_work(wm, author_summary, [], col_summary))
                if wm.get("status") == "read":
                    read_count += 1

            collections.append(CollectionDetailResponse(
                id=c.get("id", ""),
                name=c.get("name", ""),
                description=c.get("description"),
                type=c.get("type", "anthology"),
                author_id=c.get("author_id"),
                work_count=len(works),
                read_count=read_count,
                works=works,
            ))

        # Uncollected works — in library but not in any of this author's collections
        uncollected_res = await session.run(
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
        uncollected: list[WorkResponse] = []
        async for wr in uncollected_res:
            uncollected.append(_record_to_work(wr["work"], author_summary, wr["stream_ids"], wr["cols"]))

        return _build_author_detail(stats, collections, uncollected)


def _build_author_summary(r: dict) -> AuthorResponse:
    a = r["author"]
    total = r["total_works"] or 0
    read = r["read_works"] or 0
    major_total = r["major_total"] or 0
    major_read = r["major_read"] or 0

    if major_total > 0:
        pct = round(major_read / major_total, 4)
    elif total > 0:
        pct = round(read / total, 4)
    else:
        pct = 0.0

    return AuthorResponse(
        id=a.get("id", ""),
        name=a.get("name", ""),
        birth_year=a.get("birth_year"),
        death_year=a.get("death_year"),
        nationality=a.get("nationality"),
        primary_language=a.get("primary_language"),
        total_works=total,
        read_works=read,
        completion_pct=pct,
        collections=[],
        works=[],
    )


def _build_author_detail(
    stats: dict,
    collections: list[CollectionDetailResponse],
    uncollected: list[WorkResponse],
) -> AuthorResponse:
    a = stats["author"]
    total = stats["total_works"] or 0
    read = stats["read_works"] or 0
    major_total = stats["major_total"] or 0
    major_read = stats["major_read"] or 0

    if major_total > 0:
        pct = round(major_read / major_total, 4)
    elif total > 0:
        pct = round(read / total, 4)
    else:
        pct = 0.0

    return AuthorResponse(
        id=a.get("id", ""),
        name=a.get("name", ""),
        birth_year=a.get("birth_year"),
        death_year=a.get("death_year"),
        nationality=a.get("nationality"),
        primary_language=a.get("primary_language"),
        total_works=total,
        read_works=read,
        completion_pct=pct,
        collections=collections,
        works=uncollected,
    )
