"""Work and Author service layer.

All Cypher queries live here — routers stay thin.
Follows the pattern from finalysis: service functions receive
driver/session as arguments (never call dependencies directly).
"""
from __future__ import annotations

import logging
import uuid  # still needed for uuid.uuid4() in _record_reading_event
from datetime import date

from neo4j import AsyncDriver
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bildung.ids import author_id as _author_id
from bildung.ids import work_id as _work_id
from bildung.models.api import (
    AuthorSummary,
    CollectionSummary,
    CreateWorkRequest,
    UpdateWorkRequest,
    WorkResponse,
)
from bildung.models.postgres import ReadingEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_work_id(title: str, author_name: str) -> str:
    """Deterministic UUID matching the ingestion pipeline's scheme."""
    return _work_id(title, author_name)


def _new_author_id(name: str) -> str:
    return _author_id(name)


def _record_to_work(
    work_map: dict,
    authors_list: list[dict],
    stream_ids: list[str] | None = None,
    collections_list: list[dict] | None = None,
) -> WorkResponse:
    authors = [
        AuthorSummary(id=a["id"] or "", name=a["name"] or "")
        for a in authors_list
        if a.get("name")
    ]
    collections = [
        CollectionSummary(
            id=c["id"] or "",
            name=c["name"] or "",
            type=c.get("type", "anthology"),
            order=c.get("order"),
        )
        for c in (collections_list or [])
        if c.get("id")
    ]
    return WorkResponse(
        id=work_map.get("id", ""),
        title=work_map.get("title", ""),
        status=work_map.get("status", ""),
        language_read_in=work_map.get("language_read_in"),
        date_read=work_map.get("date_read"),
        density_rating=work_map.get("density_rating"),
        source_type=work_map.get("source_type", "fiction"),
        personal_note=work_map.get("personal_note"),
        edition_note=work_map.get("edition_note"),
        significance=work_map.get("significance"),
        authors=authors,
        stream_ids=stream_ids or [],
        collections=collections,
    )


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

async def list_works(
    driver: AsyncDriver,
    status: str | None = None,
    author: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[WorkResponse]:
    async with driver.session() as session:
        result = await session.run(
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
        return [
            _record_to_work(r["work"], r["authors"])
            async for r in result
        ]


async def get_work(driver: AsyncDriver, work_id: str) -> WorkResponse | None:
    async with driver.session() as session:
        result = await session.run(
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
        record = await result.single()
        if not record:
            return None
        return _record_to_work(
            record["work"], record["authors"],
            record["stream_ids"], record["collections"],
        )


async def create_work(
    driver: AsyncDriver,
    pg_session: AsyncSession,
    req: CreateWorkRequest,
) -> WorkResponse:
    wid = _new_work_id(req.title, req.author)
    aid = _new_author_id(req.author)

    async with driver.session() as session:
        async with await session.begin_transaction() as tx:
            # Ensure author exists
            exists = await tx.run(
                "MATCH (a:Author {id: $id}) RETURN count(a) AS n", id=aid
            )
            rec = await exists.single()
            if rec["n"] == 0:
                await tx.run(
                    "CREATE (a:Author {id: $id, name: $name})",
                    id=aid,
                    name=req.author,
                )

            # Create or retrieve work
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
                id=wid,
                title=req.title,
                status=req.status,
                language_read_in=req.language_read_in,
                date_read=req.date_read,
                density_rating=req.density_rating,
                source_type=req.source_type,
                personal_note=req.personal_note,
                significance=req.significance,
            )

            # Link author → work (idempotent)
            await tx.run(
                """
                MATCH (a:Author {id: $aid})
                MATCH (w:Work {id: $wid})
                MERGE (a)-[:WROTE]->(w)
                """,
                aid=aid,
                wid=wid,
            )

    logger.info("create_work: id=%s title=%r status=%s", wid, req.title, req.status)

    if req.status == "read":
        await _record_reading_event(pg_session, wid, "finished", req.date_read)

    return await get_work(driver, wid)  # type: ignore[return-value]


async def update_work(
    driver: AsyncDriver,
    pg_session: AsyncSession,
    work_id: str,
    req: UpdateWorkRequest,
) -> WorkResponse | None:
    # Fetch current work to detect status transition
    current = await get_work(driver, work_id)
    if not current:
        return None

    # Build update map from only the provided (non-None) fields
    updates: dict = {
        k: v for k, v in req.model_dump().items() if v is not None
    }
    if not updates:
        return current

    async with driver.session() as session:
        await session.run(
            "MATCH (w:Work {id: $id}) SET w += $updates",
            id=work_id,
            updates=updates,
        )

    logger.info("update_work: id=%s fields=%s", work_id, list(updates.keys()))

    # Side-effect: log reading event when status transitions to "read"
    if req.status == "read" and current.status != "read":
        event_date = req.date_read or current.date_read or str(date.today())
        await _record_reading_event(pg_session, work_id, "finished", event_date)

    return await get_work(driver, work_id)


# ---------------------------------------------------------------------------
# PostgreSQL side-effects
# ---------------------------------------------------------------------------

async def _record_reading_event(
    pg_session: AsyncSession,
    work_id: str,
    event_type: str,
    event_date: str | None,
) -> None:
    parsed_date = _parse_date(event_date)
    stmt = insert(ReadingEvent).values(
        id=uuid.uuid4(),
        work_id=uuid.UUID(work_id),
        event_type=event_type,
        event_date=parsed_date,
    )
    await pg_session.execute(stmt)
    await pg_session.commit()


def _parse_date(raw: str | None) -> date:
    """Best-effort: '2024', '2024-03', '2024-03-15' → date. Falls back to today."""
    if not raw:
        return date.today()
    try:
        if len(raw) == 4:
            return date(int(raw), 12, 31)
        if len(raw) == 7:
            y, m = raw.split("-")
            return date(int(y), int(m), 1)
        return date.fromisoformat(raw)
    except (ValueError, AttributeError):
        return date.today()
