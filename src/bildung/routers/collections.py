"""Collections router — /collections resource and membership endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import AsyncDriver

from bildung.dependencies import get_neo4j_driver
from bildung.models.api import (
    CollectionDetailResponse,
    CollectionMembershipRequest,
    CollectionResponse,
    CollectionStreamRequest,
    CreateCollectionRequest,
    UpdateCollectionRequest,
)
from bildung.services import collections as svc

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
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> list[CollectionResponse]:
    return await svc.list_collections(driver, author_id=author_id, type_=type, limit=limit, offset=offset)


@router.get("/collections/{collection_id}", response_model=CollectionDetailResponse)
async def get_collection(
    collection_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> CollectionDetailResponse:
    c = await svc.get_collection(driver, collection_id)
    if not c:
        raise HTTPException(status_code=404, detail="Collection not found")
    return c


@router.post("/collections", response_model=CollectionResponse, status_code=201)
async def create_collection(
    req: CreateCollectionRequest,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> CollectionResponse:
    return await svc.create_collection(driver, req)


@router.patch("/collections/{collection_id}", response_model=CollectionDetailResponse)
async def update_collection(
    collection_id: str,
    req: UpdateCollectionRequest,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> CollectionDetailResponse:
    c = await svc.update_collection(driver, collection_id, req)
    if not c:
        raise HTTPException(status_code=404, detail="Collection not found")
    return c


@router.delete("/collections/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> None:
    ok = await svc.delete_collection(driver, collection_id)
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
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> None:
    ok = await svc.add_work_to_collection(driver, work_id, collection_id, req)
    if not ok:
        raise HTTPException(status_code=404, detail="Work or collection not found")


@router.delete("/works/{work_id}/collections/{collection_id}", status_code=204)
async def remove_work_from_collection(
    work_id: str,
    collection_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> None:
    ok = await svc.remove_work_from_collection(driver, work_id, collection_id)
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
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> None:
    ok = await svc.add_collection_to_stream(driver, collection_id, stream_id, req)
    if not ok:
        raise HTTPException(status_code=404, detail="Collection or stream not found")


@router.delete("/collections/{collection_id}/streams/{stream_id}", status_code=204)
async def remove_collection_from_stream(
    collection_id: str,
    stream_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> None:
    ok = await svc.remove_collection_from_stream(driver, collection_id, stream_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Assignment not found")
