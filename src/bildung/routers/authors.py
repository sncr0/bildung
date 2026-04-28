"""Authors router — /authors resource."""
from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import AsyncDriver

from bildung.dependencies import get_neo4j_driver
from bildung.models.api import AuthorResponse
from bildung.services import authors as svc

router = APIRouter(prefix="/authors", tags=["authors"])


@router.get("", response_model=list[AuthorResponse])
async def list_authors(
    limit: int = Query(50, ge=1, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> list[AuthorResponse]:
    return await svc.list_authors(driver, limit=limit, offset=offset)


@router.get("/{author_id}", response_model=AuthorResponse)
async def get_author(
    author_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> AuthorResponse:
    author = await svc.get_author(driver, author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    return author
