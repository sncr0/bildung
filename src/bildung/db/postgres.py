from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from bildung.config import Settings


def build_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.postgres_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=10,
        pool_recycle=3600,     # recycle connections after 1 h to avoid stale TCP
        pool_timeout=30,       # raise after 30 s waiting for a connection
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
