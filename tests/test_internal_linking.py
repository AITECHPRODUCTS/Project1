from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main
from backend.schemas import InternalLinkingRequest
from backend.services import internal_linking


SOURCE_URL = "https://example.com/guides"
DESTINATION_URL = "https://example.com/sourdough-start"
UNRELATED_URL = "https://example.com/cake-decorating"

SOURCE_HTML = """<html lang="en"><head><title>Beginner bread baking guide</title></head>
<body><main><h1>Bread baking for beginners</h1>
<p>This guide explains sourdough starter feeding, a reliable starter schedule, and bread preparation for home bakers.</p>
<p>Learn how sourdough starter feeding changes fermentation and how to care for your starter.</p>
<a href="/existing">Existing topic guide</a></main></body></html>"""

DESTINATION_HTML = """<html lang="en"><head><title>Sourdough starter feeding schedule</title></head>
<body><main><h1>Sourdough starter feeding schedule</h1>
<p>Learn a consistent sourdough starter feeding process and starter maintenance routine.</p>
<a href="/guides">Beginner guide</a></main></body></html>"""

UNRELATED_HTML = """<html lang="en"><head><title>Cake decorating basics</title></head>
<body><main><h1>Decorate cakes at home</h1>
<p>Use frosting, piping tips, cake boards and simple decoration patterns for birthday cakes.</p>
</main></body></html>"""


async def fake_page_fetch(url: str, *, max_bytes: int, timeout: float):
    assert max_bytes == 1_000_000
    assert timeout == 10.0
    pages = {
        SOURCE_URL: SOURCE_HTML,
        DESTINATION_URL: DESTINATION_HTML,
        UNRELATED_URL: UNRELATED_HTML,
    }
    if url not in pages:
        raise ValueError("fixture page intentionally unavailable")
    return pages[url], "text/html; charset=utf-8", 200


@pytest.mark.asyncio
async def test_recommends_missing_topically_relevant_links_without_following_discovered_urls(monkeypatch):
    fetched = []

    async def track_fetch(url: str, *, max_bytes: int, timeout: float):
        fetched.append(url)
        return await fake_page_fetch(url, max_bytes=max_bytes, timeout=timeout)

    monkeypatch.setattr(internal_linking, "fetch_public_page", track_fetch)
    result = await internal_linking.recommend_internal_links(
        urls=[SOURCE_URL, DESTINATION_URL, UNRELATED_URL],
        max_suggestions_per_page=5,
    )

    suggestions = result["recommendations"]
    assert any(
        row["source_url"] == SOURCE_URL and row["destination_url"] == DESTINATION_URL
        for row in suggestions
    )
    relevant = next(
        row for row in suggestions
        if row["source_url"] == SOURCE_URL and row["destination_url"] == DESTINATION_URL
    )
    assert relevant["relevance_score"] >= 35
    assert {"sourdough", "starter"} <= set(relevant["matched_terms"])
    assert relevant["requires_human_review"] is True
    assert relevant["link_inserted"] is False
    assert result["read_only"] is True
    assert result["automatic_crawl_enabled"] is False
    assert result["discovered_links_followed"] == 0
    assert result["link_inserted"] is False
    assert fetched == [SOURCE_URL, DESTINATION_URL, UNRELATED_URL]


@pytest.mark.asyncio
async def test_does_not_recommend_a_destination_already_linked_from_source(monkeypatch):
    source_html = SOURCE_HTML.replace('<a href="/existing">Existing topic guide</a>',
                                      '<a href="/sourdough-start">Sourdough starter feeding schedule</a>')

    async def fetch(url: str, *, max_bytes: int, timeout: float):
        html = source_html if url == SOURCE_URL else DESTINATION_HTML
        return html, "text/html", 200

    monkeypatch.setattr(internal_linking, "fetch_public_page", fetch)
    result = await internal_linking.recommend_internal_links(urls=[SOURCE_URL, DESTINATION_URL])
    assert not any(
        row["source_url"] == SOURCE_URL and row["destination_url"] == DESTINATION_URL
        for row in result["recommendations"]
    )


@pytest.mark.asyncio
async def test_partial_fetch_failure_is_reported_without_discarding_other_pages(monkeypatch):
    async def fetch(url: str, *, max_bytes: int, timeout: float):
        if url == UNRELATED_URL:
            raise TimeoutError("simulated timeout")
        return await fake_page_fetch(url, max_bytes=max_bytes, timeout=timeout)

    monkeypatch.setattr(internal_linking, "fetch_public_page", fetch)
    result = await internal_linking.recommend_internal_links(
        urls=[SOURCE_URL, DESTINATION_URL, UNRELATED_URL]
    )
    assert result["analyzed_page_count"] == 2
    assert result["failed_page_count"] == 1
    failed = next(page for page in result["pages"] if page["url"] == UNRELATED_URL)
    assert failed["status"] == "failed"
    assert failed["error_type"] == "TimeoutError"
    assert any(row["destination_url"] == DESTINATION_URL for row in result["recommendations"])


@pytest.mark.asyncio
async def test_requires_two_safely_analyzed_html_pages(monkeypatch):
    async def fetch(url: str, *, max_bytes: int, timeout: float):
        if url == DESTINATION_URL:
            raise TimeoutError("page unavailable")
        return SOURCE_HTML, "text/html", 200

    monkeypatch.setattr(internal_linking, "fetch_public_page", fetch)
    with pytest.raises(ValueError, match="At least two supplied pages"):
        await internal_linking.recommend_internal_links(urls=[SOURCE_URL, DESTINATION_URL])


def test_request_requires_public_urls_from_a_single_origin():
    with pytest.raises(ValidationError, match="same public HTTP"):
        InternalLinkingRequest(urls=[SOURCE_URL, "https://other.example/article"])
    with pytest.raises(ValidationError, match="Local/private"):
        InternalLinkingRequest(urls=["https://example.com/a", "http://127.0.0.1/b"])
    with pytest.raises(ValidationError, match="at least two"):
        InternalLinkingRequest(urls=[SOURCE_URL, SOURCE_URL])


def test_internal_link_api_is_read_only_and_reports_reviewable_suggestions(monkeypatch):
    async def fake_recommend(*, urls: list[str], max_suggestions_per_page: int):
        assert urls == [SOURCE_URL, DESTINATION_URL]
        assert max_suggestions_per_page == 5
        return {
            "origin": ["https", "example.com", 443],
            "requested_page_count": 2,
            "analyzed_page_count": 2,
            "failed_page_count": 0,
            "pages": [],
            "recommendation_count": 1,
            "recommendations": [{
                "source_url": SOURCE_URL,
                "destination_url": DESTINATION_URL,
                "suggested_anchor_text": "Sourdough starter feeding schedule",
                "relevance_score": 82,
                "matched_terms": ["sourdough", "starter"],
                "requires_human_review": True,
                "link_inserted": False,
            }],
            "read_only": True,
            "link_inserted": False,
            "automatic_crawl_enabled": False,
            "discovered_links_followed": 0,
        }

    monkeypatch.setattr(main, "recommend_internal_links_service", fake_recommend)
    with TestClient(main.app) as client:
        response = client.post("/api/research/internal-links", json={
            "urls": [SOURCE_URL, DESTINATION_URL],
            "max_suggestions_per_page": 5,
        })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["read_only"] is True
    assert data["link_inserted"] is False
    assert data["recommendation_count"] == 1
    assert data["recommendations"][0]["requires_human_review"] is True
