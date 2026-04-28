"""Stats service — aggregation queries for the dashboard."""
from __future__ import annotations

import logging

from neo4j import AsyncDriver

from bildung.models.api import Stats

logger = logging.getLogger(__name__)


async def get_stats(driver: AsyncDriver) -> Stats:
    async with driver.session() as s:
        total_works = (await (await s.run(
            "MATCH (w:Work) RETURN count(w) AS n"
        )).single())["n"]

        total_authors = (await (await s.run(
            "MATCH (a:Author) RETURN count(a) AS n"
        )).single())["n"]

        total_streams = (await (await s.run(
            "MATCH (s:Stream) RETURN count(s) AS n"
        )).single())["n"]

        by_status = {
            r["status"]: r["n"]
            for r in await (await s.run(
                "MATCH (w:Work) RETURN w.status AS status, count(w) AS n"
            )).data()
            if r["status"]
        }

        by_year = {
            r["yr"]: r["n"]
            for r in await (await s.run(
                "MATCH (w:Work) WHERE w.date_read IS NOT NULL "
                "RETURN w.date_read AS yr, count(w) AS n ORDER BY yr"
            )).data()
        }

        by_language = {
            r["lang"]: r["n"]
            for r in await (await s.run(
                "MATCH (w:Work) WHERE w.language_read_in IS NOT NULL "
                "RETURN w.language_read_in AS lang, count(w) AS n ORDER BY n DESC"
            )).data()
        }

    return Stats(
        total_works=total_works,
        total_authors=total_authors,
        total_streams=total_streams,
        by_status=by_status,
        by_year=by_year,
        by_language=by_language,
    )
