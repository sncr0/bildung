"""Streams router — /streams resource and /works/{id}/streams membership."""
from fastapi import APIRouter, Depends, HTTPException, Query

from bildung.dependencies import get_stream_service
from bildung.models.api import (
    AssignStreamRequest,
    CreateStreamRequest,
    StreamDetailResponse,
    StreamMembershipRequest,
    StreamResponse,
    UpdateStreamRequest,
)
from bildung.services.streams import StreamService

router = APIRouter(tags=["streams"])


# ---------------------------------------------------------------------------
# Stream CRUD  —  /streams
# ---------------------------------------------------------------------------

@router.get("/streams", response_model=list[StreamResponse])
async def list_streams(
    limit: int = Query(50, ge=1, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    svc: StreamService = Depends(get_stream_service),
) -> list[StreamResponse]:
    return await svc.list(limit=limit, offset=offset)


@router.get("/streams/{stream_id}", response_model=StreamDetailResponse)
async def get_stream(
    stream_id: str,
    svc: StreamService = Depends(get_stream_service),
) -> StreamDetailResponse:
    stream = await svc.get(stream_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    return stream


@router.post("/streams", response_model=StreamResponse, status_code=201)
async def create_stream(
    req: CreateStreamRequest,
    svc: StreamService = Depends(get_stream_service),
) -> StreamResponse:
    return await svc.create(req)


@router.patch("/streams/{stream_id}", response_model=StreamDetailResponse)
async def update_stream(
    stream_id: str,
    req: UpdateStreamRequest,
    svc: StreamService = Depends(get_stream_service),
) -> StreamDetailResponse:
    stream = await svc.update(stream_id, req)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    return stream


@router.delete("/streams/{stream_id}", status_code=204)
async def delete_stream(
    stream_id: str,
    svc: StreamService = Depends(get_stream_service),
) -> None:
    deleted = await svc.delete(stream_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Stream not found")


# ---------------------------------------------------------------------------
# Stream membership  —  /works/{work_id}/streams
# ---------------------------------------------------------------------------

@router.put("/works/{work_id}/streams/{stream_id}", status_code=204)
async def add_work_to_stream(
    work_id: str,
    stream_id: str,
    req: StreamMembershipRequest = StreamMembershipRequest(),
    svc: StreamService = Depends(get_stream_service),
) -> None:
    """Idempotent — PUT is safe to call multiple times. Position is optional."""
    ok = await svc.assign_work(work_id, AssignStreamRequest(stream_id=stream_id, position=req.position))
    if not ok:
        raise HTTPException(status_code=404, detail="Work or stream not found")


@router.delete("/works/{work_id}/streams/{stream_id}", status_code=204)
async def remove_work_from_stream(
    work_id: str,
    stream_id: str,
    svc: StreamService = Depends(get_stream_service),
) -> None:
    ok = await svc.remove_work(work_id, stream_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Assignment not found")
