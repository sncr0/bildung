"""Basic stats endpoint — XP fields will be populated in Step 7."""
from fastapi import APIRouter, Depends
from neo4j import AsyncDriver
from pydantic import BaseModel

from bildung.dependencies import get_neo4j_driver

router = APIRouter(tags=["stats"])


class Stats(BaseModel):
    total_works: int
    total_authors: int
    total_streams: int
    by_status: dict[str, int]
    by_year: dict[str, int]
    by_language: dict[str, int]


@router.get("/stats", response_model=Stats)
async def get_stats(driver: AsyncDriver = Depends(get_neo4j_driver)) -> Stats:
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
