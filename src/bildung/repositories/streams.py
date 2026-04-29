"""Stream repository — PostgreSQL reads, dual-write (PG + Neo4j)."""
from __future__ import annotations

import logging
import uuid
from datetime import timezone

from neo4j import AsyncDriver
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bildung.models.domain import Stream

logger = logging.getLogger(__name__)


def _fmt_dt(dt) -> str:
    if dt is None:
        return ""
    utc = dt.astimezone(timezone.utc)
    ms = utc.microsecond // 1000
    return utc.strftime(f"%Y-%m-%dT%H:%M:%S.{ms:03d}Z")


class StreamRepository:
    def __init__(self, pg_session: AsyncSession, neo4j_driver: AsyncDriver) -> None:
        self._pg = pg_session
        self._neo = neo4j_driver

    async def list(self, limit: int = 50, offset: int = 0) -> list[dict]:
        result = await self._pg.execute(
            text("""
                SELECT
                    s.id::text, s.name, s.description, s.color, s.created_at,
                    (SELECT count(DISTINCT work_id) FROM work_streams ws WHERE ws.stream_id = s.id) AS direct_works,
                    (SELECT count(DISTINCT collection_id) FROM collection_streams cs WHERE cs.stream_id = s.id) AS coll_count,
                    (SELECT count(DISTINCT wc.work_id)
                     FROM collection_streams cs
                     JOIN work_collections wc ON wc.collection_id = cs.collection_id
                     WHERE cs.stream_id = s.id) AS coll_works
                FROM streams s
                ORDER BY s.name
                LIMIT :limit OFFSET :offset
            """),
            {"limit": limit, "offset": offset},
        )
        rows = result.mappings().all()
        return [
            {
                "stream": {
                    "id": row["id"], "name": row["name"],
                    "description": row["description"], "color": row["color"],
                    "created_at": _fmt_dt(row["created_at"]),
                },
                "work_count": (row["direct_works"] or 0) + (row["coll_works"] or 0),
                "collection_count": row["coll_count"] or 0,
            }
            for row in rows
        ]

    async def get(self, stream_id: str) -> Stream | None:
        result = await self._pg.execute(
            text("SELECT id::text, name, description, color, created_at FROM streams WHERE id = :id::uuid"),
            {"id": stream_id},
        )
        row = result.mappings().first()
        if not row:
            return None
        return Stream(
            id=row["id"], name=row["name"], description=row["description"],
            color=row["color"], created_at=_fmt_dt(row["created_at"]),
        )

    async def get_collections_for_stream(self, stream_id: str) -> list[dict]:
        result = await self._pg.execute(
            text("""
                SELECT
                    c.id::text, c.name, c.description, c.type,
                    c.author_id::text AS author_id, cs."order"
                FROM collection_streams cs
                JOIN collections c ON c.id = cs.collection_id
                WHERE cs.stream_id = :id::uuid
                ORDER BY
                    CASE c.type
                        WHEN 'major_works' THEN 0 WHEN 'minor_works' THEN 1
                        WHEN 'series' THEN 2 ELSE 3
                    END,
                    coalesce(cs."order", 9999), c.name
            """),
            {"id": stream_id},
        )
        rows = result.mappings().all()
        return [
            {
                "col": {
                    "id": row["id"], "name": row["name"],
                    "description": row["description"], "type": row["type"],
                    "author_id": row["author_id"],
                }
            }
            for row in rows
        ]

    async def get_works_for_collection(self, coll_id: str) -> list[dict]:
        result = await self._pg.execute(
            text("""
                SELECT
                    w.id::text AS work_id, w.title, w.status, w.language_read_in, w.date_read,
                    w.density_rating, w.source_type, w.personal_note, w.edition_note,
                    w.significance, w.page_count, w.year_published, w.original_language,
                    w.original_title, w.openlibrary_id, w.isbn, w.cover_url,
                    wc."order" AS position,
                    (SELECT jsonb_agg(jsonb_build_object('id', a.id::text, 'name', a.name))
                     FROM work_authors wa JOIN authors a ON a.id = wa.author_id
                     WHERE wa.work_id = w.id) AS authors,
                    (SELECT array_agg(ws2.stream_id::text)
                     FROM work_streams ws2 WHERE ws2.work_id = w.id) AS stream_ids
                FROM work_collections wc
                JOIN works w ON w.id = wc.work_id
                WHERE wc.collection_id = :cid::uuid
                ORDER BY coalesce(wc."order", 9999), w.title
            """),
            {"cid": coll_id},
        )
        rows = result.mappings().all()
        return [
            {
                "work": {
                    "id": r["work_id"], "title": r["title"], "status": r["status"],
                    "language_read_in": r["language_read_in"], "date_read": r["date_read"],
                    "density_rating": r["density_rating"], "source_type": r["source_type"],
                    "personal_note": r["personal_note"], "edition_note": r["edition_note"],
                    "significance": r["significance"], "page_count": r["page_count"],
                    "year_published": r["year_published"], "original_language": r["original_language"],
                    "original_title": r["original_title"], "openlibrary_id": r["openlibrary_id"],
                    "isbn": r["isbn"], "cover_url": r["cover_url"],
                },
                "position": r["position"],
                "authors": list(r["authors"] or []),
                "stream_ids": list(r["stream_ids"] or []),
            }
            for r in rows
        ]

    async def get_direct_works(self, stream_id: str) -> list[dict]:
        result = await self._pg.execute(
            text("""
                SELECT
                    w.id::text AS work_id, w.title, w.status, w.language_read_in, w.date_read,
                    w.density_rating, w.source_type, w.personal_note, w.edition_note,
                    w.significance, w.page_count, w.year_published, w.original_language,
                    w.original_title, w.openlibrary_id, w.isbn, w.cover_url,
                    ws.position,
                    (SELECT jsonb_agg(jsonb_build_object('id', a.id::text, 'name', a.name))
                     FROM work_authors wa JOIN authors a ON a.id = wa.author_id
                     WHERE wa.work_id = w.id) AS authors
                FROM work_streams ws
                JOIN works w ON w.id = ws.work_id
                WHERE ws.stream_id = :id::uuid
                ORDER BY coalesce(ws.position, 9999), w.title
            """),
            {"id": stream_id},
        )
        rows = result.mappings().all()
        return [
            {
                "work": {
                    "id": r["work_id"], "title": r["title"], "status": r["status"],
                    "language_read_in": r["language_read_in"], "date_read": r["date_read"],
                    "density_rating": r["density_rating"], "source_type": r["source_type"],
                    "personal_note": r["personal_note"], "edition_note": r["edition_note"],
                    "significance": r["significance"], "page_count": r["page_count"],
                    "year_published": r["year_published"], "original_language": r["original_language"],
                    "original_title": r["original_title"], "openlibrary_id": r["openlibrary_id"],
                    "isbn": r["isbn"], "cover_url": r["cover_url"],
                },
                "position": r["position"],
                "authors": list(r["authors"] or []),
            }
            for r in rows
        ]

    async def create(
        self, stream_id: str, name: str, description: str | None,
        color: str | None, created_at: str,
    ) -> Stream:
        await self._pg.execute(
            text("""
                INSERT INTO streams (id, name, description, color)
                VALUES (:id, :name, :description, :color)
                ON CONFLICT (id) DO NOTHING
            """),
            {"id": uuid.UUID(stream_id), "name": name, "description": description, "color": color},
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run(
                    """
                    CREATE (st:Stream {id: $id, name: $name, description: $description,
                                       color: $color, created_at: $created_at})
                    """,
                    id=stream_id, name=name, description=description,
                    color=color, created_at=created_at,
                )
        except Exception as exc:
            logger.warning("Neo4j sync failed for new stream %s: %s", stream_id, exc)
        return Stream(id=stream_id, name=name, description=description,
                      color=color, created_at=created_at)

    async def update(self, stream_id: str, updates: dict) -> bool:
        allowed = {"name", "description", "color"}
        safe = {k: v for k, v in updates.items() if k in allowed}
        if not safe:
            return True
        set_clause = ", ".join(f"{k} = :{k}" for k in safe)
        await self._pg.execute(
            text(f"UPDATE streams SET {set_clause} WHERE id = :_stream_id::uuid"),  # noqa: S608
            {**safe, "_stream_id": stream_id},
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run("MATCH (s:Stream {id: $id}) SET s += $updates", id=stream_id, updates=safe)
        except Exception as exc:
            logger.warning("Neo4j sync failed for stream update %s: %s", stream_id, exc)
        return True

    async def delete(self, stream_id: str) -> bool:
        await self._pg.execute(
            text("DELETE FROM work_streams WHERE stream_id = :id::uuid"), {"id": stream_id}
        )
        await self._pg.execute(
            text("DELETE FROM collection_streams WHERE stream_id = :id::uuid"), {"id": stream_id}
        )
        result = await self._pg.execute(
            text("DELETE FROM streams WHERE id = :id::uuid"), {"id": stream_id}
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run(
                    """
                    MATCH (s:Stream {id: $id})
                    OPTIONAL MATCH ()-[r1:BELONGS_TO]->(s)
                    OPTIONAL MATCH ()-[r2:IN_STREAM]->(s)
                    DELETE r1, r2, s
                    """,
                    id=stream_id,
                )
        except Exception as exc:
            logger.warning("Neo4j sync failed for stream delete %s: %s", stream_id, exc)
        return (result.rowcount or 0) > 0

    async def assign_work(self, work_id: str, stream_id: str, position: int | None) -> bool:
        await self._pg.execute(
            text("""
                INSERT INTO work_streams (work_id, stream_id, position)
                VALUES (:wid, :sid, :pos)
                ON CONFLICT (work_id, stream_id) DO UPDATE SET position = :pos
            """),
            {"wid": uuid.UUID(work_id), "sid": uuid.UUID(stream_id), "pos": position},
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run(
                    """
                    MATCH (w:Work {id: $wid}) MATCH (s:Stream {id: $sid})
                    MERGE (w)-[r:BELONGS_TO]->(s) ON CREATE SET r.position = $pos
                    """,
                    wid=work_id, sid=stream_id, pos=position,
                )
        except Exception as exc:
            logger.warning("Neo4j sync failed for assign_work to stream: %s", exc)
        return True

    async def remove_work(self, work_id: str, stream_id: str) -> bool:
        result = await self._pg.execute(
            text("DELETE FROM work_streams WHERE work_id = :wid::uuid AND stream_id = :sid::uuid"),
            {"wid": work_id, "sid": stream_id},
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run(
                    "MATCH (w:Work {id: $wid})-[r:BELONGS_TO]->(s:Stream {id: $sid}) DELETE r",
                    wid=work_id, sid=stream_id,
                )
        except Exception as exc:
            logger.warning("Neo4j sync failed for remove_work from stream: %s", exc)
        return (result.rowcount or 0) > 0
