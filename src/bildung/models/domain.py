"""Core domain models — the internal contract for repositories and services.

These models represent the domain entities independent of any database or API format.
Repositories return them. Services work with them. API schemas convert to/from them.

Rules:
- No SQLAlchemy imports
- No Neo4j driver imports
- No FastAPI imports
- Literal types come from models/neo4j.py (the canonical source)
"""
from __future__ import annotations

from pydantic import BaseModel

from bildung.models.neo4j import (
    CollectionTypeLiteral,
    DensityLiteral,
    SignificanceLiteral,
    SourceTypeLiteral,
    StatusLiteral,
)


class AuthorSummary(BaseModel):
    """Minimal author reference embedded in other models."""
    id: str
    name: str


class CollectionMembership(BaseModel):
    """A work's membership in a collection, with optional ordering."""
    collection_id: str
    collection_name: str
    collection_type: CollectionTypeLiteral
    order: int | None = None


class Work(BaseModel):
    """A literary work — the central entity of the system."""
    id: str
    title: str
    status: StatusLiteral = "to_read"
    language_read_in: str | None = None
    date_read: str | None = None
    density_rating: DensityLiteral | None = None
    source_type: SourceTypeLiteral = "fiction"
    personal_note: str | None = None
    edition_note: str | None = None
    significance: SignificanceLiteral | None = None
    # Enrichment fields (from OpenLibrary)
    page_count: int | None = None
    year_published: int | None = None
    original_language: str | None = None
    original_title: str | None = None
    openlibrary_id: str | None = None
    isbn: str | None = None
    cover_url: str | None = None
    # Relationships (populated by repository when needed)
    authors: list[AuthorSummary] = []
    collections: list[CollectionMembership] = []


class Author(BaseModel):
    """A literary author."""
    id: str
    name: str
    birth_year: int | None = None
    death_year: int | None = None
    nationality: str | None = None
    primary_language: str | None = None
    openlibrary_id: str | None = None


class Collection(BaseModel):
    """A named grouping of works (major works, minor works, series, anthology)."""
    id: str
    name: str
    description: str | None = None
    type: CollectionTypeLiteral = "anthology"
    author_id: str | None = None


class Stream(BaseModel):
    """A personal reading path — a curated intellectual storyline."""
    id: str
    name: str
    description: str | None = None
    color: str | None = None
    created_at: str = ""


class Series(BaseModel):
    """An ordered series of works (e.g., The Sea of Fertility tetralogy)."""
    id: str
    name: str
    description: str | None = None
