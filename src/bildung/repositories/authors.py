"""Author repository — all Author queries."""
from __future__ import annotations

from bildung.models.domain import Author
from bildung.repositories.base import NeoRepository


class AuthorRepository(NeoRepository):
    """Encapsulates all Author-related Neo4j queries."""

    async def list(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Return author data with aggregate counts.

        Returns raw dicts with keys: author, total_works, read_works,
        major_total, major_read. The service layer computes completion_pct
        and builds AuthorResponse.
        """
        records = await self._run(
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
        return [dict(r) for r in records]

    async def get(self, author_id: str) -> Author | None:
        """Return a single author's scalar fields."""
        record = await self._run_single(
            "MATCH (a:Author {id: $id}) RETURN a {.*} AS author",
            id=author_id,
        )
        if not record:
            return None
        return self._to_author(record["author"])

    async def get_with_stats(self, author_id: str) -> dict | None:
        """Return author with aggregate stats for the detail view.

        Returns a raw dict because the service layer needs to combine this
        with collections and uncollected works to build AuthorResponse.
        """
        record = await self._run_single(
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
        if not record:
            return None
        return dict(record)

    async def get_author_collections(self, author_id: str) -> list[dict]:
        """Return all collections owned by an author with their works.

        Returns raw records for the service to assemble into CollectionDetailResponse.
        """
        records = await self._run(
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
        return [dict(r) for r in records]

    async def get_uncollected_works(self, author_id: str) -> list[dict]:
        """Return works by this author not in any of the author's collections."""
        records = await self._run(
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
        return [dict(r) for r in records]

    @staticmethod
    def _to_author(a: dict) -> Author:
        return Author(
            id=a.get("id", ""),
            name=a.get("name", ""),
            birth_year=a.get("birth_year"),
            death_year=a.get("death_year"),
            nationality=a.get("nationality"),
            primary_language=a.get("primary_language"),
            openlibrary_id=a.get("openlibrary_id"),
        )
