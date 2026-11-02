from __future__ import annotations

import pytest

from backend.services import seo_audit


@pytest.mark.asyncio
async def test_auditor_reports_page_hygiene_and_never_claims_search_performance(monkeypatch):
    content = " ".join(["Helpful sourdough guidance for home bakers."] * 90)
    html = f"""<!doctype html>
    <html lang="en"><head>
      <title>Beginner sourdough starter care: practical baking checklist</title>
      <meta name="description" content="Learn how beginner home bakers can care for a sourdough starter with practical, simple steps and helpful troubleshooting guidance.">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <meta name="robots" content="index,follow">
      <link rel="canonical" href="/sourdough/">
    </head><body><main>
      <h1>Sourdough starter care for beginners</h1>
      <h2>Daily feeding checklist</h2>
      <p>{content}</p>
      <img src="/starter.jpg" alt="Jar of sourdough starter">
      <a href="/related-guide">Related guide</a>
      <a href="https://example.org/food-safety">Food-safety reference</a>
    </main></body></html>"""

    async def fake_fetch(url: str, *, max_bytes: int, timeout: float):
        assert url == "https://example.com/sourdough"
        assert max_bytes == 2_000_000
        assert timeout == 12.0
        return html, "text/html; charset=utf-8", 200

    monkeypatch.setattr(seo_audit, "fetch_public_page", fake_fetch)
    result = await seo_audit.audit_public_page("https://example.com/sourdough")

    assert result["http_status"] == 200
    assert result["title"]
    assert result["h1_count"] == 1
    assert result["canonical_url"] == "https://example.com/sourdough/"
    assert result["image_count"] == 1
    assert result["images_missing_alt"] == 0
    assert result["internal_link_count"] == 1
    assert result["external_link_count"] == 1
    assert result["main_content_word_count"] >= 300
    assert result["checklist_score"] > 60
    assert result["links_crawled"] == 0
    assert result["read_only"] is True
    assert "traffic" in result["score_definition"]


@pytest.mark.asyncio
async def test_auditor_flags_missing_metadata_multiple_h1_noindex_and_missing_alt(monkeypatch):
    html = """<html><head><meta name="robots" content="noindex,nofollow"></head>
    <body><main><h1>First heading</h1><h1>Second heading</h1><img src="/missing-alt.png"><h3>Skipped level</h3><p>Short content.</p></main></body></html>"""

    async def fake_fetch(url: str, *, max_bytes: int, timeout: float):
        return html, "text/html", 200

    monkeypatch.setattr(seo_audit, "fetch_public_page", fake_fetch)
    result = await seo_audit.audit_public_page("https://example.com/private-preview")

    ids = {item["id"] for item in result["issues"]}
    assert {"title_present", "meta_description", "h1_count", "indexing_directives", "image_alt_text", "heading_outline"} <= ids
    assert result["indexing_blocked"] is True
    assert result["h1_count"] == 2
    assert result["images_missing_alt"] == 1
    assert result["read_only"] is True


@pytest.mark.asyncio
async def test_auditor_requires_html_content(monkeypatch):
    async def fake_fetch(url: str, *, max_bytes: int, timeout: float):
        return "PDF bytes are not HTML", "application/pdf", 200

    monkeypatch.setattr(seo_audit, "fetch_public_page", fake_fetch)
    with pytest.raises(ValueError, match="requires a public HTML"):
        await seo_audit.audit_public_page("https://example.com/report")


@pytest.mark.asyncio
async def test_auditor_does_not_need_or_fetch_canonical_or_links(monkeypatch):
    calls = []

    async def fake_fetch(url: str, *, max_bytes: int, timeout: float):
        calls.append(url)
        return '<html><head><title>Simple report</title></head><body><h1>Report</h1><a href="/other">Other</a></body></html>', "text/html", 200

    monkeypatch.setattr(seo_audit, "fetch_public_page", fake_fetch)
    await seo_audit.audit_public_page("https://example.com/report")
    assert calls == ["https://example.com/report"]
