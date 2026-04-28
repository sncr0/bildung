"""Authors router — /authors resource."""
from fastapi import APIRouter, Depends, HTTPException, Query

from bildung.dependencies import get_author_service
from bildung.models.api import AuthorResponse
from bildung.services.authors import AuthorService

router = APIRouter(prefix="/authors", tags=["authors"])


@router.get("", response_model=list[AuthorResponse])
async def list_authors(
    limit: int = Query(50, ge=1, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    svc: AuthorService = Depends(get_author_service),
) -> list[AuthorResponse]:
    return await svc.list(limit=limit, offset=offset)


@router.get("/{author_id}", response_model=AuthorResponse)
async def get_author(
    author_id: str,
    svc: AuthorService = Depends(get_author_service),
) -> AuthorResponse:
    author = await svc.get(author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    return author
