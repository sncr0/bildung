"""Stats router — /stats endpoint."""
from fastapi import APIRouter, Depends
from neo4j import AsyncDriver

from bildung.dependencies import get_neo4j_driver
from bildung.models.api import Stats
from bildung.services import stats as svc

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=Stats)
async def get_stats(driver: AsyncDriver = Depends(get_neo4j_driver)) -> Stats:
    return await svc.get_stats(driver)
