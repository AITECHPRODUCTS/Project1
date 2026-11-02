from __future__ import annotations

from fastapi.testclient import TestClient

from backend import main


def test_content_atomize_persists_reviewable_assets(monkeypatch):
    async def fake_atomize_content(**kwargs):
        return {
            "source_title": kwargs["source_title"],
            "atoms": [{
                "platform": "linkedin",
                "title": "Reviewable LinkedIn draft",
                "content": "A sourced draft. Disclosure: disclose any affiliate relationship.",
                "hook": "A sourced draft",
                "cta": "Verify claims before publishing",
                "affiliate_disclosure": "Disclose any affiliate relationship",
                "source_facts": ["A source fact"],
                "claims_to_verify": ["Verify claims"],
            }],
            "source_urls": kwargs["source_urls"],
            "provider": "test-provider",
            "rag_sources": [],
            "requires_review": True,
            "publishing_started": False,
        }

    monkeypatch.setattr("backend.services.content_atomizer.atomize_content", fake_atomize_content)
    with TestClient(main.app) as client:
        response = client.post("/api/content/atomize", json={
            "source_title": "Source title",
            "source_body": "This is a source body with more than eighty characters, including evidence and context.",
            "platforms": ["linkedin"],
            "source_urls": ["https://example.com/source"],
        })

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["asset_count"] == 1
    assert payload["asset_ids"][0]
    assert payload["requires_review"] is True
    assert payload["publishing_started"] is False

def test_x_thread_endpoint_persists_reviewable_thread_draft(monkeypatch):
    async def fake_atomize_content(**kwargs):
        assert kwargs["platforms"] == ["x_thread"]
        return {
            "source_title": kwargs["source_title"],
            "atoms": [{
                "platform": "x_thread",
                "title": "Reviewable X thread",
                "content": "1/ A source-backed post.\n2/ Disclosure: verify the relationship before posting.",
                "hook": "A source-backed post",
                "cta": "Review the source",
                "affiliate_disclosure": "Disclose any affiliate relationship",
                "source_facts": ["A source fact"],
                "claims_to_verify": ["Verify claims"],
            }],
            "source_urls": kwargs["source_urls"],
            "provider": "test-provider",
            "rag_sources": [],
            "requires_review": True,
            "publishing_started": False,
        }

    monkeypatch.setattr("backend.services.content_atomizer.atomize_content", fake_atomize_content)
    with TestClient(main.app) as client:
        response = client.post("/api/content/atomize", json={
            "source_title": "A source-backed X thread",
            "source_body": (
                "This is a source body with enough detail to build a short thread "
                "and preserve context for the reader. Verify every claim before reuse."
            ),
            "platforms": ["x_thread"],
            "source_urls": ["https://example.com/source"],
        })

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["asset_count"] == 1
    assert payload["atoms"][0]["platform"] == "x_thread"
    assert payload["asset_ids"]
    assert payload["requires_review"] is True
    assert payload["publishing_started"] is False

