"""Base repositories — Neo4j for graph, PostgreSQL for entities."""
from __future__ import annotations

from neo4j import AsyncDriver, Record
from sqlalchemy.ext.asyncio import AsyncSession


class NeoRepository:
    """Base for repositories that talk to Neo4j (graph edges only)."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def _run(self, query: str, **params: object) -> list[Record]:
        async with self._driver.session() as session:
            result = await session.run(query, params)
            return [r async for r in result]

    async def _run_single(self, query: str, **params: object) -> Record | None:
        async with self._driver.session() as session:
            result = await session.run(query, params)
            return await result.single()


class PgRepository:
    """Base for repositories that read/write PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
