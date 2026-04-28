"""Series router — /series resource and /works/{id}/series membership."""
from fastapi import APIRouter, Depends, HTTPException, Query

from bildung.dependencies import get_series_service
from bildung.models.api import (
    CreateSeriesRequest,
    SeriesDetailResponse,
    SeriesMembershipRequest,
    SeriesResponse,
    UpdateSeriesRequest,
)
from bildung.services.series import SeriesService

router = APIRouter(tags=["series"])


# ---------------------------------------------------------------------------
# Series CRUD  —  /series
# ---------------------------------------------------------------------------

@router.get("/series", response_model=list[SeriesResponse])
async def list_series(
    limit: int = Query(50, ge=1, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    svc: SeriesService = Depends(get_series_service),
) -> list[SeriesResponse]:
    return await svc.list(limit=limit, offset=offset)


@router.get("/series/{series_id}", response_model=SeriesDetailResponse)
async def get_series(
    series_id: str,
    svc: SeriesService = Depends(get_series_service),
) -> SeriesDetailResponse:
    s = await svc.get(series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    return s


@router.post("/series", response_model=SeriesResponse, status_code=201)
async def create_series(
    req: CreateSeriesRequest,
    svc: SeriesService = Depends(get_series_service),
) -> SeriesResponse:
    return await svc.create(req)


@router.patch("/series/{series_id}", response_model=SeriesDetailResponse)
async def update_series(
    series_id: str,
    req: UpdateSeriesRequest,
    svc: SeriesService = Depends(get_series_service),
) -> SeriesDetailResponse:
    s = await svc.update(series_id, req)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    return s


@router.delete("/series/{series_id}", status_code=204)
async def delete_series(
    series_id: str,
    svc: SeriesService = Depends(get_series_service),
) -> None:
    ok = await svc.delete(series_id)
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
    svc: SeriesService = Depends(get_series_service),
) -> None:
    ok = await svc.assign_work(work_id, series_id, req)
    if not ok:
        raise HTTPException(status_code=404, detail="Work or series not found")


@router.delete("/works/{work_id}/series/{series_id}", status_code=204)
async def remove_work_from_series(
    work_id: str,
    series_id: str,
    svc: SeriesService = Depends(get_series_service),
) -> None:
    ok = await svc.remove_work(work_id, series_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Membership not found")
