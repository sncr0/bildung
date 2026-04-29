"""FastAPI dependency functions — mirrors finalysis web/dependencies.py pattern."""
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from neo4j import AsyncDriver
from sqlalchemy.ext.asyncio import AsyncSession

from bildung.app_state import AppState
from bildung.repositories.authors import AuthorRepository
from bildung.repositories.collections import CollectionRepository
from bildung.repositories.series import SeriesRepository
from bildung.repositories.streams import StreamRepository
from bildung.repositories.works import WorkRepository
from bildung.services.authors import AuthorService
from bildung.services.collections import CollectionService
from bildung.services.openlibrary import OpenLibraryClient
from bildung.services.series import SeriesService
from bildung.services.stats import StatsService
from bildung.services.streams import StreamService
from bildung.services.works import WorkService


def get_app_state(request: Request) -> AppState:
    return request.app.state.app_state


async def get_pg_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    state = get_app_state(request)
    async with state.pg_session_factory() as session:
        yield session


def get_neo4j_driver(request: Request) -> AsyncDriver:
    return get_app_state(request).neo4j_driver


def get_ol_client(request: Request) -> OpenLibraryClient:
    return get_app_state(request).ol_client


# --- Repositories ---

async def get_work_repo(
    request: Request,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> WorkRepository:
    return WorkRepository(pg_session=pg_session, neo4j_driver=get_neo4j_driver(request))


async def get_author_repo(
    request: Request,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> AuthorRepository:
    return AuthorRepository(pg_session=pg_session, neo4j_driver=get_neo4j_driver(request))


async def get_collection_repo(
    request: Request,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> CollectionRepository:
    return CollectionRepository(pg_session=pg_session, neo4j_driver=get_neo4j_driver(request))


async def get_stream_repo(
    request: Request,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> StreamRepository:
    return StreamRepository(pg_session=pg_session, neo4j_driver=get_neo4j_driver(request))


async def get_series_repo(
    request: Request,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> SeriesRepository:
    return SeriesRepository(pg_session=pg_session, neo4j_driver=get_neo4j_driver(request))


# --- Services ---

async def get_work_service(
    request: Request,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> WorkService:
    return WorkService(
        work_repo=WorkRepository(pg_session=pg_session, neo4j_driver=get_neo4j_driver(request)),
        pg_session=pg_session,
    )


async def get_author_service(
    request: Request,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> AuthorService:
    return AuthorService(
        author_repo=AuthorRepository(pg_session=pg_session, neo4j_driver=get_neo4j_driver(request))
    )


async def get_stream_service(
    request: Request,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> StreamService:
    return StreamService(
        stream_repo=StreamRepository(pg_session=pg_session, neo4j_driver=get_neo4j_driver(request))
    )


async def get_collection_service(
    request: Request,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> CollectionService:
    return CollectionService(
        collection_repo=CollectionRepository(pg_session=pg_session, neo4j_driver=get_neo4j_driver(request))
    )


async def get_series_service(
    request: Request,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> SeriesService:
    return SeriesService(
        series_repo=SeriesRepository(pg_session=pg_session, neo4j_driver=get_neo4j_driver(request))
    )


async def get_stats_service(
    request: Request,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> StatsService:
    return StatsService(pg_session=pg_session)
