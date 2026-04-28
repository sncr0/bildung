# Bildung — Project Conventions

## Stack
- Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), Neo4j Python driver
- Frontend: React + TypeScript, Vite, TailwindCSS, D3.js
- Databases: PostgreSQL 16 + Neo4j 5
- Package management: `uv` only. Never use pip directly.

## Commands
- `uv run uvicorn src.bildung.main:app --reload` — start backend
- `uv run alembic upgrade head` — run PG migrations
- `uv run pytest -v` — run tests
- `cd frontend && npm run dev` — start frontend
- `docker compose up -d` — start Neo4j + PostgreSQL

## Code Standards
- Type hints on all function signatures
- Pydantic v2 models for all request/response validation
- Async database operations (both PG and Neo4j)
- Use `uv add <package>` to add dependencies, never pip
- All config via pydantic-settings, loaded from .env
- Neo4j queries in Cypher, keep them in service functions not inline in routers
- PostgreSQL via SQLAlchemy async, Alembic for migrations

## Architecture Reference
- This project follows patterns from the `finalysis` project (personal finance analytics)
- Similar medallion-style data organization principles
- Similar config management and project structure conventions
- Adapted to a dual-database (Neo4j + PostgreSQL) setup

## Testing
- pytest with pytest-asyncio
- Test XP calculations thoroughly — these are the core game mechanic
- Test Neo4j queries with a test database
