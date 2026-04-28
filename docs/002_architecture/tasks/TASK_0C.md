# Task 0C — Backend Fixes (IDs, Dead Code, Ports, Config)

## Kickoff

### Read Before Starting
1. **This spec** (you're reading it)
2. **Next task spec:** `TASK_1A.md` — Domain models. That task needs `config.py` to NOT have a module-level singleton, because domain model tests need to import bildung modules without triggering `.env` loading. The config change in this task is a hard prerequisite.
3. **Architecture reference:** `02_target_architecture.md` → "Configuration Target" section. Key principle: explicit construction, no import-time side effects.

### Pre-conditions
- [ ] Task 0B is complete (stats service extracted)
- [ ] Backend starts: `uv run uvicorn src.bildung.main:app --reload`
- [ ] All endpoints respond: `/works`, `/authors`, `/streams`, `/stats`

### Lessons from Previous Task
_To be populated by Task 0B implementer._

---

## Spec

### Goal

Fix 4 small but consequential backend issues that would complicate later tasks if left in place:
1. Stream ID generation inconsistency (random vs. deterministic)
2. Dead code in two files
3. Docker Compose port mismatch
4. Module-level config singleton

These are independent fixes bundled into one task because each is too small to warrant its own spec.

### What This Enables

Task 1A (domain models) needs to import from `bildung.models` and `bildung.ids` without triggering `.env` loading at import time. The config singleton fix is the blocker. The stream ID fix ensures all entities use the same ID scheme before Task 1B creates repositories that assume deterministic IDs.

---

### Fix 1: Stream ID Generation

**File:** `src/bildung/services/streams.py`

**Current:** `create_stream()` at line 170 uses `str(uuid.uuid4())` — a random UUID.
**Target:** Use `ids.stream_id(req.name)` — deterministic, matching the enrichment script.

Change:
```python
# Before (line 170):
stream_id = str(uuid.uuid4())

# After:
from bildung.ids import stream_id as _stream_id
# ...
sid = _stream_id(req.name)
```

Also update the return value and the `CREATE` Cypher to use `sid` instead of `stream_id`.

**Remove** the `import uuid` from `streams.py` if it's no longer used after this change (check — it's used for `uuid.uuid4()` on line 170 and nowhere else in the file).

**Keep** `created_at` as-is (ISO string). Changing temporal storage format is out of scope.

---

### Fix 2: Dead Code Removal

**File:** `src/bildung/services/openlibrary.py`

Delete lines 229-247: the `build_ol_client()` function and `ManagedOLClient` class. These are never called — `AppState.create()` creates the `httpx.AsyncClient` and `OpenLibraryClient` directly.

Verify no imports reference them:
```bash
grep -rn "build_ol_client\|ManagedOLClient" src/ tests/
```

**File:** `src/bildung/ingestion/reading_list.py`

Delete lines 114-130: the `_merge_author()` function. It's never called — the actual implementation is `_upsert_author()` at line 133. The dead function has a `return False  # placeholder` that makes it obviously non-functional.

---

### Fix 3: Docker Compose Port Alignment

**File:** `docker-compose.yml`

**Current:** PostgreSQL maps `5433:5432` (host port 5433, container port 5432).
**Config default:** `postgres_port: int = 5432`.

Change `docker-compose.yml` to map `5432:5432`:

```yaml
ports:
  - "5432:5432"
```

**Important:** If the `.env` file has `POSTGRES_PORT=5433`, update it to `POSTGRES_PORT=5432`. If it has no `POSTGRES_PORT` line, no change needed (the default of 5432 will now be correct).

**Risk:** If other services on the machine use port 5432, this will conflict. But since this is a dev-only Docker setup and the user already runs it, the port is likely free.

---

### Fix 4: Explicit Config Loading

**File:** `src/bildung/config.py`

**Current:**
```python
settings = Settings()  # Line 38 — runs at import time
```

**Target:**
```python
def load_settings(env_file: str = ".env") -> Settings:
    """Load settings from the specified env file. Call explicitly, not at import time."""
    return Settings(_env_file=env_file)
```

Remove the module-level `settings = Settings()` line entirely. Do NOT keep it as a fallback. Do NOT add `settings = load_settings()` as a "convenience."

**Files that import `settings` and need updating:**

1. `src/bildung/app_state.py` (line 7: `from bildung.config import Settings, settings as _default_settings`)
   - Change `AppState.create()` to call `load_settings()` if no config is passed:
   ```python
   from bildung.config import Settings, load_settings

   @classmethod
   async def create(cls, cfg: Settings | None = None) -> "AppState":
       if cfg is None:
           cfg = load_settings()
       # ... rest unchanged
   ```

