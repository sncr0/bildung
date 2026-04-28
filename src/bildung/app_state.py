"""Application state — created once at startup, stored in app.state.app_state.

Mirrors the AppState / from_config pattern from the finalysis project.
"""
from dataclasses import dataclass

import httpx
from neo4j import AsyncDriver
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from bildung.config import Settings, load_settings
from bildung.db.neo4j import build_driver, init_constraints
from bildung.db.postgres import build_engine, build_session_factory
from bildung.services.openlibrary import OpenLibraryClient


@dataclass
class AppState:
    settings: Settings
    pg_engine: AsyncEngine
    pg_session_factory: async_sessionmaker[AsyncSession]
    neo4j_driver: AsyncDriver
    ol_client: OpenLibraryClient
    _http_client: httpx.AsyncClient  # kept alive for the ol_client

    @classmethod
    async def create(cls, cfg: Settings | None = None) -> "AppState":
        if cfg is None:
            cfg = load_settings()
        engine = build_engine(cfg)
        session_factory = build_session_factory(engine)
        driver = build_driver(cfg)
        await init_constraints(driver)
        http = httpx.AsyncClient(
            headers={"User-Agent": "Bildung/0.1 (personal reading tracker)"}
        )
        ol = OpenLibraryClient(http)
        return cls(
            settings=cfg,
            pg_engine=engine,
            pg_session_factory=session_factory,
            neo4j_driver=driver,
            ol_client=ol,
            _http_client=http,
        )

    async def close(self) -> None:
        await self.pg_engine.dispose()
        await self.neo4j_driver.close()
        await self._http_client.aclose()
