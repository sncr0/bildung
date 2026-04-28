"""Stream service — reading paths composed of collections + direct works."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from bildung.ids import stream_id as _stream_id
from bildung.models.api import (
    AssignStreamRequest,
    AuthorSummary as ApiAuthorSummary,
    CollectionDetailResponse,
    CollectionSummary,
    CreateStreamRequest,
    StreamDetailResponse,
    StreamResponse,
    UpdateStreamRequest,
    WorkResponse,
)
from bildung.repositories.streams import StreamRepository
from bildung.repositories.works import WorkRepository

logger = logging.getLogger(__name__)


class StreamService:
    def __init__(self, stream_repo: StreamRepository) -> None:
        self._streams = stream_repo

    async def list(self, limit: int = 50, offset: int = 0) -> list[StreamResponse]:
        rows = await self._streams.list(limit=limit, offset=offset)
        return [
            StreamResponse(
                id=r["stream"].get("id", ""),
                name=r["stream"].get("name", ""),
                description=r["stream"].get("description"),
                color=r["stream"].get("color"),
                created_at=r["stream"].get("created_at", ""),
                work_count=r["work_count"] or 0,
                collection_count=r["collection_count"] or 0,
            )
            for r in rows
        ]

    async def get(self, stream_id: str) -> StreamDetailResponse | None:
        stream = await self._streams.get(stream_id)
        if not stream:
            return None

        col_rows = await self._streams.get_collections_for_stream(stream_id)
        collections: list[CollectionDetailResponse] = []
        for cr in col_rows:
            c = cr["col"]
            work_rows = await self._streams.get_works_for_collection(c["id"])
            col_works: list[WorkResponse] = []
            read_count = 0
            for wr in work_rows:
                col_summary = [{
                    "id": c["id"],
                    "name": c.get("name", ""),
                    "type": c.get("type", ""),
                    "order": wr.get("position"),
                }]
                col_works.append(_raw_to_work_response(
                    wr["work"], wr["authors"], wr["stream_ids"], col_summary
                ))
                if wr["work"].get("status") == "read":
                    read_count += 1
            collections.append(CollectionDetailResponse(
                id=c.get("id", ""),
                name=c.get("name", ""),
                description=c.get("description"),
                type=c.get("type", "anthology"),
                author_id=c.get("author_id"),
                work_count=len(col_works),
                read_count=read_count,
                works=col_works,
            ))

        col_work_ids: set[str] = {w.id for coll in collections for w in coll.works}

        direct_rows = await self._streams.get_direct_works(stream_id)
        direct_works: list[WorkResponse] = []
        for wr in direct_rows:
            if wr["work"].get("id") not in col_work_ids:
                direct_works.append(_raw_to_work_response(wr["work"], wr["authors"], None))

        total_works = sum(c.work_count for c in collections) + len(direct_works)

        return StreamDetailResponse(
            id=stream.id,
            name=stream.name,
            description=stream.description,
            color=stream.color,
            created_at=stream.created_at,
            work_count=total_works,
            collection_count=len(collections),
            collections=collections,
            works=direct_works,
        )

    async def create(self, req: CreateStreamRequest) -> StreamResponse:
        sid = _stream_id(req.name)
        created_at = datetime.now(timezone.utc).isoformat()
        stream = await self._streams.create(
            stream_id=sid, name=req.name, description=req.description,
            color=req.color, created_at=created_at,
        )
        return StreamResponse(
            id=stream.id, name=stream.name, description=stream.description,
            color=stream.color, created_at=stream.created_at,
            work_count=0, collection_count=0,
        )

    async def update(self, stream_id: str, req: UpdateStreamRequest) -> StreamDetailResponse | None:
        existing = await self._streams.get(stream_id)
        if not existing:
            return None
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if updates:
            await self._streams.update(stream_id, updates)
        return await self.get(stream_id)

    async def delete(self, stream_id: str) -> bool:
        return await self._streams.delete(stream_id)

    async def assign_work(self, work_id: str, req: AssignStreamRequest) -> bool:
        return await self._streams.assign_work(work_id, req.stream_id, req.position)

    async def remove_work(self, work_id: str, stream_id: str) -> bool:
        return await self._streams.remove_work(work_id, stream_id)


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
