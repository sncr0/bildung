"""Series repository — PostgreSQL reads, dual-write (PG + Neo4j)."""
from __future__ import annotations

import logging
import uuid

from neo4j import AsyncDriver
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bildung.models.domain import Series

logger = logging.getLogger(__name__)


class SeriesRepository:
    def __init__(self, pg_session: AsyncSession, neo4j_driver: AsyncDriver) -> None:
        self._pg = pg_session
        self._neo = neo4j_driver

    async def list(self, limit: int = 50, offset: int = 0) -> list[dict]:
        result = await self._pg.execute(
            text("""
                SELECT
                    s.id::text, s.name, s.description,
                    count(DISTINCT w.id) AS work_count,
                    count(DISTINCT w.id) FILTER (WHERE w.status = 'read') AS read_count
                FROM series s
                LEFT JOIN work_series ws ON ws.series_id = s.id
                LEFT JOIN works w ON w.id = ws.work_id
                GROUP BY s.id
                ORDER BY s.name
                LIMIT :limit OFFSET :offset
            """),
            {"limit": limit, "offset": offset},
        )
        rows = result.mappings().all()
        return [
            {
                "series": {"id": row["id"], "name": row["name"], "description": row["description"]},
                "work_count": row["work_count"] or 0,
                "read_count": row["read_count"] or 0,
            }
            for row in rows
        ]

    async def get(self, series_id: str) -> Series | None:
        result = await self._pg.execute(
            text("SELECT id::text, name, description FROM series WHERE id = :id::uuid"),
            {"id": series_id},
        )
        row = result.mappings().first()
        if not row:
            return None
        return Series(id=row["id"], name=row["name"], description=row["description"])

    async def get_with_works(self, series_id: str) -> dict | None:
        s_result = await self._pg.execute(
            text("SELECT id::text, name, description FROM series WHERE id = :id::uuid"),
            {"id": series_id},
        )
        s_row = s_result.mappings().first()
        if not s_row:
            return None

        work_result = await self._pg.execute(
            text("""
                SELECT
                    w.id::text AS work_id, w.title, w.status, w.language_read_in, w.date_read,
                    w.density_rating, w.source_type, w.personal_note, w.edition_note,
                    w.significance, w.page_count, w.year_published, w.original_language,
                    w.original_title, w.openlibrary_id, w.isbn, w.cover_url,
                    wser."order" AS position,
                    (SELECT jsonb_agg(jsonb_build_object('id', a.id::text, 'name', a.name))
                     FROM work_authors wa JOIN authors a ON a.id = wa.author_id
                     WHERE wa.work_id = w.id) AS authors,
                    (SELECT array_agg(ws.stream_id::text)
                     FROM work_streams ws WHERE ws.work_id = w.id) AS stream_ids
                FROM work_series wser
                JOIN works w ON w.id = wser.work_id
                WHERE wser.series_id = :id::uuid
                ORDER BY coalesce(wser."order", 9999), w.title
            """),
            {"id": series_id},
        )
        work_rows = work_result.mappings().all()
        return {
            "series": dict(s_row),
            "works": [
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
                for r in work_rows
            ],
        }

    async def create(self, series_id: str, name: str, description: str | None) -> Series:
        await self._pg.execute(
            text("""
                INSERT INTO series (id, name, description)
                VALUES (:id, :name, :description)
                ON CONFLICT (id) DO NOTHING
            """),
            {"id": uuid.UUID(series_id), "name": name, "description": description},
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run(
                    "MERGE (s:Series {id: $id}) ON CREATE SET s.name = $name, s.description = $description",
                    id=series_id, name=name, description=description,
                )
        except Exception as exc:
            logger.warning("Neo4j sync failed for new series %s: %s", series_id, exc)
        return Series(id=series_id, name=name, description=description)

    async def update(self, series_id: str, updates: dict) -> bool:
        allowed = {"name", "description"}
        safe = {k: v for k, v in updates.items() if k in allowed}
        if not safe:
            return True
        set_clause = ", ".join(f"{k} = :{k}" for k in safe)
        result = await self._pg.execute(
            text(f"UPDATE series SET {set_clause} WHERE id = :_series_id::uuid"),  # noqa: S608
            {**safe, "_series_id": series_id},
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run("MATCH (s:Series {id: $id}) SET s += $updates", id=series_id, updates=safe)
        except Exception as exc:
            logger.warning("Neo4j sync failed for series update %s: %s", series_id, exc)
        return (result.rowcount or 0) > 0

    async def delete(self, series_id: str) -> bool:
        await self._pg.execute(
            text("DELETE FROM work_series WHERE series_id = :id::uuid"), {"id": series_id}
        )
        result = await self._pg.execute(
            text("DELETE FROM series WHERE id = :id::uuid"), {"id": series_id}
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run("MATCH (s:Series {id: $id}) DETACH DELETE s", id=series_id)
        except Exception as exc:
            logger.warning("Neo4j sync failed for series delete %s: %s", series_id, exc)
        return (result.rowcount or 0) > 0

    async def assign_work(self, work_id: str, series_id: str, order: int | None) -> bool:
        await self._pg.execute(
            text("""
                INSERT INTO work_series (work_id, series_id, "order")
                VALUES (:wid, :sid, :ord)
                ON CONFLICT (work_id, series_id) DO UPDATE SET "order" = :ord
            """),
            {"wid": uuid.UUID(work_id), "sid": uuid.UUID(series_id), "ord": order},
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run(
                    """
                    MATCH (w:Work {id: $wid}) MATCH (s:Series {id: $sid})
                    MERGE (w)-[r:PART_OF]->(s) SET r.order = $order
                    """,
                    wid=work_id, sid=series_id, order=order,
                )
        except Exception as exc:
            logger.warning("Neo4j sync failed for assign_work to series: %s", exc)
        return True

    async def remove_work(self, work_id: str, series_id: str) -> bool:
        result = await self._pg.execute(
            text("DELETE FROM work_series WHERE work_id = :wid::uuid AND series_id = :sid::uuid"),
            {"wid": work_id, "sid": series_id},
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run(
                    "MATCH (w:Work {id: $wid})-[r:PART_OF]->(s:Series {id: $sid}) DELETE r",
                    wid=work_id, sid=series_id,
                )
        except Exception as exc:
            logger.warning("Neo4j sync failed for remove_work from series: %s", exc)
        return (result.rowcount or 0) > 0
