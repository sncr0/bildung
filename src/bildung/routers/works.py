"""Works router — /works resource."""
from fastapi import APIRouter, Depends, HTTPException, Query

from bildung.dependencies import get_work_service
from bildung.models.api import (
    CreateWorkRequest,
    UpdateWorkRequest,
    WorkResponse,
)
from bildung.models.neo4j import StatusLiteral
from bildung.services.works import WorkService

router = APIRouter(prefix="/works", tags=["works"])


@router.get("", response_model=list[WorkResponse])
async def list_works(
    status: StatusLiteral | None = Query(None, description="Filter by reading status"),
    author: str | None = Query(None, description="Filter by author name (substring)"),
    limit: int = Query(50, ge=1, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    svc: WorkService = Depends(get_work_service),
) -> list[WorkResponse]:
    return await svc.list(status=status, author=author, limit=limit, offset=offset)


@router.get("/{work_id}", response_model=WorkResponse)
async def get_work(
    work_id: str,
    svc: WorkService = Depends(get_work_service),
) -> WorkResponse:
    work = await svc.get(work_id)
    if not work:
        raise HTTPException(status_code=404, detail="Work not found")
    return work


@router.post("", response_model=WorkResponse, status_code=201)
async def create_work(
    req: CreateWorkRequest,
    svc: WorkService = Depends(get_work_service),
) -> WorkResponse:
    return await svc.create(req)


@router.patch("/{work_id}", response_model=WorkResponse)
async def update_work(
    work_id: str,
    req: UpdateWorkRequest,
    svc: WorkService = Depends(get_work_service),
) -> WorkResponse:
    work = await svc.update(work_id, req)
    if not work:
        raise HTTPException(status_code=404, detail="Work not found")
    return work
