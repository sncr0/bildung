"""Work repository — PostgreSQL reads, dual-write (PG + Neo4j)."""
from __future__ import annotations

import logging
import uuid

from neo4j import AsyncDriver
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bildung.models.domain import AuthorSummary, CollectionMembership, Work

logger = logging.getLogger(__name__)

_LIST_SQL = text("""
    SELECT
        w.id::text AS id, w.title, w.status, w.language_read_in, w.date_read,
        w.density_rating, w.source_type, w.personal_note, w.edition_note,
        w.significance, w.page_count, w.year_published, w.original_language,
        w.original_title, w.openlibrary_id, w.isbn, w.cover_url,
        (SELECT jsonb_agg(jsonb_build_object('id', a.id::text, 'name', a.name))
         FROM work_authors wa JOIN authors a ON a.id = wa.author_id
         WHERE wa.work_id = w.id) AS authors
    FROM works w
    WHERE (:status IS NULL OR w.status = :status)
      AND (:author IS NULL OR w.id IN (
          SELECT wa2.work_id FROM work_authors wa2
          JOIN authors a2 ON a2.id = wa2.author_id
          WHERE lower(a2.name) LIKE lower('%' || :author || '%')
      ))
    ORDER BY w.title
    LIMIT :limit OFFSET :offset
""")

_GET_SQL = text("""
    SELECT
        w.id::text AS id, w.title, w.status, w.language_read_in, w.date_read,
        w.density_rating, w.source_type, w.personal_note, w.edition_note,
        w.significance, w.page_count, w.year_published, w.original_language,
        w.original_title, w.openlibrary_id, w.isbn, w.cover_url,
        (SELECT jsonb_agg(jsonb_build_object('id', a.id::text, 'name', a.name))
         FROM work_authors wa JOIN authors a ON a.id = wa.author_id
         WHERE wa.work_id = w.id) AS authors,
        (SELECT jsonb_agg(
                    jsonb_build_object(
                        'id', c.id::text, 'name', c.name, 'type', c.type,
                        'order', wc."order"
                    ) ORDER BY coalesce(wc."order", 9999), c.name
                )
         FROM work_collections wc JOIN collections c ON c.id = wc.collection_id
         WHERE wc.work_id = w.id) AS collections
    FROM works w
    WHERE w.id = :id::uuid
""")


