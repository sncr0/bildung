"""Stats router — /stats endpoint."""
from fastapi import APIRouter, Depends

from bildung.dependencies import get_stats_service
from bildung.models.api import Stats
from bildung.services.stats import StatsService

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=Stats)
async def get_stats(svc: StatsService = Depends(get_stats_service)) -> Stats:
    return await svc.get_stats()
