import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DATE, INTEGER, TEXT, VARCHAR, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ReadingEvent(Base):
    """Immutable log — one row per event (started / finished / abandoned / added_to_list)."""

    __tablename__ = "reading_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    event_date: Mapped[date] = mapped_column(DATE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class XpLedger(Base):
    """Immutable, append-only XP log."""

    __tablename__ = "xp_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    xp_type: Mapped[str] = mapped_column(VARCHAR, nullable=False)  # 'reading' | 'mastery' | 'connection'
    amount: Mapped[Decimal] = mapped_column(nullable=False)
    breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_text: Mapped[str] = mapped_column(TEXT, nullable=False)
    question_type: Mapped[str] = mapped_column(VARCHAR, nullable=False)  # 'comprehension' | 'cross_work' | 'cross_stream'
    related_work_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    related_stream_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    difficulty: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    max_xp: Mapped[Decimal | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quiz_questions.id"), nullable=False
    )
    answer_text: Mapped[str] = mapped_column(TEXT, nullable=False)
    score: Mapped[Decimal] = mapped_column(nullable=False)
    xp_earned: Mapped[Decimal] = mapped_column(nullable=False)
    llm_feedback: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SrsSchedule(Base):
    __tablename__ = "srs_schedule"

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quiz_questions.id"), primary_key=True
    )
    next_due: Mapped[date] = mapped_column(DATE, nullable=False)
    interval_days: Mapped[int] = mapped_column(INTEGER, nullable=False, server_default="1")
    ease_factor: Mapped[Decimal] = mapped_column(nullable=False, server_default="2.5")
    consecutive_correct: Mapped[int] = mapped_column(INTEGER, nullable=False, server_default="0")


# ---------------------------------------------------------------------------
# Entity tables — scalar properties for works, authors, collections, etc.
# ---------------------------------------------------------------------------

class WorkEntity(Base):
    """Work entity — scalar properties stored in PostgreSQL."""
    __tablename__ = "works"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(TEXT, nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR, nullable=False, server_default="to_read")
    language_read_in: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    date_read: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    density_rating: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    source_type: Mapped[str] = mapped_column(VARCHAR, nullable=False, server_default="fiction")
    personal_note: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    edition_note: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    significance: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    page_count: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    year_published: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    original_language: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    original_title: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    openlibrary_id: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    isbn: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuthorEntity(Base):
    __tablename__ = "authors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(TEXT, nullable=False)
    birth_year: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    death_year: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    nationality: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    primary_language: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    openlibrary_id: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CollectionEntity(Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(TEXT, nullable=False)
    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    type: Mapped[str] = mapped_column(VARCHAR, nullable=False, server_default="anthology")
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("authors.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StreamEntity(Base):
    __tablename__ = "streams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(TEXT, nullable=False)
    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    color: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SeriesEntity(Base):
    __tablename__ = "series"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(TEXT, nullable=False)
    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# --- Junction tables ---

class WorkAuthor(Base):
    __tablename__ = "work_authors"

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("works.id"), primary_key=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("authors.id"), primary_key=True
    )


class WorkCollection(Base):
    __tablename__ = "work_collections"

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("works.id"), primary_key=True
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id"), primary_key=True
    )
    order: Mapped[int | None] = mapped_column(INTEGER, nullable=True)


class WorkStream(Base):
    __tablename__ = "work_streams"

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("works.id"), primary_key=True
    )
    stream_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("streams.id"), primary_key=True
    )
    position: Mapped[int | None] = mapped_column(INTEGER, nullable=True)


class CollectionStream(Base):
    __tablename__ = "collection_streams"

    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id"), primary_key=True
    )
    stream_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("streams.id"), primary_key=True
    )
    order: Mapped[int | None] = mapped_column(INTEGER, nullable=True)


class WorkSeries(Base):
    __tablename__ = "work_series"

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("works.id"), primary_key=True
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id"), primary_key=True
    )
    order: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
