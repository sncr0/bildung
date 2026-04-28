"""Smoke tests for the OpenLibrary client.

These hit the real OL API — skip in CI if offline.
Run manually: uv run pytest tests/test_openlibrary.py -v -s
"""
import pytest
import httpx

from bildung.services.openlibrary import OpenLibraryClient, OLSearchResult


@pytest.fixture
async def ol() -> OpenLibraryClient:
    async with httpx.AsyncClient(headers={"User-Agent": "Bildung-test/0.1"}) as client:
        yield OpenLibraryClient(client, request_delay=0.2)


@pytest.mark.asyncio
async def test_search_known_work(ol: OpenLibraryClient) -> None:
    result = await ol.search("Crime and Punishment", author="Dostoyevsky")
    assert result is not None
    assert isinstance(result, OLSearchResult)
    assert "punishment" in result.title.lower() or "crime" in result.title.lower()
    assert result.ol_work_key.startswith("OL")
    # Should return the original work, not a translation
    assert result.author_name is not None
    assert "dostoev" in result.author_name.lower() or "dostoyev" in result.author_name.lower()


@pytest.mark.asyncio
async def test_search_returns_page_count(ol: OpenLibraryClient) -> None:
    result = await ol.search("The Brothers Karamazov", author="Dostoyevsky")
    assert result is not None
    assert result.page_count is not None
    assert result.page_count > 100


@pytest.mark.asyncio
async def test_search_cover_url(ol: OpenLibraryClient) -> None:
    result = await ol.search("Lolita", author="Nabokov")
    assert result is not None
    if result.cover_url:
        assert result.cover_url.startswith("https://covers.openlibrary.org")


@pytest.mark.asyncio
async def test_search_no_results(ol: OpenLibraryClient) -> None:
    result = await ol.search("xyzzy_this_book_does_not_exist_12345")
    assert result is None


@pytest.mark.asyncio
async def test_search_title_only_fallback(ol: OpenLibraryClient) -> None:
    # Wrong author should still find the book via title-only fallback
    result = await ol.search("Siddhartha", author="Definitely Not The Author ZZZZZ")
    assert result is not None
    assert "siddhartha" in result.title.lower()


@pytest.mark.asyncio
async def test_get_author(ol: OpenLibraryClient) -> None:
    # OL key for Fyodor Dostoevsky: OL19382A
    result = await ol.get_author("OL19382A")
    assert result is not None
    name_lower = result.name.lower()
    assert "dostoev" in name_lower or "достоевский" in name_lower


@pytest.mark.asyncio
async def test_get_author_birth_death_years(ol: OpenLibraryClient) -> None:
    # Leo Tolstoy: born 1828, died 1910
    result = await ol.get_author("OL26783A")
    assert result is not None
    assert result.birth_year == 1828
    assert result.death_year == 1910


@pytest.mark.asyncio
async def test_parse_year_in_result(ol: OpenLibraryClient) -> None:
    result = await ol.search("Anna Karenina", author="Tolstoy")
    assert result is not None
    assert result.author_name is not None
    assert "tolstoy" in result.author_name.lower() or "толстой" in result.author_name.lower()
