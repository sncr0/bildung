"""Collection service — the universal grouping unit (major/minor canon, series, anthology)."""
from __future__ import annotations

import logging

from bildung.ids import collection_id as _collection_id
from bildung.models.api import (
    AuthorSummary as ApiAuthorSummary,
    CollectionDetailResponse,
    CollectionMembershipRequest,
    CollectionResponse,
    CollectionStreamRequest,
    CollectionSummary,
    CreateCollectionRequest,
    UpdateCollectionRequest,
    WorkResponse,
)
from bildung.repositories.collections import CollectionRepository
from bildung.repositories.works import WorkRepository

logger = logging.getLogger(__name__)


class CollectionService:
    def __init__(self, collection_repo: CollectionRepository) -> None:
        self._collections = collection_repo

    async def list(
        self,
        author_id: str | None = None,
        type_: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CollectionResponse]:
        rows = await self._collections.list(
            author_id=author_id, type_=type_, limit=limit, offset=offset
        )
        return [
            CollectionResponse(
                id=r["col"].get("id", ""),
                name=r["col"].get("name", ""),
                description=r["col"].get("description"),
                type=r["col"].get("type", "anthology"),
                author_id=r["col"].get("author_id"),
                work_count=r["work_count"] or 0,
                read_count=r["read_count"] or 0,
            )
            for r in rows
        ]

    async def get(self, coll_id: str) -> CollectionDetailResponse | None:
        data = await self._collections.get_with_works(coll_id)
        if not data:
            return None

        c = data["col"]
        works: list[WorkResponse] = []
        read_count = 0
        for wr in data["works"]:
            col_summary = [{
                "id": coll_id,
                "name": c.get("name", ""),
                "type": c.get("type", ""),
                "order": wr.get("position"),
            }]
            works.append(_raw_to_work_response(
                wr["work"], wr["authors"], wr["stream_ids"], col_summary
            ))
            if wr["work"].get("status") == "read":
                read_count += 1

        return CollectionDetailResponse(
            id=c.get("id", ""),
            name=c.get("name", ""),
            description=c.get("description"),
            type=c.get("type", "anthology"),
            author_id=c.get("author_id"),
            work_count=len(works),
            read_count=read_count,
            works=works,
        )

    async def create(self, req: CreateCollectionRequest) -> CollectionResponse:
        coll_id = _collection_id(req.name)
        collection = await self._collections.create(
            coll_id=coll_id, name=req.name, description=req.description,
            type_=req.type, author_id=req.author_id,
        )
        logger.info("create_collection: id=%s name=%r type=%s", coll_id, req.name, req.type)
        return CollectionResponse(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            type=collection.type,
            author_id=collection.author_id,
            work_count=0,
            read_count=0,
        )

    async def update(self, coll_id: str, req: UpdateCollectionRequest) -> CollectionDetailResponse | None:
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if updates:
            ok = await self._collections.update(coll_id, updates)
            if not ok:
                return None
        return await self.get(coll_id)

    async def delete(self, coll_id: str) -> bool:
        return await self._collections.delete(coll_id)

    async def add_work(self, work_id: str, coll_id: str, req: CollectionMembershipRequest) -> bool:
        return await self._collections.add_work(work_id, coll_id, req.order)

    async def remove_work(self, work_id: str, coll_id: str) -> bool:
        return await self._collections.remove_work(work_id, coll_id)

    async def add_to_stream(self, coll_id: str, stream_id: str, req: CollectionStreamRequest) -> bool:
        return await self._collections.add_to_stream(coll_id, stream_id, req.order)

    async def remove_from_stream(self, coll_id: str, stream_id: str) -> bool:
        return await self._collections.remove_from_stream(coll_id, stream_id)


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
