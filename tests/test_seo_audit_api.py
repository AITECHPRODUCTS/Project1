from __future__ import annotations

from fastapi.testclient import TestClient

from backend import main


def test_seo_audit_endpoint_returns_read_only_audit(monkeypatch):
    async def fake_audit(url: str):
        return {
            "url": url,
            "http_status": 200,
            "title": "Verified input page",
            "checklist_score": 75,
            "checks": [],
            "issues": [],
            "read_only": True,
            "requires_review": True,
            "links_crawled": 0,
            "score_definition": "Rule-based page hygiene checklist only; not a search ranking, traffic, conversion or revenue prediction.",
        }

    monkeypatch.setattr(main, "audit_public_page_service", fake_audit)
    with TestClient(main.app) as client:
        response = client.post("/api/research/seo-audit", json={"url": "https://example.com/page"})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["read_only"] is True
    assert payload["links_crawled"] == 0
    assert payload["url"] == "https://example.com/page"


def test_seo_audit_request_rejects_private_and_non_http_urls():
    with TestClient(main.app) as client:
        response = client.post("/api/research/seo-audit", json={"url": "http://127.0.0.1/metadata"})
    assert response.status_code == 422
