"""Works router — /works resource."""
from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import AsyncDriver
from sqlalchemy.ext.asyncio import AsyncSession

from bildung.dependencies import get_neo4j_driver, get_pg_session
from bildung.models.api import (
    CreateWorkRequest,
    UpdateWorkRequest,
    WorkResponse,
)
from bildung.models.neo4j import StatusLiteral
from bildung.services import works as svc

router = APIRouter(prefix="/works", tags=["works"])


@router.get("", response_model=list[WorkResponse])
async def list_works(
    status: StatusLiteral | None = Query(None, description="Filter by reading status"),
    author: str | None = Query(None, description="Filter by author name (substring)"),
    limit: int = Query(50, ge=1, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> list[WorkResponse]:
    return await svc.list_works(driver, status=status, author=author, limit=limit, offset=offset)


@router.get("/{work_id}", response_model=WorkResponse)
async def get_work(
    work_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> WorkResponse:
    work = await svc.get_work(driver, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="Work not found")
    return work


@router.post("", response_model=WorkResponse, status_code=201)
async def create_work(
    req: CreateWorkRequest,
    driver: AsyncDriver = Depends(get_neo4j_driver),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> WorkResponse:
    return await svc.create_work(driver, pg_session, req)


@router.patch("/{work_id}", response_model=WorkResponse)
async def update_work(
    work_id: str,
    req: UpdateWorkRequest,
    driver: AsyncDriver = Depends(get_neo4j_driver),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> WorkResponse:
    work = await svc.update_work(driver, pg_session, work_id, req)
    if not work:
        raise HTTPException(status_code=404, detail="Work not found")
    return work
