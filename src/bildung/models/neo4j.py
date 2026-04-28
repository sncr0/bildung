"""Pydantic schemas for Neo4j nodes and relationships.

These are not ORM models — they're plain dataclasses/Pydantic models
used to validate and transfer data to/from Neo4j.
"""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


StatusLiteral = Literal["unread", "reading", "read", "abandoned", "to_read"]
DensityLiteral = Literal["light", "moderate", "dense", "grueling"]
SourceTypeLiteral = Literal["primary", "secondary", "fiction"]
SignificanceLiteral = Literal["major", "minor"]
CollectionTypeLiteral = Literal["major_works", "minor_works", "series", "anthology"]


class WorkNode(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    title: str
    original_title: str | None = None
    year_published: int | None = None
    page_count: int | None = None
    original_language: str | None = None
    openlibrary_id: str | None = None
    isbn: str | None = None
    status: StatusLiteral = "read"
    date_read: str | None = None          # ISO date string, year-only ok ("2024")
    density_rating: DensityLiteral | None = None
    language_read_in: str | None = None   # "EN", "NL", "FR", "DE", …
    source_type: SourceTypeLiteral = "fiction"
    personal_note: str | None = None
    edition_note: str | None = None
    cover_url: str | None = None
    significance: SignificanceLiteral | None = None


class AuthorNode(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    birth_year: int | None = None
    death_year: int | None = None
    nationality: str | None = None
    primary_language: str | None = None
    openlibrary_id: str | None = None


class StreamNode(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    description: str | None = None
    color: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CollectionNode(BaseModel):
    """A named grouping of works: major/minor canon, series, anthology."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    description: str | None = None
    type: str = "anthology"          # CollectionTypeLiteral
    author_id: str | None = None     # owning author, if applicable
