"""Work repository — all Work CRUD and query operations."""
from __future__ import annotations

from neo4j import AsyncDriver

from bildung.models.domain import AuthorSummary, CollectionMembership, Work
from bildung.repositories.base import NeoRepository


class WorkRepository(NeoRepository):
    """Encapsulates all Work-related Neo4j queries."""

    async def list(
        self,
        status: str | None = None,
        author: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Work]:
        records = await self._run(
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
        return [self._to_work(r["work"], r["authors"]) for r in records]

    async def get(self, work_id: str) -> Work | None:
        record = await self._run_single(
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
        if not record:
            return None
        return self._to_work(
            record["work"], record["authors"],
            record["collections"],
        )

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
        """Create a work node and link to its author. Returns the created Work."""
        async with self._driver.session() as session:
            async with await session.begin_transaction() as tx:
                # Ensure author exists
                exists = await tx.run(
                    "MATCH (a:Author {id: $id}) RETURN count(a) AS n", id=author_id
                )
                rec = await exists.single()
                if rec["n"] == 0:
                    await tx.run(
                        "CREATE (a:Author {id: $id, name: $name})",
                        id=author_id, name=author_name,
                    )

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
                    id=work_id, title=title, status=status,
                    language_read_in=language_read_in,
                    date_read=date_read, density_rating=density_rating,
                    source_type=source_type, personal_note=personal_note,
                    significance=significance,
                )

                await tx.run(
                    """
                    MATCH (a:Author {id: $aid})
                    MATCH (w:Work {id: $wid})
                    MERGE (a)-[:WROTE]->(w)
                    """,
                    aid=author_id, wid=work_id,
                )

        return await self.get(work_id)  # type: ignore[return-value]

    async def update(self, work_id: str, updates: dict) -> Work | None:
        """Update scalar properties on a Work node."""
        if not updates:
            return await self.get(work_id)
        async with self._driver.session() as session:
            await session.run(
                "MATCH (w:Work {id: $id}) SET w += $updates",
                id=work_id, updates=updates,
            )
        return await self.get(work_id)

    # --- private mapping ---

    @staticmethod
    def _to_work(
        work_map: dict,
        authors_list: list[dict],
        collections_list: list[dict] | None = None,
    ) -> Work:
        """Map a Neo4j record to a domain Work."""
        authors = [
            AuthorSummary(id=a["id"] or "", name=a["name"] or "")
            for a in authors_list
            if a.get("name")
        ]
        collections = [
            CollectionMembership(
                collection_id=c["id"] or "",
                collection_name=c["name"] or "",
                collection_type=c.get("type", "anthology"),
                order=c.get("order"),
            )
            for c in (collections_list or [])
            if c.get("id")
        ]
        return Work(
            id=work_map.get("id", ""),
            title=work_map.get("title", ""),
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
