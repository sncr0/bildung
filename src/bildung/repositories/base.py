"""Base repository — shared Neo4j session helpers."""
from __future__ import annotations

from neo4j import AsyncDriver, Record


class NeoRepository:
    """Base for repositories that talk to Neo4j."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def _run(self, query: str, **params: object) -> list[Record]:
        """Execute a query and return all records."""
        async with self._driver.session() as session:
            result = await session.run(query, params)
            return [r async for r in result]

    async def _run_single(self, query: str, **params: object) -> Record | None:
        """Execute a query and return a single record (or None)."""
        async with self._driver.session() as session:
            result = await session.run(query, params)
            return await result.single()
