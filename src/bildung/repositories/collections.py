"""Collection repository — PostgreSQL reads, dual-write (PG + Neo4j)."""
from __future__ import annotations

import logging
import uuid

from neo4j import AsyncDriver
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bildung.models.domain import Collection

logger = logging.getLogger(__name__)


class CollectionRepository:
    def __init__(self, pg_session: AsyncSession, neo4j_driver: AsyncDriver) -> None:
        self._pg = pg_session
        self._neo = neo4j_driver

    async def list(
        self,
        author_id: str | None = None,
        type_: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        result = await self._pg.execute(
            text("""
                SELECT
                    c.id::text AS id, c.name, c.description, c.type,
                    c.author_id::text AS author_id,
                    count(DISTINCT w.id) AS work_count,
                    count(DISTINCT w.id) FILTER (WHERE w.status = 'read') AS read_count
                FROM collections c
                LEFT JOIN work_collections wc ON wc.collection_id = c.id
                LEFT JOIN works w ON w.id = wc.work_id
                WHERE (:author_id IS NULL OR c.author_id = :author_id::uuid)
                  AND (:type IS NULL OR c.type = :type)
                GROUP BY c.id
                ORDER BY c.type, c.name
                LIMIT :limit OFFSET :offset
            """),
            {"author_id": author_id, "type": type_, "limit": limit, "offset": offset},
        )
        rows = result.mappings().all()
        return [
            {
                "col": {
                    "id": row["id"], "name": row["name"],
                    "description": row["description"], "type": row["type"],
                    "author_id": row["author_id"],
                },
                "work_count": row["work_count"] or 0,
                "read_count": row["read_count"] or 0,
            }
            for row in rows
        ]

    async def get(self, coll_id: str) -> Collection | None:
        result = await self._pg.execute(
            text("SELECT id::text, name, description, type, author_id::text FROM collections WHERE id = :id::uuid"),
            {"id": coll_id},
        )
        row = result.mappings().first()
        if not row:
            return None
        return Collection(
            id=row["id"], name=row["name"], description=row["description"],
            type=row["type"], author_id=row["author_id"],
        )

    async def get_with_works(self, coll_id: str) -> dict | None:
        col_result = await self._pg.execute(
            text("SELECT id::text, name, description, type, author_id::text FROM collections WHERE id = :id::uuid"),
            {"id": coll_id},
        )
        col_row = col_result.mappings().first()
        if not col_row:
            return None

        work_result = await self._pg.execute(
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
                    (SELECT array_agg(ws.stream_id::text)
                     FROM work_streams ws WHERE ws.work_id = w.id) AS stream_ids
                FROM work_collections wc
                JOIN works w ON w.id = wc.work_id
                WHERE wc.collection_id = :id::uuid
                ORDER BY coalesce(wc."order", 9999), w.title
            """),
            {"id": coll_id},
        )
        work_rows = work_result.mappings().all()
        return {
            "col": dict(col_row),
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

    async def create(
        self, coll_id: str, name: str, description: str | None,
        type_: str, author_id: str | None,
    ) -> Collection:
        author_uuid = uuid.UUID(author_id) if author_id else None
        await self._pg.execute(
            text("""
                INSERT INTO collections (id, name, description, type, author_id)
                VALUES (:id, :name, :description, :type, :author_id)
                ON CONFLICT (id) DO NOTHING
            """),
            {"id": uuid.UUID(coll_id), "name": name, "description": description,
             "type": type_, "author_id": author_uuid},
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run(
                    """
                    MERGE (c:Collection {id: $id})
                    ON CREATE SET c.name = $name, c.description = $description,
                                  c.type = $type, c.author_id = $author_id
                    """,
                    id=coll_id, name=name, description=description,
                    type=type_, author_id=author_id,
                )
        except Exception as exc:
            logger.warning("Neo4j sync failed for new collection %s: %s", coll_id, exc)
        return Collection(id=coll_id, name=name, description=description,
                          type=type_, author_id=author_id)

    async def update(self, coll_id: str, updates: dict) -> bool:
        allowed = {"name", "description", "type"}
        safe = {k: v for k, v in updates.items() if k in allowed}
        if not safe:
            return True
        set_clause = ", ".join(f"{k} = :{k}" for k in safe)
        result = await self._pg.execute(
            text(f"UPDATE collections SET {set_clause} WHERE id = :_coll_id::uuid"),  # noqa: S608
            {**safe, "_coll_id": coll_id},
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run("MATCH (c:Collection {id: $id}) SET c += $updates", id=coll_id, updates=safe)
        except Exception as exc:
            logger.warning("Neo4j sync failed for collection update %s: %s", coll_id, exc)
        return (result.rowcount or 0) > 0

    async def delete(self, coll_id: str) -> bool:
        await self._pg.execute(
            text("DELETE FROM work_collections WHERE collection_id = :id::uuid"), {"id": coll_id}
        )
        await self._pg.execute(
            text("DELETE FROM collection_streams WHERE collection_id = :id::uuid"), {"id": coll_id}
        )
        result = await self._pg.execute(
            text("DELETE FROM collections WHERE id = :id::uuid"), {"id": coll_id}
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run("MATCH (c:Collection {id: $id}) DETACH DELETE c", id=coll_id)
        except Exception as exc:
            logger.warning("Neo4j sync failed for collection delete %s: %s", coll_id, exc)
        return (result.rowcount or 0) > 0

    async def add_work(self, work_id: str, coll_id: str, order: int | None) -> bool:
        await self._pg.execute(
            text("""
                INSERT INTO work_collections (work_id, collection_id, "order")
                VALUES (:wid, :cid, :ord)
                ON CONFLICT (work_id, collection_id) DO UPDATE SET "order" = :ord
            """),
            {"wid": uuid.UUID(work_id), "cid": uuid.UUID(coll_id), "ord": order},
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run(
                    """
                    MATCH (w:Work {id: $wid}) MATCH (c:Collection {id: $cid})
                    MERGE (w)-[r:IN_COLLECTION]->(c) SET r.order = $order
                    """,
                    wid=work_id, cid=coll_id, order=order,
                )
        except Exception as exc:
            logger.warning("Neo4j sync failed for add_work to collection: %s", exc)
        return True

    async def remove_work(self, work_id: str, coll_id: str) -> bool:
        result = await self._pg.execute(
            text("DELETE FROM work_collections WHERE work_id = :wid::uuid AND collection_id = :cid::uuid"),
            {"wid": work_id, "cid": coll_id},
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run(
                    "MATCH (w:Work {id: $wid})-[r:IN_COLLECTION]->(c:Collection {id: $cid}) DELETE r",
                    wid=work_id, cid=coll_id,
                )
        except Exception as exc:
            logger.warning("Neo4j sync failed for remove_work from collection: %s", exc)
        return (result.rowcount or 0) > 0

    async def add_to_stream(self, coll_id: str, stream_id: str, order: int | None) -> bool:
        await self._pg.execute(
            text("""
                INSERT INTO collection_streams (collection_id, stream_id, "order")
                VALUES (:cid, :sid, :ord)
                ON CONFLICT (collection_id, stream_id) DO UPDATE SET "order" = :ord
            """),
            {"cid": uuid.UUID(coll_id), "sid": uuid.UUID(stream_id), "ord": order},
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run(
                    """
                    MATCH (c:Collection {id: $cid}) MATCH (s:Stream {id: $sid})
                    MERGE (c)-[r:IN_STREAM]->(s) SET r.order = $order
                    """,
                    cid=coll_id, sid=stream_id, order=order,
                )
        except Exception as exc:
            logger.warning("Neo4j sync failed for add_to_stream: %s", exc)
        return True

    async def remove_from_stream(self, coll_id: str, stream_id: str) -> bool:
        result = await self._pg.execute(
            text("DELETE FROM collection_streams WHERE collection_id = :cid::uuid AND stream_id = :sid::uuid"),
            {"cid": coll_id, "sid": stream_id},
        )
        await self._pg.commit()
        try:
            async with self._neo.session() as s:
                await s.run(
                    "MATCH (c:Collection {id: $cid})-[r:IN_STREAM]->(s:Stream {id: $sid}) DELETE r",
                    cid=coll_id, sid=stream_id,
                )
        except Exception as exc:
            logger.warning("Neo4j sync failed for remove_from_stream: %s", exc)
        return (result.rowcount or 0) > 0
