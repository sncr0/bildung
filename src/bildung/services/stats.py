"""Stats service — aggregation queries against PostgreSQL."""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bildung.models.api import Stats

logger = logging.getLogger(__name__)


class StatsService:
    def __init__(self, pg_session: AsyncSession) -> None:
        self._pg = pg_session

    async def get_stats(self) -> Stats:
        result = await self._pg.execute(text("SELECT count(*) FROM works"))
        total_works = result.scalar() or 0

        result = await self._pg.execute(text("SELECT count(*) FROM authors"))
        total_authors = result.scalar() or 0

        result = await self._pg.execute(text("SELECT count(*) FROM streams"))
        total_streams = result.scalar() or 0

        result = await self._pg.execute(
            text("SELECT status, count(*) AS n FROM works GROUP BY status")
        )
        by_status = {row.status: row.n for row in result if row.status}

        result = await self._pg.execute(
            text("""
                SELECT left(date_read, 4) AS yr, count(*) AS n
                FROM works
                WHERE date_read IS NOT NULL AND length(date_read) >= 4
                GROUP BY yr
                ORDER BY yr
            """)
        )
        by_year = {row.yr: row.n for row in result if row.yr}

        result = await self._pg.execute(
            text("""
                SELECT language_read_in AS lang, count(*) AS n
                FROM works
                WHERE language_read_in IS NOT NULL
                GROUP BY lang
                ORDER BY n DESC
            """)
        )
        by_language = {row.lang: row.n for row in result if row.lang}

        return Stats(
            total_works=total_works,
            total_authors=total_authors,
            total_streams=total_streams,
            by_status=by_status,
            by_year=by_year,
            by_language=by_language,
        )
