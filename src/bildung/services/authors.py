"""Author service — list, detail, collections, completion stats."""
from __future__ import annotations

import logging

from bildung.models.api import (
    AuthorResponse,
    AuthorSummary as ApiAuthorSummary,
    CollectionDetailResponse,
    CollectionSummary,
    WorkResponse,
)
from bildung.repositories.authors import AuthorRepository
from bildung.repositories.works import WorkRepository

logger = logging.getLogger(__name__)


class AuthorService:
    def __init__(self, author_repo: AuthorRepository) -> None:
        self._authors = author_repo

    async def list(self, limit: int = 50, offset: int = 0) -> list[AuthorResponse]:
        rows = await self._authors.list(limit=limit, offset=offset)
        return [self._row_to_summary(r) for r in rows]

    async def get(self, author_id: str) -> AuthorResponse | None:
        stats = await self._authors.get_with_stats(author_id)
        if not stats:
            return None

        a = stats["author"]
        author_summary = [{"id": a.get("id", ""), "name": a.get("name", "")}]

        col_rows = await self._authors.get_author_collections(author_id)
        collections: list[CollectionDetailResponse] = []
        for cr in col_rows:
            c = cr["col"]
            entries = cr["work_entries"]
            works: list[WorkResponse] = []
            read_count = 0
            for entry in entries:
                wm = entry.get("w")
                if not wm:
                    continue
                col_summary = [{
                    "id": c.get("id", ""),
                    "name": c.get("name", ""),
                    "type": c.get("type", ""),
                    "order": entry.get("ord"),
                }]
                works.append(_raw_to_work_response(wm, author_summary, [], col_summary))
                if wm.get("status") == "read":
                    read_count += 1
            collections.append(CollectionDetailResponse(
                id=c.get("id", ""),
                name=c.get("name", ""),
                description=c.get("description"),
                type=c.get("type", "anthology"),
                author_id=c.get("author_id"),
                work_count=len(works),
                read_count=read_count,
                works=works,
            ))

        uncollected_rows = await self._authors.get_uncollected_works(author_id)
        uncollected = [
            _raw_to_work_response(wr["work"], author_summary, wr["stream_ids"], wr["cols"])
            for wr in uncollected_rows
        ]

        return _build_author_response(stats, collections, uncollected)

    @staticmethod
    def _row_to_summary(r: dict) -> AuthorResponse:
        a = r["author"]
        total = r["total_works"] or 0
        read = r["read_works"] or 0
        major_total = r["major_total"] or 0
        major_read = r["major_read"] or 0

        if major_total > 0:
            pct = round(major_read / major_total, 4)
        elif total > 0:
            pct = round(read / total, 4)
        else:
            pct = 0.0

        return AuthorResponse(
            id=a.get("id", ""),
            name=a.get("name", ""),
            birth_year=a.get("birth_year"),
            death_year=a.get("death_year"),
            nationality=a.get("nationality"),
            primary_language=a.get("primary_language"),
            total_works=total,
            read_works=read,
            completion_pct=pct,
            collections=[],
            works=[],
        )


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


def _build_author_response(
    stats: dict,
    collections: list[CollectionDetailResponse],
    uncollected: list[WorkResponse],
) -> AuthorResponse:
    a = stats["author"]
    total = stats["total_works"] or 0
    read = stats["read_works"] or 0
    major_total = stats["major_total"] or 0
    major_read = stats["major_read"] or 0

    if major_total > 0:
        pct = round(major_read / major_total, 4)
    elif total > 0:
        pct = round(read / total, 4)
    else:
        pct = 0.0

    return AuthorResponse(
        id=a.get("id", ""),
        name=a.get("name", ""),
        birth_year=a.get("birth_year"),
        death_year=a.get("death_year"),
        nationality=a.get("nationality"),
        primary_language=a.get("primary_language"),
        total_works=total,
        read_works=read,
        completion_pct=pct,
        collections=collections,
        works=uncollected,
    )
