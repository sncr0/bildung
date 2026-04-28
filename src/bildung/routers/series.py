"""Series router — /series resource and /works/{id}/series membership."""
from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import AsyncDriver

from bildung.dependencies import get_neo4j_driver
from bildung.models.api import (
    CreateSeriesRequest,
    SeriesDetailResponse,
    SeriesMembershipRequest,
    SeriesResponse,
    UpdateSeriesRequest,
)
from bildung.services import series as svc

router = APIRouter(tags=["series"])


# ---------------------------------------------------------------------------
# Series CRUD  —  /series
# ---------------------------------------------------------------------------

@router.get("/series", response_model=list[SeriesResponse])
async def list_series(
    limit: int = Query(50, ge=1, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> list[SeriesResponse]:
    return await svc.list_series(driver, limit=limit, offset=offset)


@router.get("/series/{series_id}", response_model=SeriesDetailResponse)
async def get_series(
    series_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> SeriesDetailResponse:
    s = await svc.get_series(driver, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    return s


@router.post("/series", response_model=SeriesResponse, status_code=201)
async def create_series(
    req: CreateSeriesRequest,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> SeriesResponse:
    return await svc.create_series(driver, req)


@router.patch("/series/{series_id}", response_model=SeriesDetailResponse)
async def update_series(
    series_id: str,
    req: UpdateSeriesRequest,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> SeriesDetailResponse:
    s = await svc.update_series(driver, series_id, req)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    return s


@router.delete("/series/{series_id}", status_code=204)
async def delete_series(
    series_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> None:
    ok = await svc.delete_series(driver, series_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Series not found")


# ---------------------------------------------------------------------------
# Series membership  —  /works/{work_id}/series
# ---------------------------------------------------------------------------

@router.put("/works/{work_id}/series/{series_id}", status_code=204)
async def add_work_to_series(
    work_id: str,
    series_id: str,
    req: SeriesMembershipRequest = SeriesMembershipRequest(),
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> None:
    ok = await svc.assign_work_to_series(driver, work_id, series_id, req)
    if not ok:
        raise HTTPException(status_code=404, detail="Work or series not found")


@router.delete("/works/{work_id}/series/{series_id}", status_code=204)
async def remove_work_from_series(
    work_id: str,
    series_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> None:
    ok = await svc.remove_work_from_series(driver, work_id, series_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Membership not found")
