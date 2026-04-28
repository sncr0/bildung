"""FastAPI dependency functions — mirrors finalysis web/dependencies.py pattern."""
from collections.abc import AsyncGenerator

from fastapi import Request
from neo4j import AsyncDriver
from sqlalchemy.ext.asyncio import AsyncSession

from bildung.app_state import AppState
from bildung.services.openlibrary import OpenLibraryClient


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