2. `src/bildung/ingestion/reading_list.py` (line 27: `from bildung.config import settings`)
   - Change `_main()` to call `load_settings()` explicitly:
   ```python
   from bildung.config import load_settings
   # ...
   async def _main() -> None:
       settings = load_settings()
       # ... use settings.neo4j_uri etc.
   ```

3. `src/bildung/ingestion/seed_enrichments.py` (line 11: `from bildung.config import settings`)
   - Same pattern: call `load_settings()` in `main()`.

**Verify no other files import the singleton:**
```bash
grep -rn "from bildung.config import.*settings" src/
```

### DO NOT

1. **Do not change the `Settings` class fields or defaults** (other than removing the singleton). The class itself is fine.

2. **Do not add environment detection logic** (`if os.getenv("ENV") == "test":` etc.). That's over-engineering for a personal project.

3. **Do not create a `settings.py` / `config.py` split.** Keep everything in `config.py`.

4. **Do not touch `dependencies.py`.** It accesses settings through `AppState`, which is already the right pattern.

5. **Do not add `@lru_cache` to `load_settings()`.** Caching config loading sounds smart but makes it impossible to load different configs in tests. The function is called once at startup; performance is irrelevant.

6. **Do not change `docker-compose.yml` beyond the port mapping.** Don't add healthcheck changes, environment variable changes, or volume changes.

7. **Do not change any Cypher queries, API response shapes, or frontend code.** This task is backend plumbing only.

### Acceptance Criteria

- [ ] `services/streams.py` uses `ids.stream_id()` for new streams (no `uuid.uuid4()`)
- [ ] `openlibrary.py` has no `ManagedOLClient` or `build_ol_client`
- [ ] `reading_list.py` has no `_merge_author` function
- [ ] `docker-compose.yml` maps port `5432:5432`
- [ ] `config.py` has no module-level `settings = Settings()` line
- [ ] `config.py` exports a `load_settings()` function
- [ ] `grep -rn "from bildung.config import.*settings" src/` returns zero results (only `load_settings` and `Settings` class imports)
- [ ] Backend starts without errors: `uv run uvicorn src.bildung.main:app --reload`
- [ ] All endpoints still respond correctly: `/works`, `/authors`, `/streams`, `/stats`, `/health`
- [ ] Ingestion scripts still work: `uv run python -m bildung.ingestion.reading_list` (at least starts without import errors — doesn't need to fully run if DB has data)

### Verification

```bash
# Config singleton removed
grep -n "^settings = Settings" src/bildung/config.py
# Expected: 0 results

# load_settings exists
grep -n "def load_settings" src/bildung/config.py
# Expected: 1 result

# No module references old singleton
grep -rn "from bildung.config import.*settings[^_]" src/
# Expected: 0 results (only Settings class and load_settings function imports)

# Stream ID is deterministic
grep -n "uuid.uuid4" src/bildung/services/streams.py
# Expected: 0 results

# Dead code removed
grep -n "ManagedOLClient\|build_ol_client" src/bildung/services/openlibrary.py
# Expected: 0 results
grep -n "_merge_author" src/bildung/ingestion/reading_list.py
# Expected: 0 results

# Port alignment
grep "5433" docker-compose.yml
# Expected: 0 results

# Backend starts
uv run uvicorn src.bildung.main:app --reload &
sleep 3
curl -s http://localhost:8000/health
# Expected: {"status":"ok"}

# Endpoints work
curl -s http://localhost:8000/works | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d)} works')"
curl -s http://localhost:8000/stats | python3 -m json.tool
```

---

## Handoff

_Fill in after completing this task:_

### Decisions Made
- `.env` had `POSTGRES_PORT=5433`; updated to `5432` to match docker-compose (now `5432:5432`).
- Kept the local variable named `stream_id` in `create_stream()` (spec suggested `sid`) — less churn since it's only used 3 times in the same function.
- `openlibrary.py` still imports `field` from dataclasses after removing `ManagedOLClient`; removed it.

### Harder Than Expected
Nothing unexpected. All changes were mechanical.

### Watch Out (for Task 1A)
- `load_settings()` reads `.env` by default. In tests, pass `env_file="..."` or ensure a `.env` exists — or mock Settings directly. It will raise a pydantic validation error if required fields are missing and no `.env` is found.
- `services/openlibrary.py` no longer has `field` imported (removed with `ManagedOLClient`) — don't re-add it.
- `reading_list.py` still has `_merge_author` removed; `_upsert_author` is the real implementation.

### Deviations from Spec
None.
