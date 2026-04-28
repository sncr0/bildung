"""Work service — business logic for works."""
from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bildung.ids import author_id as _author_id, work_id as _work_id
from bildung.models.api import (
    AuthorSummary as ApiAuthorSummary,
    CollectionSummary,
    CreateWorkRequest,
    UpdateWorkRequest,
    WorkResponse,
)
from bildung.models.domain import Work
from bildung.models.postgres import ReadingEvent
from bildung.repositories.works import WorkRepository

logger = logging.getLogger(__name__)


class WorkService:
    def __init__(self, work_repo: WorkRepository, pg_session: AsyncSession) -> None:
        self._works = work_repo
        self._pg_session = pg_session

    async def list(
        self,
        status: str | None = None,
        author: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WorkResponse]:
        works = await self._works.list(status=status, author=author, limit=limit, offset=offset)
        return [self._work_to_response(w) for w in works]

    async def get(self, work_id: str) -> WorkResponse | None:
        work = await self._works.get(work_id)
        if not work:
            return None
        return self._work_to_response(work)

    async def create(self, req: CreateWorkRequest) -> WorkResponse:
        wid = _work_id(req.title, req.author)
        aid = _author_id(req.author)

        work = await self._works.create(
            work_id=wid,
            title=req.title,
            author_id=aid,
            author_name=req.author,
            status=req.status,
            language_read_in=req.language_read_in,
            date_read=req.date_read,
            density_rating=req.density_rating,
            source_type=req.source_type,
            personal_note=req.personal_note,
            significance=req.significance,
        )

        logger.info("create_work: id=%s title=%r status=%s", wid, req.title, req.status)

        if req.status == "read":
            await self._record_reading_event(wid, "finished", req.date_read)

        return self._work_to_response(work)

    async def update(self, work_id: str, req: UpdateWorkRequest) -> WorkResponse | None:
        current = await self._works.get(work_id)
        if not current:
            return None

        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if not updates:
            return self._work_to_response(current)

        work = await self._works.update(work_id, updates)
        logger.info("update_work: id=%s fields=%s", work_id, list(updates.keys()))

        if req.status == "read" and current.status != "read":
            event_date = req.date_read or current.date_read or str(date.today())
            await self._record_reading_event(work_id, "finished", event_date)

        return self._work_to_response(work) if work else None

    # --- private helpers ---

    async def _record_reading_event(
        self, work_id: str, event_type: str, event_date: str | None,
    ) -> None:
        parsed_date = _parse_date(event_date)
        stmt = insert(ReadingEvent).values(
            id=uuid.uuid4(),
            work_id=uuid.UUID(work_id),
            event_type=event_type,
            event_date=parsed_date,
        )
        await self._pg_session.execute(stmt)
        await self._pg_session.commit()

    @staticmethod
    def _work_to_response(work: Work) -> WorkResponse:
        """Convert domain Work to API WorkResponse."""
        return WorkResponse(
            id=work.id,
            title=work.title,
            status=work.status,
            language_read_in=work.language_read_in,
            date_read=work.date_read,
            density_rating=work.density_rating,
            source_type=work.source_type,
            personal_note=work.personal_note,
            edition_note=work.edition_note,
            significance=work.significance,
            authors=[
                ApiAuthorSummary(id=a.id, name=a.name) for a in work.authors
            ],
            stream_ids=[],  # populated by get_work detail query only
            collections=[
                CollectionSummary(
                    id=c.collection_id,
                    name=c.collection_name,
                    type=c.collection_type,
                    order=c.order,
                )
                for c in work.collections
            ],
        )


def _parse_date(raw: str | None) -> date:
    """Best-effort: '2024', '2024-03', '2024-03-15' -> date. Falls back to today."""
    if not raw:
        return date.today()
    try:
        if len(raw) == 4:
            return date(int(raw), 12, 31)
        if len(raw) == 7:
            y, m = raw.split("-")
            return date(int(y), int(m), 1)
        return date.fromisoformat(raw)
    except (ValueError, AttributeError):
        return date.today()
