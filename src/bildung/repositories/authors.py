"""Author repository — PostgreSQL reads."""
from __future__ import annotations

import logging

from neo4j import AsyncDriver
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bildung.models.domain import Author

logger = logging.getLogger(__name__)


class AuthorRepository:
    def __init__(self, pg_session: AsyncSession, neo4j_driver: AsyncDriver) -> None:
        self._pg = pg_session
        self._neo = neo4j_driver

    async def list(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Return author data with aggregate counts."""
        result = await self._pg.execute(
            text("""
                SELECT
                    a.id::text, a.name, a.birth_year, a.death_year,
                    a.nationality, a.primary_language, a.openlibrary_id,
                    count(DISTINCT w.id) AS total_works,
                    count(DISTINCT w.id) FILTER (WHERE w.status = 'read') AS read_works,
                    count(DISTINCT w2.id) AS major_total,
                    count(DISTINCT w2.id) FILTER (WHERE w2.status = 'read') AS major_read
                FROM authors a
                LEFT JOIN work_authors wa ON wa.author_id = a.id
                LEFT JOIN works w ON w.id = wa.work_id
                LEFT JOIN collections c ON c.author_id = a.id AND c.type = 'major_works'
                LEFT JOIN work_collections wc2 ON wc2.collection_id = c.id
                LEFT JOIN works w2 ON w2.id = wc2.work_id
                GROUP BY a.id
                ORDER BY a.name
                LIMIT :limit OFFSET :offset
            """),
            {"limit": limit, "offset": offset},
        )
        rows = result.mappings().all()
        return [
            {
                "author": {
                    "id": row["id"],
                    "name": row["name"],
                    "birth_year": row["birth_year"],
                    "death_year": row["death_year"],
                    "nationality": row["nationality"],
                    "primary_language": row["primary_language"],
                    "openlibrary_id": row["openlibrary_id"],
                },
                "total_works": row["total_works"] or 0,
                "read_works": row["read_works"] or 0,
                "major_total": row["major_total"] or 0,
                "major_read": row["major_read"] or 0,
            }
            for row in rows
        ]

    async def get(self, author_id: str) -> Author | None:
        result = await self._pg.execute(
            text("SELECT id::text, name, birth_year, death_year, nationality, primary_language, openlibrary_id FROM authors WHERE id = :id::uuid"),
            {"id": author_id},
        )
        row = result.mappings().first()
        if not row:
            return None
        return self._to_author(dict(row))

    async def get_with_stats(self, author_id: str) -> dict | None:
        result = await self._pg.execute(
            text("""
                SELECT
                    a.id::text, a.name, a.birth_year, a.death_year,
                    a.nationality, a.primary_language, a.openlibrary_id,
                    count(DISTINCT w.id) AS total_works,
                    count(DISTINCT w.id) FILTER (WHERE w.status = 'read') AS read_works,
                    count(DISTINCT w2.id) AS major_total,
                    count(DISTINCT w2.id) FILTER (WHERE w2.status = 'read') AS major_read
                FROM authors a
                LEFT JOIN work_authors wa ON wa.author_id = a.id
                LEFT JOIN works w ON w.id = wa.work_id
                LEFT JOIN collections c ON c.author_id = a.id AND c.type = 'major_works'
                LEFT JOIN work_collections wc2 ON wc2.collection_id = c.id
                LEFT JOIN works w2 ON w2.id = wc2.work_id
                WHERE a.id = :id::uuid
                GROUP BY a.id
            """),
            {"id": author_id},
        )
        row = result.mappings().first()
        if not row:
            return None
        return {
            "author": {
                "id": row["id"],
                "name": row["name"],
                "birth_year": row["birth_year"],
                "death_year": row["death_year"],
                "nationality": row["nationality"],
                "primary_language": row["primary_language"],
                "openlibrary_id": row["openlibrary_id"],
            },
            "total_works": row["total_works"] or 0,
            "read_works": row["read_works"] or 0,
            "major_total": row["major_total"] or 0,
            "major_read": row["major_read"] or 0,
        }

    async def get_author_collections(self, author_id: str) -> list[dict]:
        """Return all collections owned by this author, with their works."""
        result = await self._pg.execute(
            text("""
                SELECT
                    c.id::text AS coll_id, c.name AS coll_name, c.description,
                    c.type AS coll_type, c.author_id::text AS coll_author_id,
                    w.id::text AS work_id, w.title, w.status, w.language_read_in, w.date_read,
                    w.density_rating, w.source_type, w.personal_note, w.edition_note,
                    w.significance, w.page_count, w.year_published, w.original_language,
                    w.original_title, w.openlibrary_id, w.isbn, w.cover_url,
                    wc."order" AS ord
                FROM collections c
                LEFT JOIN work_collections wc ON wc.collection_id = c.id
                LEFT JOIN works w ON w.id = wc.work_id
                WHERE c.author_id = :id::uuid
                ORDER BY
                    CASE c.type
                        WHEN 'major_works' THEN 0 WHEN 'minor_works' THEN 1
                        WHEN 'series' THEN 2 ELSE 3
                    END,
                    c.name,
                    coalesce(wc."order", 9999),
                    w.title
            """),
            {"id": author_id},
        )
        rows = result.mappings().all()

        # Group into {col: ..., work_entries: [...]}
        coll_order: list[str] = []
        coll_map: dict[str, dict] = {}
        for row in rows:
            cid = row["coll_id"]
            if cid not in coll_map:
                coll_order.append(cid)
                coll_map[cid] = {
                    "col": {
                        "id": cid,
                        "name": row["coll_name"],
                        "description": row["description"],
                        "type": row["coll_type"],
                        "author_id": row["coll_author_id"],
                    },
                    "work_entries": [],
                }
            if row["work_id"] is not None:
                w = {
                    "id": row["work_id"], "title": row["title"], "status": row["status"],
                    "language_read_in": row["language_read_in"], "date_read": row["date_read"],
                    "density_rating": row["density_rating"], "source_type": row["source_type"],
                    "personal_note": row["personal_note"], "edition_note": row["edition_note"],
                    "significance": row["significance"], "page_count": row["page_count"],
                    "year_published": row["year_published"], "original_language": row["original_language"],
                    "original_title": row["original_title"], "openlibrary_id": row["openlibrary_id"],
                    "isbn": row["isbn"], "cover_url": row["cover_url"],
                }
                coll_map[cid]["work_entries"].append({"w": w, "ord": row["ord"]})
        return [coll_map[cid] for cid in coll_order]

    async def get_uncollected_works(self, author_id: str) -> list[dict]:
        """Return works by this author not in any of the author's collections."""
        result = await self._pg.execute(
            text("""
                SELECT
                    w.id::text AS work_id, w.title, w.status, w.language_read_in, w.date_read,
                    w.density_rating, w.source_type, w.personal_note, w.edition_note,
                    w.significance, w.page_count, w.year_published, w.original_language,
                    w.original_title, w.openlibrary_id, w.isbn, w.cover_url,
                    (SELECT jsonb_agg(jsonb_build_object('id', a2.id::text, 'name', a2.name))
                     FROM work_authors wa2 JOIN authors a2 ON a2.id = wa2.author_id
                     WHERE wa2.work_id = w.id) AS authors,
                    (SELECT array_agg(ws.stream_id::text)
                     FROM work_streams ws WHERE ws.work_id = w.id) AS stream_ids,
                    (SELECT jsonb_agg(jsonb_build_object('id', c2.id::text, 'name', c2.name,
                                     'type', c2.type, 'order', wc2."order"))
                     FROM work_collections wc2 JOIN collections c2 ON c2.id = wc2.collection_id
                     WHERE wc2.work_id = w.id) AS cols
                FROM works w
                JOIN work_authors wa ON wa.work_id = w.id AND wa.author_id = :id::uuid
                WHERE NOT EXISTS (
                    SELECT 1 FROM work_collections wc3
                    JOIN collections c3 ON c3.id = wc3.collection_id
                    WHERE wc3.work_id = w.id AND c3.author_id = :id::uuid
                )
                ORDER BY w.title
            """),
            {"id": author_id},
        )
        rows = result.mappings().all()
        return [
            {
                "work": {
                    "id": row["work_id"], "title": row["title"], "status": row["status"],
                    "language_read_in": row["language_read_in"], "date_read": row["date_read"],
                    "density_rating": row["density_rating"], "source_type": row["source_type"],
                    "personal_note": row["personal_note"], "edition_note": row["edition_note"],
                    "significance": row["significance"], "page_count": row["page_count"],
                    "year_published": row["year_published"], "original_language": row["original_language"],
                    "original_title": row["original_title"], "openlibrary_id": row["openlibrary_id"],
                    "isbn": row["isbn"], "cover_url": row["cover_url"],
                },
                "stream_ids": list(row["stream_ids"] or []),
                "cols": list(row["cols"] or []),
            }
            for row in rows
        ]

    @staticmethod
    def _to_author(a: dict) -> Author:
        return Author(
            id=str(a.get("id") or ""),
            name=a.get("name") or "",
            birth_year=a.get("birth_year"),
            death_year=a.get("death_year"),
            nationality=a.get("nationality"),
            primary_language=a.get("primary_language"),
            openlibrary_id=a.get("openlibrary_id"),
        )