class WorkRepository:
    def __init__(self, pg_session: AsyncSession, neo4j_driver: AsyncDriver) -> None:
        self._pg = pg_session
        self._neo = neo4j_driver

    async def list(
        self,
        status: str | None = None,
        author: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Work]:
        result = await self._pg.execute(
            _LIST_SQL, {"status": status, "author": author, "limit": limit, "offset": offset}
        )
        rows = result.mappings().all()
        return [self._to_work(dict(row), list(row["authors"] or [])) for row in rows]

    async def get(self, work_id: str) -> Work | None:
        result = await self._pg.execute(_GET_SQL, {"id": work_id})
        row = result.mappings().first()
        if not row:
            return None
        return self._to_work(
            dict(row),
            list(row["authors"] or []),
            list(row["collections"] or []),
        )

    async def get_stream_ids(self, work_id: str) -> list[str]:
        result = await self._pg.execute(
            text("SELECT array_agg(stream_id::text) AS ids FROM work_streams WHERE work_id = :id::uuid"),
            {"id": work_id},
        )
        row = result.mappings().first()
        if not row or row["ids"] is None:
            return []
        return list(row["ids"])

    async def create(
        self,
        work_id: str,
        title: str,
        author_id: str,
        author_name: str,
        *,
        status: str = "to_read",
        language_read_in: str | None = None,
        date_read: str | None = None,
        density_rating: str | None = None,
        source_type: str = "fiction",
        personal_note: str | None = None,
        significance: str | None = None,
    ) -> Work:
        await self._pg.execute(
            text("""
                INSERT INTO authors (id, name)
                VALUES (:id, :name)
                ON CONFLICT (id) DO NOTHING
            """),
            {"id": uuid.UUID(author_id), "name": author_name},
        )
        await self._pg.execute(
            text("""
                INSERT INTO works (id, title, status, language_read_in, date_read,
                    density_rating, source_type, personal_note, significance)
                VALUES (:id, :title, :status, :language_read_in, :date_read,
                    :density_rating, :source_type, :personal_note, :significance)
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": uuid.UUID(work_id),
                "title": title,
                "status": status,
                "language_read_in": language_read_in,
                "date_read": date_read,
                "density_rating": density_rating,
                "source_type": source_type,
                "personal_note": personal_note,
                "significance": significance,
            },
        )
        await self._pg.execute(
            text("""
                INSERT INTO work_authors (work_id, author_id)
                VALUES (:wid, :aid)
                ON CONFLICT DO NOTHING
            """),
            {"wid": uuid.UUID(work_id), "aid": uuid.UUID(author_id)},
        )
        await self._pg.commit()
        try:
            await self._sync_neo4j_create(
                work_id, title, author_id, author_name,
                status=status, language_read_in=language_read_in,
                date_read=date_read, density_rating=density_rating,
                source_type=source_type, personal_note=personal_note,
                significance=significance,
            )
        except Exception as exc:
            logger.warning("Neo4j sync failed for new work %s: %s", work_id, exc)
        return await self.get(work_id)  # type: ignore[return-value]

    async def update(self, work_id: str, updates: dict) -> Work | None:
        if not updates:
            return await self.get(work_id)
        allowed = {
            "status", "density_rating", "language_read_in", "personal_note",
            "edition_note", "date_read", "source_type", "significance",
        }
        safe = {k: v for k, v in updates.items() if k in allowed}
        if not safe:
            return await self.get(work_id)
        set_clause = ", ".join(f"{k} = :{k}" for k in safe)
        await self._pg.execute(
            text(f"UPDATE works SET {set_clause}, updated_at = now() WHERE id = :_work_id::uuid"),  # noqa: S608
            {**safe, "_work_id": work_id},
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run(
                    "MATCH (w:Work {id: $id}) SET w += $updates",
                    id=work_id, updates=safe,
                )
        except Exception as exc:
            logger.warning("Neo4j sync failed for work update %s: %s", work_id, exc)
        return await self.get(work_id)

    # --- private Neo4j sync ---

    async def _sync_neo4j_create(
        self, work_id: str, title: str, author_id: str, author_name: str, **props: object
    ) -> None:
        async with self._neo.session() as session:
            async with await session.begin_transaction() as tx:
                await tx.run(
                    "MERGE (a:Author {id: $id}) ON CREATE SET a.name = $name",
                    id=author_id, name=author_name,
                )
                await tx.run(
                    """
                    MERGE (w:Work {id: $id})
                    ON CREATE SET w.title = $title, w.status = $status,
                        w.language_read_in = $language_read_in, w.date_read = $date_read,
                        w.density_rating = $density_rating, w.source_type = $source_type,
                        w.personal_note = $personal_note, w.significance = $significance
                    """,
                    id=work_id, title=title, **props,
                )
                await tx.run(
                    "MATCH (a:Author {id: $aid}) MATCH (w:Work {id: $wid}) MERGE (a)-[:WROTE]->(w)",
                    aid=author_id, wid=work_id,
                )

    # --- static mapping helpers (called by services) ---

    @staticmethod
    def _to_work(
        work_map: dict,
        authors_list: list[dict],
        collections_list: list[dict] | None = None,
    ) -> Work:
        """Map a work dict (from PG or Neo4j) to a domain Work."""
        authors = [
            AuthorSummary(id=str(a.get("id") or ""), name=a.get("name") or "")
            for a in authors_list
            if a.get("name")
        ]
        collections = [
            CollectionMembership(
                collection_id=str(c.get("id") or ""),
                collection_name=c.get("name") or "",
                collection_type=c.get("type", "anthology"),
                order=c.get("order"),
            )
            for c in (collections_list or [])
            if c.get("id")
        ]
        return Work(
            id=str(work_map.get("id") or ""),
            title=work_map.get("title") or "",
            status=work_map.get("status", "to_read"),
            language_read_in=work_map.get("language_read_in"),
            date_read=work_map.get("date_read"),
            density_rating=work_map.get("density_rating"),
            source_type=work_map.get("source_type", "fiction"),
            personal_note=work_map.get("personal_note"),
            edition_note=work_map.get("edition_note"),
            significance=work_map.get("significance"),
            page_count=work_map.get("page_count"),
            year_published=work_map.get("year_published"),
            original_language=work_map.get("original_language"),
            original_title=work_map.get("original_title"),
            openlibrary_id=work_map.get("openlibrary_id"),
            isbn=work_map.get("isbn"),
            cover_url=work_map.get("cover_url"),
            authors=authors,
            collections=collections,
        )
