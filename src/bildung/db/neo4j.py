from neo4j import AsyncDriver, AsyncGraphDatabase

from bildung.config import Settings

# Uniqueness constraints (also create an implicit index)
_CONSTRAINTS = [
    "CREATE CONSTRAINT work_id IF NOT EXISTS FOR (w:Work) REQUIRE w.id IS UNIQUE",
    "CREATE CONSTRAINT author_id IF NOT EXISTS FOR (a:Author) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT stream_id IF NOT EXISTS FOR (s:Stream) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT collection_id IF NOT EXISTS FOR (c:Collection) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT series_id IF NOT EXISTS FOR (s:Series) REQUIRE s.id IS UNIQUE",
]

# Additional lookup indexes
_INDEXES = [
    "CREATE INDEX work_title IF NOT EXISTS FOR (w:Work) ON (w.title)",
    "CREATE INDEX work_status IF NOT EXISTS FOR (w:Work) ON (w.status)",
    "CREATE INDEX author_name IF NOT EXISTS FOR (a:Author) ON (a.name)",
    # Used in every author-detail query (get_author, list_authors)
    "CREATE INDEX collection_author_id IF NOT EXISTS FOR (c:Collection) ON (c.author_id)",
    "CREATE INDEX collection_type IF NOT EXISTS FOR (c:Collection) ON (c.type)",
]


def build_driver(settings: Settings) -> AsyncDriver:
    return AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
        notifications_min_severity="WARNING",  # suppress INFO-level schema/perf notes
        max_connection_lifetime=3600,           # recycle connections after 1 h
        connection_acquisition_timeout=30,      # raise after 30 s waiting for a slot
        liveness_check_timeout=30,              # probe idle connections every 30 s
    )


async def init_constraints(driver: AsyncDriver) -> None:
    """Idempotently create constraints and indexes. Safe to call on every startup."""
    async with driver.session() as session:
        for stmt in _CONSTRAINTS + _INDEXES:
            await session.run(stmt)
