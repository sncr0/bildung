"""Async OpenLibrary API client.

OpenLibrary is a nonprofit — keep requests respectful:
- Default 0.5s delay between calls
- Search by title + author, fall back to title-only if needed
- Return top match (OL ranks by relevance); None if nothing found
"""
import asyncio
import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://openlibrary.org/search.json"
_COVER_URL = "https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
_AUTHOR_URL = "https://openlibrary.org{author_key}.json"

# Fields we actually need — minimises response payload
_SEARCH_FIELDS = ",".join([
    "key",
    "title",
    "author_name",
    "author_key",
    "first_publish_year",
    "number_of_pages_median",
    "isbn",
    "cover_i",
    "language",
])


@dataclass
class OLSearchResult:
    """Normalised result from OpenLibrary search."""
    ol_work_key: str           # e.g. "OL12345W"
    ol_author_key: str | None  # e.g. "OL123A"
    title: str
    author_name: str | None
    year_published: int | None
    page_count: int | None
    isbn: str | None
    cover_url: str | None
    original_language: str | None

    @property
    def openlibrary_id(self) -> str:
        return self.ol_work_key


@dataclass
class OLAuthorResult:
    ol_author_key: str   # e.g. "OL123A"
    name: str
    birth_year: int | None
    death_year: int | None
    nationality: str | None


class OpenLibraryClient:
    """Thin async wrapper around the OpenLibrary Search API."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        request_delay: float = 0.5,
    ) -> None:
        self._client = client
        self._delay = request_delay

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(
        self,
        title: str,
        author: str | None = None,
    ) -> OLSearchResult | None:
        """Search for a work.

        Strategy:
        1. Search with title + author (if provided).
        2. If no hits, retry with title only.
        Returns the best-scoring match, or None.
        """
        if author:
            result = await self._search_raw(title=title, author=author)
            if not result:
                logger.debug("No results for '%s' + '%s', retrying title-only", title, author)
                result = await self._search_raw(title=title)
        else:
            result = await self._search_raw(title=title)

        return result

    async def get_author(self, ol_author_key: str) -> OLAuthorResult | None:
        """Fetch author details by key (e.g. "OL123A")."""
        url = _AUTHOR_URL.format(author_key=f"/authors/{ol_author_key}")
        await asyncio.sleep(self._delay)
        try:
            resp = await self._client.get(url, timeout=10)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Author fetch failed for %s: %s", ol_author_key, exc)
            return None

        data = resp.json()
        return OLAuthorResult(
            ol_author_key=ol_author_key,
            name=data.get("name", ""),
            birth_year=data.get("birth_date", None) and _parse_year(data["birth_date"]),
            death_year=data.get("death_date", None) and _parse_year(data["death_date"]),
            nationality=None,  # OL doesn't expose nationality directly
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _search_raw(
        self,
        title: str,
        author: str | None = None,
    ) -> OLSearchResult | None:
        params: dict[str, str | int] = {
            "title": title,
            "fields": _SEARCH_FIELDS,
            "limit": 10,
        }
        if author:
            params["author"] = author

        await asyncio.sleep(self._delay)
        try:
            resp = await self._client.get(_SEARCH_URL, params=params, timeout=10)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("OpenLibrary search failed for '%s': %s", title, exc)
            return None

        docs = resp.json().get("docs", [])
        if not docs:
            return None

        best = _pick_best(docs, title=title, author=author)
        return _parse_doc(best)


# ------------------------------------------------------------------
# Scoring + parsing helpers (module-level, no state)
# ------------------------------------------------------------------

def _pick_best(docs: list[dict], title: str, author: str | None) -> dict:
    """Score each candidate and return the highest-scoring one."""
    def score(doc: dict) -> float:
        s = 0.0
        doc_title = doc.get("title", "")
        if doc_title.lower() == title.lower():
            s += 2.0
        elif title.lower() in doc_title.lower():
            s += 1.0

        if author:
            author_names = doc.get("author_name", [])
            matched = any(
                author.lower() in name.lower() or name.lower() in author.lower()
                for name in author_names
            )
            if matched:
                s += 2.0  # strong bonus for correct author
            elif author_names:
                s -= 1.0  # penalise confirmed wrong author

        if doc.get("number_of_pages_median"):
            s += 0.5
        if doc.get("first_publish_year"):
            s += 0.5
        return s

    return max(docs, key=score)


def _parse_doc(doc: dict) -> OLSearchResult:
    raw_key: str = doc.get("key", "")  # "/works/OL12345W"
    ol_work_key = raw_key.removeprefix("/works/")

    author_keys: list[str] = doc.get("author_key", [])
    raw_author_key = author_keys[0] if author_keys else None
    ol_author_key = raw_author_key.removeprefix("/authors/") if raw_author_key else None

    author_names: list[str] = doc.get("author_name", [])
    author_name = author_names[0] if author_names else None

    cover_id = doc.get("cover_i")
    cover_url = _COVER_URL.format(cover_id=cover_id) if cover_id else None

    isbns: list[str] = doc.get("isbn", [])
    isbn = isbns[0] if isbns else None

    languages: list[str] = doc.get("language", [])
    original_language = languages[0] if languages else None

    return OLSearchResult(
        ol_work_key=ol_work_key,
        ol_author_key=ol_author_key,
        title=doc.get("title", ""),
        author_name=author_name,
        year_published=doc.get("first_publish_year"),
        page_count=doc.get("number_of_pages_median"),
        isbn=isbn,
        cover_url=cover_url,
        original_language=original_language,
    )


def _parse_year(raw: str) -> int | None:
    """Extract a 4-digit year from a date string like '1844' or 'June 1, 1844'."""
    import re
    m = re.search(r"\b(\d{4})\b", raw)
    return int(m.group(1)) if m else None


# ------------------------------------------------------------------
# Factory — used by FastAPI lifespan and tests
# ------------------------------------------------------------------

def build_ol_client(request_delay: float = 0.5) -> "ManagedOLClient":
    """Return a context-managed client suitable for use in lifespan."""
    return ManagedOLClient(request_delay=request_delay)


@dataclass
class ManagedOLClient:
    """Wraps OpenLibraryClient + httpx.AsyncClient lifecycle."""
    request_delay: float = 0.5
    _http: httpx.AsyncClient = field(init=False)
    _ol: OpenLibraryClient = field(init=False)

    async def __aenter__(self) -> "OpenLibraryClient":
        self._http = httpx.AsyncClient(headers={"User-Agent": "Bildung/0.1 (personal reading tracker)"})
        self._ol = OpenLibraryClient(self._http, request_delay=self.request_delay)
        return self._ol

    async def __aexit__(self, *_) -> None:
        await self._http.aclose()
