# Architecture Improvements — Bildung

> Audit date: 2026-04-15  
> Auditor: L7-level review against finalysis reference patterns  
> Status: in progress

## Executive Summary

The codebase has a solid structural foundation — lifespan-managed AppState, dependency injection, Cypher kept in services — but several issues block production readiness or will cause hard failures at scale. This document lists improvements by priority tier, explains the target architecture, and tracks implementation status.

---

## Target Architecture

```
HTTP request
    │
    ▼
[CORS + Logging Middleware]
    │
    ▼
[Router] — thin; validates input, raises HTTPException, delegates to service
    │
    ▼
[Service] — owns Cypher/SQL; uses explicit transactions; returns Pydantic models
    │
    ├──▶ [Neo4j AsyncDriver] — pool-configured, health-checked at startup
    └──▶ [PostgreSQL AsyncEngine] — pool-configured, health-checked at startup
```

Key invariants:
- **No business logic in routers** — done
- **No DB calls outside services** — done  
- **All list endpoints paginated** — TODO
- **All multi-step writes in explicit transactions** — TODO
- **Connection pools explicitly sized** — TODO
- **Startup fails loud if DBs unreachable** — TODO

---

## Tier 1 — Critical (Breaks at Runtime)

### 1.1 Missing Series API models
**File:** `src/bildung/models/api.py`  
**Issue:** `series.py` service and router both import `CreateSeriesRequest`, `SeriesResponse`, `SeriesDetailResponse`, `UpdateSeriesRequest`, `SeriesMembershipRequest` — none of which exist in `api.py`. Python will `ImportError` on first request that touches the series router.  
**Fix:** Add the five missing Pydantic schemas.  
**Status:** ✅ implemented

### 1.2 Series router never registered
**File:** `src/bildung/main.py`  
**Issue:** `series_router` is imported nowhere and never passed to `app.include_router()`. All `/series` endpoints are dead.  
**Fix:** Import and register in `create_app()`.  
**Status:** ✅ implemented

---

## Tier 2 — High (Production Blocker)

### 2.1 No pagination on list endpoints
**Files:** routers for works, authors, streams, collections, series  
**Issue:** All list endpoints return unbounded result sets. 10 000-work library → full Neo4j scan → OOM or timeout.  
**Fix:** Add `limit: int = 50, offset: int = 0` query params; propagate `SKIP $offset LIMIT $limit` to all Cypher list queries.  
**Status:** ✅ implemented

### 2.2 Connection pool not configured (PostgreSQL)
**File:** `src/bildung/db/postgres.py`  
**Issue:** `create_async_engine` uses SQLAlchemy defaults (`pool_size=5, max_overflow=10`). Under concurrent load the pool saturates and requests queue.  
**Fix:** Explicit `pool_size=20, max_overflow=10, pool_recycle=3600`.  
**Status:** ✅ implemented

### 2.3 Neo4j driver has no pool or timeout config
**File:** `src/bildung/db/neo4j.py`  
**Issue:** Driver created with only auth. No max connection lifetime, no acquisition timeout, no liveness check interval.  
**Fix:** Add `max_connection_lifetime`, `connection_acquisition_timeout`, `liveness_check_timeout`.  
**Status:** ✅ implemented

### 2.4 Startup does not validate DB reachability
**File:** `src/bildung/main.py`  
**Issue:** `AppState.create()` builds objects but never pings the DBs. If Neo4j or Postgres is down, the app starts but fails on the first request with an unhelpful error.  
**Fix:** Run a cheap probe (`RETURN 1` for Neo4j, `SELECT 1` for Postgres) inside lifespan before `yield`.  
**Status:** ✅ implemented

### 2.5 No CORS middleware
**File:** `src/bildung/main.py`  
**Issue:** No `CORSMiddleware` configured. The React frontend (Vite on `:5173`) cannot call the API on `:8000`.  
**Fix:** Add `CORSMiddleware` with configurable origins.  
**Status:** ✅ implemented

### 2.6 Multi-step Neo4j writes are not transactional
**File:** `src/bildung/services/works.py` — `create_work()`  
**Issue:** Three separate `session.run()` calls (ensure author, create work, link author). If the third call fails, orphaned nodes exist with no rollback.  
**Fix:** Wrap with `async with session.begin_transaction() as tx:`, use `tx.run()`.  
**Status:** ✅ implemented

---

## Tier 3 — Medium (Quality / Observability)

### 3.1 Status filter not validated
**File:** `src/bildung/routers/works.py`  
**Issue:** `status` is `str | None` — any value is forwarded to Cypher. Invalid statuses silently return empty lists.  
**Fix:** Use `StatusLiteral | None` in the query param.  
**Status:** ✅ implemented

### 3.2 Missing Neo4j indexes
**File:** `src/bildung/db/neo4j.py`  
**Issue:** No indexes on `Collection.author_id` or `Collection.type`, which are used in every author-detail query. No constraint on `Collection.id` or `Series.id`.  
**Fix:** Add constraints + indexes for Collection and Series.  
**Status:** ✅ implemented

### 3.3 No structured logging
**Files:** all routers, services  
**Issue:** Zero logging. No request trace, no mutation audit trail, no error context beyond the default FastAPI 500 body.  
**Fix:** Add `logging.getLogger(__name__)` per module; add a startup log; log all mutations (create/update/delete) at INFO.  
**Status:** ✅ implemented

### 3.4 Hardcoded namespace UUIDs scattered across files
**Files:** `services/collections.py`, `services/series.py`, `ingestion/reading_list.py`, `ingestion/seed_enrichments.py`  
**Issue:** Each file defines its own `uuid.UUID("c3f5a9e0-...")`. If one diverges, cross-module ID lookups break silently.  
**Fix:** Centralise in `src/bildung/ids.py` — one module, one source of truth.  
**Status:** ✅ implemented

---

## Patterns Borrowed from Finalysis

| Pattern | Finalysis file | Applied in Bildung |
|---------|---------------|-------------------|
| AppState dataclass + factory classmethod | `app_state.py` | already present |
| `create_app(state=)` for test injection | `web/app.py` | already present |
| Stateless dependency functions | `web/dependencies.py` | already present |
| Explicit lifespan + health check | `web/app.py` | `main.py` improved |
| One-module config with validators | `config.py` | `config.py` improved |
| Explicit connection pool sizing | `db/connection.py` | `db/postgres.py` improved |
| Structured logging per module | `db/sync.py` | added across services |
| Hardened invariants (raise, don't skip) | `db/repositories/transactions.py` | transaction boundary fix |
