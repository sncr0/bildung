"""Pydantic schemas for API request/response."""
from typing import Annotated

from pydantic import BaseModel, Field

from bildung.models.neo4j import (
    CollectionTypeLiteral,
    DensityLiteral,
    SignificanceLiteral,
    SourceTypeLiteral,
    StatusLiteral,
)


# ---------------------------------------------------------------------------
# Sub-schemas
# ---------------------------------------------------------------------------

class AuthorSummary(BaseModel):
    id: str
    name: str


class CollectionSummary(BaseModel):
    id: str
    name: str
    type: str
    order: int | None = None


# ---------------------------------------------------------------------------
# Work
# ---------------------------------------------------------------------------

class WorkResponse(BaseModel):
    id: str
    title: str
    status: str
    language_read_in: str | None
    date_read: str | None
    density_rating: str | None
    source_type: str
    personal_note: str | None
    edition_note: str | None
    significance: str | None          # "major" | "minor" | None — kept for display
    authors: list[AuthorSummary]
    stream_ids: list[str] = []
    collections: list[CollectionSummary] = []


class CreateWorkRequest(BaseModel):
    title: Annotated[str, Field(min_length=1)]
    author: Annotated[str, Field(min_length=1)]
    language_read_in: str = "EN"
    status: StatusLiteral = "to_read"
    date_read: str | None = None
    density_rating: DensityLiteral | None = None
    source_type: SourceTypeLiteral = "fiction"
    personal_note: str | None = None
    significance: SignificanceLiteral | None = None


class UpdateWorkRequest(BaseModel):
    status: StatusLiteral | None = None
    density_rating: DensityLiteral | None = None
    language_read_in: str | None = None
    personal_note: str | None = None
    edition_note: str | None = None
    date_read: str | None = None
    source_type: SourceTypeLiteral | None = None
    significance: SignificanceLiteral | None = None


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

class CollectionResponse(BaseModel):
    id: str
    name: str
    description: str | None
    type: str
    author_id: str | None = None
    work_count: int = 0
    read_count: int = 0


class CollectionDetailResponse(CollectionResponse):
    works: list[WorkResponse] = []


class CreateCollectionRequest(BaseModel):
    name: Annotated[str, Field(min_length=1)]
    description: str | None = None
    type: CollectionTypeLiteral = "anthology"
    author_id: str | None = None


class UpdateCollectionRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    type: CollectionTypeLiteral | None = None


class CollectionMembershipRequest(BaseModel):
    """Body for PUT /works/{id}/collections/{collection_id}."""
    order: int | None = None


# ---------------------------------------------------------------------------
# Stream
# ---------------------------------------------------------------------------

class StreamResponse(BaseModel):
    id: str
    name: str
    description: str | None
    color: str | None
    created_at: str
    work_count: int = 0
    collection_count: int = 0


class StreamDetailResponse(StreamResponse):
    collections: list[CollectionDetailResponse] = []
    works: list[WorkResponse] = []   # directly-assigned works not in any collection


class CreateStreamRequest(BaseModel):
    name: Annotated[str, Field(min_length=1)]
    description: str | None = None
    color: str | None = None


class UpdateStreamRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None


class StreamMembershipRequest(BaseModel):
    """Body for PUT /works/{id}/streams/{stream_id}."""
    position: int | None = None


class CollectionStreamRequest(BaseModel):
    """Body for PUT /collections/{id}/streams/{stream_id}."""
    order: int | None = None


# Kept for backward compat
class AssignStreamRequest(BaseModel):
    stream_id: str
    position: int | None = None


# ---------------------------------------------------------------------------
# Author
# ---------------------------------------------------------------------------

class AuthorResponse(BaseModel):
    id: str
    name: str
    birth_year: int | None
    death_year: int | None
    nationality: str | None
    primary_language: str | None
    total_works: int = 0
    read_works: int = 0
    completion_pct: float = 0.0      # based on major_works collection if present
    collections: list[CollectionDetailResponse] = []
    works: list[WorkResponse] = []   # works not in any collection


# ---------------------------------------------------------------------------
# Series
# ---------------------------------------------------------------------------

class SeriesResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    work_count: int = 0
    read_count: int = 0


class SeriesDetailResponse(SeriesResponse):
    works: list[WorkResponse] = []


class CreateSeriesRequest(BaseModel):
    name: Annotated[str, Field(min_length=1)]
    description: str | None = None


class UpdateSeriesRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class SeriesMembershipRequest(BaseModel):
    """Body for PUT /works/{id}/series/{series_id}."""
    order: int | None = None
