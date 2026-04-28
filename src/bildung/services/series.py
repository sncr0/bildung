"""Series service — CRUD and work membership."""
from __future__ import annotations

import logging

from bildung.ids import series_id as _series_id
from bildung.models.api import (
    AuthorSummary as ApiAuthorSummary,
    CollectionSummary,
    CreateSeriesRequest,
    SeriesDetailResponse,
    SeriesMembershipRequest,
    SeriesResponse,
    UpdateSeriesRequest,
    WorkResponse,
)
from bildung.repositories.series import SeriesRepository
from bildung.repositories.works import WorkRepository

logger = logging.getLogger(__name__)


class SeriesService:
    def __init__(self, series_repo: SeriesRepository) -> None:
        self._series = series_repo

    async def list(self, limit: int = 50, offset: int = 0) -> list[SeriesResponse]:
        rows = await self._series.list(limit=limit, offset=offset)
        return [
            SeriesResponse(
                id=r["series"].get("id", ""),
                name=r["series"].get("name", ""),
                description=r["series"].get("description"),
                work_count=r["work_count"] or 0,
                read_count=r["read_count"] or 0,
            )
            for r in rows
        ]

    async def get(self, series_id: str) -> SeriesDetailResponse | None:
        data = await self._series.get_with_works(series_id)
        if not data:
            return None

        s = data["series"]
        works: list[WorkResponse] = []
        read_count = 0
        for wr in data["works"]:
            col_entry = [{
                "id": series_id,
                "name": s.get("name", ""),
                "order": wr.get("position"),
            }]
            works.append(_raw_to_work_response(
                wr["work"], wr["authors"], wr["stream_ids"], col_entry
            ))
            if wr["work"].get("status") == "read":
                read_count += 1

        return SeriesDetailResponse(
            id=s.get("id", ""),
            name=s.get("name", ""),
            description=s.get("description"),
            work_count=len(works),
            read_count=read_count,
            works=works,
        )

    async def create(self, req: CreateSeriesRequest) -> SeriesResponse:
        sid = _series_id(req.name)
        series = await self._series.create(sid, req.name, req.description)
        return SeriesResponse(
            id=series.id, name=series.name, description=series.description,
            work_count=0, read_count=0,
        )

    async def update(self, series_id: str, req: UpdateSeriesRequest) -> SeriesDetailResponse | None:
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if updates:
            ok = await self._series.update(series_id, updates)
            if not ok:
                return None
        return await self.get(series_id)

    async def delete(self, series_id: str) -> bool:
        return await self._series.delete(series_id)

    async def assign_work(self, work_id: str, series_id: str, req: SeriesMembershipRequest) -> bool:
        return await self._series.assign_work(work_id, series_id, req.order)

    async def remove_work(self, work_id: str, series_id: str) -> bool:
        return await self._series.remove_work(work_id, series_id)


def _raw_to_work_response(
    work_map: dict,
    authors_list: list[dict],
    stream_ids: list | None,
    collections_list: list | None = None,
) -> WorkResponse:
    domain = WorkRepository._to_work(work_map, authors_list, collections_list)
    return WorkResponse(
        id=domain.id,
        title=domain.title,
        status=domain.status,
        language_read_in=domain.language_read_in,
        date_read=domain.date_read,
        density_rating=domain.density_rating,
        source_type=domain.source_type,
        personal_note=domain.personal_note,
        edition_note=domain.edition_note,
        significance=domain.significance,
        authors=[ApiAuthorSummary(id=a.id, name=a.name) for a in domain.authors],
        stream_ids=stream_ids or [],
        collections=[
            CollectionSummary(
                id=c.collection_id,
                name=c.collection_name,
                type=c.collection_type,
                order=c.order,
            )
            for c in domain.collections
        ],
    )
