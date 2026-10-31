from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from backend.schemas import ContentAtomizeRequest
from backend.services import content_atomizer


@pytest.mark.asyncio
async def test_content_atomizer_generates_platform_specific_drafts_and_preserves_disclosure(monkeypatch):
    source_body = (
        "Teams can reduce manual review time by documenting repeatable steps. "
        "A checklist helps reviewers confirm the same requirements each time. "
        "Measure outcomes before making performance claims."
    )
    requested = ["linkedin", "x"]
    atoms = [
        {
            "platform": platform,
            "title": f"Source-led {platform} draft",
            "content": f"Source-led content for {platform}.",
            "hook": "Teams can reduce manual review time by documenting repeatable steps.",
            "cta": "Measure outcomes before making performance claims.",
            "source_facts": ["Teams can reduce manual review time by documenting repeatable steps."],
            "claims_to_verify": ["Verify any time-saving claim."],
        }
        for platform in requested
    ]

    async def fake_complete(*args, **kwargs):
        return {"text": json.dumps({"atoms": atoms}), "provider": "test-llm", "sources": []}

    monkeypatch.setattr(content_atomizer.llm_service, "complete", fake_complete)
    result = await content_atomizer.atomize_content(
        source_title="Repeatable review",
        source_body=source_body,
        platforms=requested,
        source_urls=["https://example.com/source"],
    )

    assert [atom["platform"] for atom in result["atoms"]] == requested
    assert result["provider"] == "test-llm"
    assert all("commercial relationship" in atom["content"].lower() for atom in result["atoms"])
    assert result["atoms"][0]["source_facts"] == [
        "Teams can reduce manual review time by documenting repeatable steps."
    ]
    assert result["requires_review"] is True
    assert result["publishing_started"] is False


@pytest.mark.asyncio
async def test_content_atomizer_uses_deterministic_fallback_when_llm_returns_invalid_json(monkeypatch):
    async def fake_complete(*args, **kwargs):
        return {"text": "not valid JSON", "provider": "test-provider", "sources": []}

    monkeypatch.setattr(content_atomizer.llm_service, "complete", fake_complete)
    result = await content_atomizer.atomize_content(
        source_title="Source title",
        source_body="A source sentence with a measurable claim. A second source sentence gives context.",
        platforms=["blog", "tiktok"],
    )

    assert result["provider"] == "test-provider"
    assert len(result["atoms"]) == 2
    assert all(atom["content"] for atom in result["atoms"])
    assert all("Disclosure:" in atom["content"] for atom in result["atoms"])
    assert result["requires_review"] is True


@pytest.mark.asyncio
async def test_content_atomizer_falls_back_when_provider_raises(monkeypatch):
    async def failing_complete(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(content_atomizer.llm_service, "complete", failing_complete)
    result = await content_atomizer.atomize_content(
        source_title="Source title",
        source_body="A source sentence with enough context for content generation. A second sentence adds detail.",
        platforms=["reddit"],
    )

    assert result["provider"] == "deterministic_fallback"
    assert result["atoms"][0]["platform"] == "reddit"


@pytest.mark.asyncio
async def test_content_atomizer_rejects_unsupported_platform_and_short_source():
    with pytest.raises(ValueError, match="Unsupported"):
        await content_atomizer.atomize_content(
            source_title="Source title",
            source_body="A sufficiently long source body " * 5,
            platforms=["unknown"],
        )
    with pytest.raises(ValueError, match="80 characters"):
        await content_atomizer.atomize_content(
            source_title="Source title",
            source_body="too short",
            platforms=["linkedin"],
        )

@pytest.mark.parametrize(
    "source_url",
    [
        "javascript:alert(1)",
        "https://user:password@example.com/source",
        "http://127.0.0.1/metadata",
        "http://10.1.2.3/private",
        "http://[::1]/private",
        "http://localhost/admin",
        "https://internal.local/source",
    ],
)
def test_content_atomizer_rejects_unsafe_source_reference_urls(source_url: str):
    with pytest.raises(ValidationError):
        ContentAtomizeRequest(
            source_title="Grounding test source",
            source_body=(
                "This source body is long enough to satisfy the minimum length "
                "while providing context for a content draft and evidence review."
            ),
            platforms=["linkedin"],
            source_urls=[source_url],
        )

@pytest.mark.asyncio
async def test_x_thread_posts_are_numbered_disclosed_and_limited_to_280_characters(monkeypatch):
    long_post = " ".join(["evidence"] * 90)

    async def fake_complete(*args, **kwargs):
        return {
            "text": json.dumps({"atoms": [{
                "platform": "x_thread",
                "title": "Source-backed thread",
                "content": f"1/ {long_post}\n\nDisclosure: old model-generated disclosure",
                "hook": "Source hook",
                "cta": "Review the source",
                "source_facts": ["Teams need evidence"],
                "claims_to_verify": ["Check source wording"],
            }]}),
            "provider": "test-llm",
            "sources": [],
        }

    monkeypatch.setattr(content_atomizer.llm_service, "complete", fake_complete)
    result = await content_atomizer.atomize_content(
        source_title="Source-backed thread",
        source_body=(
            "Teams should keep source notes. A second fact needs review. "
            "Use evidence before making a claim. This final sentence provides context."
        ),
        platforms=["x_thread"],
    )
    atom = result["atoms"][0]
    posts = atom["content"].splitlines()

    assert atom["platform"] == "x_thread"
    assert len(posts) >= 3
    assert all(len(post) <= 280 for post in posts)
    assert [post.split("/", 1)[0] for post in posts] == [str(i) for i in range(1, len(posts) + 1)]
    assert posts[-1].startswith(f"{len(posts)}/ Disclosure:")
    assert result["requires_review"] is True
    assert result["publishing_started"] is False


@pytest.mark.asyncio
async def test_x_thread_deterministic_fallback_is_numbered_and_disclosure_bearing(monkeypatch):
    async def invalid_json(*args, **kwargs):
        return {"text": "not JSON", "provider": "test-provider", "sources": []}

    monkeypatch.setattr(content_atomizer.llm_service, "complete", invalid_json)
    result = await content_atomizer.atomize_content(
        source_title="Source-grounded topic",
        source_body=(
            "The first source fact explains the main topic. "
            "A second source fact gives the next step. "
            "A third fact provides context for readers."
        ),
        platforms=["x_thread"],
    )
    posts = result["atoms"][0]["content"].splitlines()

    assert posts[0].startswith("1/ ")
    assert posts[-1].startswith(f"{len(posts)}/ Disclosure:")
    assert all(len(post) <= 280 for post in posts)
    assert "Disclosure:" in posts[-1]
    assert result["provider"] == "test-provider"

