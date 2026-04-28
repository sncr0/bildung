# Task 5B — OpenLibrary Enrichment Integration

## Kickoff

### Read Before Starting
1. **This spec** (you're reading it)
2. **No next task spec** — this is the final task in the migration. After this, the architecture is clean and ready for Phase 2+ features.
3. **Architecture reference:** `02_target_architecture.md` → data quality goals.
4. **Current OpenLibrary client:** `services/openlibrary.py` — read the `OpenLibraryClient` class and its `search_work()` and `get_work_details()` methods. This client already exists and works. The test in `tests/test_openlibrary.py` proves it.
5. **Enrichment pipeline:** `ingestion/enrichments.py` (created in Task 5A). Your changes extend this pipeline.

### Pre-conditions
- [ ] Task 5A is complete (YAML enrichments working)
- [ ] `uv run python -m bildung.ingestion.enrichments` runs successfully
- [ ] The `OpenLibraryClient` is functional (check `tests/test_openlibrary.py`)
- [ ] Backend starts and all endpoints work

### Lessons from Previous Task
_To be populated by Task 5A implementer._

---

## Spec

### Goal

Wire the existing `OpenLibraryClient` into the enrichment pipeline. After running the enrichment script, works that have OpenLibrary matches get backfilled with: page count, year published, original language, ISBN, cover URL, and OpenLibrary ID. This is the final data quality improvement.

### What This Enables

Richer work detail pages (cover images, page counts for XP calculation, publication years for timeline views). The XP engine needs page count to calculate reading XP — without it, all works get the same base XP regardless of length.

### Files to Modify

```
src/bildung/ingestion/enrichments.py    — Add OpenLibrary enrichment step
```

### Files to Create

None. The `OpenLibraryClient` already exists. The enrichment pipeline already exists. This task wires them together.

### Files NOT to Modify

```
src/bildung/services/openlibrary.py   — DO NOT CHANGE the client.
src/bildung/models/*.py               — DO NOT CHANGE.
src/bildung/repositories/*.py         — DO NOT CHANGE.
src/bildung/services/*.py (other)     — DO NOT CHANGE.
src/bildung/routers/*.py              — DO NOT CHANGE.
src/bildung/ingestion/data/*.yaml     — DO NOT CHANGE (unless adding an OL exclusion list).
```

### Exact Changes

#### `enrichments.py` — Add OpenLibrary Step

Add a new function that:
1. Queries PostgreSQL for works missing `openlibrary_id`
2. For each work, searches OpenLibrary by title + author name
3. If a match is found, updates the work row with enrichment data
4. Rate-limits requests (OpenLibrary asks for max 1 req/second)
5. Logs progress and skipped/failed lookups

```python
import asyncio
import httpx

from bildung.services.openlibrary import OpenLibraryClient


async def apply_openlibrary_enrichments(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Backfill works with OpenLibrary metadata (page count, year, cover, etc.)."""
    
    # Find works without openlibrary_id
    async with session_factory() as pg:
        result = await pg.execute(
            text("""
                SELECT w.id, w.title, a.name AS author_name
                FROM works w
                JOIN work_authors wa ON wa.work_id = w.id
                JOIN authors a ON a.id = wa.author_id
                WHERE w.openlibrary_id IS NULL
                ORDER BY w.title
            """)
        )
        works_to_enrich = result.fetchall()

    if not works_to_enrich:
        logger.info("No works need OpenLibrary enrichment")
        return 0

    logger.info("Found %d works to enrich from OpenLibrary", len(works_to_enrich))

    async with httpx.AsyncClient(
        headers={"User-Agent": "Bildung/0.1 (personal reading tracker)"}
    ) as http:
        ol = OpenLibraryClient(http)
        count = 0

        for row in works_to_enrich:
            work_id = row.id
            title = row.title
            author_name = row.author_name

            try:
                # Search OpenLibrary
                results = await ol.search_work(title, author_name)
                if not results:
                    logger.debug("No OL match for: %s by %s", title, author_name)
                    await asyncio.sleep(1)  # Rate limit
                    continue

                # Take the best match (first result)
                best = results[0]
                ol_key = best.get("key", "")

                # Get detailed info
                details = await ol.get_work_details(ol_key)
                if not details:
                    await asyncio.sleep(1)
                    continue

                # Update work in PostgreSQL
                async with session_factory() as pg:
                    await pg.execute(
                        text("""
                            UPDATE works SET
                                openlibrary_id = :ol_id,
                                page_count = COALESCE(:page_count, page_count),
                                year_published = COALESCE(:year_published, year_published),
                                original_language = COALESCE(:original_language, original_language),
                                isbn = COALESCE(:isbn, isbn),
                                cover_url = COALESCE(:cover_url, cover_url)
                            WHERE id = :id
                        """),
                        {
                            "id": work_id,
                            "ol_id": ol_key,
                            "page_count": details.get("page_count"),
                            "year_published": details.get("year_published"),
                            "original_language": details.get("original_language"),
                            "isbn": details.get("isbn"),
                            "cover_url": details.get("cover_url"),
                        },
                    )
                    await pg.commit()

                count += 1
                logger.info("Enriched: %s (%s)", title, ol_key)

            except Exception:
                logger.exception("Failed to enrich: %s by %s", title, author_name)

            # Rate limit: 1 request per second
            await asyncio.sleep(1)

    return count
```

**Important:** The exact method names and return shapes of `OpenLibraryClient` may differ from what's shown here. Read `services/openlibrary.py` carefully and adapt the code to match the actual interface. Do NOT modify the client to match this spec.

Add the call to `_main()`:

```python
async def _main() -> None:
    # ... existing enrichment steps ...

    # OpenLibrary enrichment (last, because it's slow and external)
    n = await apply_openlibrary_enrichments(session_factory)
    logger.info("OpenLibrary: %d works enriched", n)
```

### Key Design Decisions (and why)

**1. `COALESCE` in UPDATE — don't overwrite existing data.**
If a work already has a `page_count` from a previous enrichment or manual entry, don't overwrite it with null from OpenLibrary. `COALESCE(:new, existing)` keeps the existing value if the new value is null.

**2. Rate limiting with `asyncio.sleep(1)`.**
OpenLibrary's API terms ask for max 1 request per second. For ~200 works, this takes ~3 minutes. That's fine for a one-shot enrichment script.

**3. Skip on failure, don't abort.**
If one work fails (network error, bad response, no match), log and continue. A failed enrichment for one work shouldn't prevent enriching all others.

**4. Search by title + author, not by ISBN or OpenLibrary ID.**
Most works don't have ISBNs or OL IDs yet (that's what we're trying to backfill). Title + author search is the starting point.

**5. First result as "best match."**
OpenLibrary search returns results ranked by relevance. For exact title + author queries, the first result is usually correct. A more sophisticated matching algorithm (Levenshtein distance, multiple result comparison) is over-engineering for this scale.

### DO NOT

1. **Do not modify `OpenLibraryClient`.** Use it as-is. If its interface doesn't match what you need, adapt your enrichment code, not the client.

2. **Do not run OpenLibrary enrichment in parallel.** Serial requests with rate limiting are required by OpenLibrary's terms. Do not use `asyncio.gather()` for OL requests.

3. **Do not cache OpenLibrary responses.** The enrichment runs once (or occasionally). Caching adds complexity for a one-shot operation.

4. **Do not add a "force re-enrich" flag.** If a work has an `openlibrary_id`, it's already been enriched. To re-enrich, set `openlibrary_id = NULL` manually and re-run.

5. **Do not create a separate script for OpenLibrary enrichment.** Add it as a step in the existing `enrichments.py` pipeline.

6. **Do not modify the database schema.** All the columns you need (`openlibrary_id`, `page_count`, `year_published`, etc.) already exist on the `works` table.

7. **Do not enrich authors from OpenLibrary.** Author metadata comes from the YAML files (Task 5A). OpenLibrary author data is often incomplete or inconsistent. Stick with curated YAML data for authors.

### Acceptance Criteria

- [ ] `enrichments.py` has an `apply_openlibrary_enrichments()` function
- [ ] Running `uv run python -m bildung.ingestion.enrichments` includes OpenLibrary enrichment
- [ ] Works without `openlibrary_id` get searched on OpenLibrary
- [ ] Matched works get `page_count`, `year_published`, `cover_url`, etc. backfilled
- [ ] Rate limiting: max 1 request per second to OpenLibrary
- [ ] Failed lookups are logged and skipped, not fatal
- [ ] Script is idempotent (works already enriched are skipped)
- [ ] Backend endpoints reflect enriched data (work detail shows page_count, cover_url)
- [ ] `test_openlibrary.py` still passes

### Verification

```bash
# Run enrichments (includes OpenLibrary step)
uv run python -m bildung.ingestion.enrichments

# Check enrichment results
uv run python -c "
from sqlalchemy import create_engine, text
from bildung.config import load_settings
cfg = load_settings()
engine = create_engine(cfg.pg_dsn.replace('+asyncpg', ''))
with engine.connect() as conn:
    total = conn.execute(text('SELECT count(*) FROM works')).scalar()
    enriched = conn.execute(text('SELECT count(*) FROM works WHERE openlibrary_id IS NOT NULL')).scalar()
    with_pages = conn.execute(text('SELECT count(*) FROM works WHERE page_count IS NOT NULL')).scalar()
    with_cover = conn.execute(text('SELECT count(*) FROM works WHERE cover_url IS NOT NULL')).scalar()
    print(f'Total works: {total}')
    print(f'With OpenLibrary ID: {enriched}')
    print(f'With page count: {with_pages}')
    print(f'With cover URL: {with_cover}')
"

# Existing test still passes
uv run pytest tests/test_openlibrary.py -v

# Backend shows enriched data
curl -s http://localhost:8000/works | python3 -c "
import json, sys
works = json.load(sys.stdin)
with_pages = [w for w in works if w.get('page_count')]
print(f'{len(with_pages)} of {len(works)} works have page counts')
"
```

---

## Handoff

_Fill in after completing this task:_

### Decisions Made
<!-- E.g., "OpenLibrary search returns edition-level data — used first edition for year_published" -->

### Harder Than Expected
<!-- E.g., "OpenLibrary search API returns inconsistent data structures for different works" -->

### Final Notes
<!-- This is the last task. Any remaining issues or future improvements worth noting? -->

### Deviations from Spec
<!-- Did you deviate? Why? -->
