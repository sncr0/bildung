import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from bildung.app_state import AppState
from bildung.routers.authors import router as authors_router
from bildung.routers.collections import router as collections_router
from bildung.routers.series import router as series_router
from bildung.routers.stats import router as stats_router
from bildung.routers.streams import router as streams_router
from bildung.routers.works import router as works_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CORS origins — expand in production via env
# ---------------------------------------------------------------------------
_CORS_ORIGINS = [
    "http://localhost:5173",   # Vite dev server
    "http://localhost:4173",   # Vite preview
    "http://127.0.0.1:5173",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Bildung starting — initialising app state")
    state = await AppState.create()

    # --- startup health checks: fail loud, fail fast ---
    logger.info("Probing PostgreSQL…")
    async with state.pg_session_factory() as pg:
        await pg.execute(text("SELECT 1"))
    logger.info("PostgreSQL OK")

    logger.info("Probing Neo4j…")
    async with state.neo4j_driver.session() as neo:
        await neo.run("RETURN 1")
    logger.info("Neo4j OK")

    app.state.app_state = state
    logger.info("Bildung ready")
    yield
    logger.info("Bildung shutting down")
    await state.close()


def create_app(state: AppState | None = None) -> FastAPI:
    """Create the FastAPI application.

    Pass ``state`` in tests to skip the lifespan and inject fixtures directly,
    mirroring the pattern used in the finalysis project.
    """
    if state is not None:
        app = FastAPI(title="Bildung", description="Personal Literary Intelligence & Gamified Reading System")
        app.state.app_state = state
    else:
        app = FastAPI(
            title="Bildung",
            description="Personal Literary Intelligence & Gamified Reading System",
            lifespan=lifespan,
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(works_router)
    app.include_router(authors_router)
    app.include_router(streams_router)
    app.include_router(collections_router)
    app.include_router(series_router)
    app.include_router(stats_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
