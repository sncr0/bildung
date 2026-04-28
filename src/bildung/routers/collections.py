"""Collections router — /collections resource and membership endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query

from bildung.dependencies import get_collection_service
from bildung.models.api import (
    CollectionDetailResponse,
    CollectionMembershipRequest,
    CollectionResponse,
    CollectionStreamRequest,
    CreateCollectionRequest,
    UpdateCollectionRequest,
)
from bildung.services.collections import CollectionService

router = APIRouter(tags=["collections"])


# ---------------------------------------------------------------------------
# Collection CRUD  —  /collections
# ---------------------------------------------------------------------------

@router.get("/collections", response_model=list[CollectionResponse])
async def list_collections(
    author_id: str | None = None,
    type: str | None = None,
    limit: int = Query(50, ge=1, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    svc: CollectionService = Depends(get_collection_service),
) -> list[CollectionResponse]:
    return await svc.list(author_id=author_id, type_=type, limit=limit, offset=offset)


@router.get("/collections/{collection_id}", response_model=CollectionDetailResponse)
async def get_collection(
    collection_id: str,
    svc: CollectionService = Depends(get_collection_service),
) -> CollectionDetailResponse:
    c = await svc.get(collection_id)
    if not c:
        raise HTTPException(status_code=404, detail="Collection not found")
    return c


@router.post("/collections", response_model=CollectionResponse, status_code=201)
async def create_collection(
    req: CreateCollectionRequest,
    svc: CollectionService = Depends(get_collection_service),
) -> CollectionResponse:
    return await svc.create(req)


@router.patch("/collections/{collection_id}", response_model=CollectionDetailResponse)
async def update_collection(
    collection_id: str,
    req: UpdateCollectionRequest,
    svc: CollectionService = Depends(get_collection_service),
) -> CollectionDetailResponse:
    c = await svc.update(collection_id, req)
    if not c:
        raise HTTPException(status_code=404, detail="Collection not found")
    return c


@router.delete("/collections/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: str,
    svc: CollectionService = Depends(get_collection_service),
) -> None:
    ok = await svc.delete(collection_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Collection not found")


# ---------------------------------------------------------------------------
# Work membership  —  /works/{work_id}/collections
# ---------------------------------------------------------------------------

@router.put("/works/{work_id}/collections/{collection_id}", status_code=204)
async def add_work_to_collection(
    work_id: str,
    collection_id: str,
    req: CollectionMembershipRequest = CollectionMembershipRequest(),
    svc: CollectionService = Depends(get_collection_service),
) -> None:
    ok = await svc.add_work(work_id, collection_id, req)
    if not ok:
        raise HTTPException(status_code=404, detail="Work or collection not found")


@router.delete("/works/{work_id}/collections/{collection_id}", status_code=204)
async def remove_work_from_collection(
    work_id: str,
    collection_id: str,
    svc: CollectionService = Depends(get_collection_service),
) -> None:
    ok = await svc.remove_work(work_id, collection_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Membership not found")


# ---------------------------------------------------------------------------
# Stream assignment  —  /collections/{collection_id}/streams
# ---------------------------------------------------------------------------

@router.put("/collections/{collection_id}/streams/{stream_id}", status_code=204)
async def add_collection_to_stream(
    collection_id: str,
    stream_id: str,
    req: CollectionStreamRequest = CollectionStreamRequest(),
    svc: CollectionService = Depends(get_collection_service),
) -> None:
    ok = await svc.add_to_stream(collection_id, stream_id, req)
    if not ok:
        raise HTTPException(status_code=404, detail="Collection or stream not found")


@router.delete("/collections/{collection_id}/streams/{stream_id}", status_code=204)
async def remove_collection_from_stream(
    collection_id: str,
    stream_id: str,
    svc: CollectionService = Depends(get_collection_service),
) -> None:
    ok = await svc.remove_from_stream(collection_id, stream_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Assignment not found")
