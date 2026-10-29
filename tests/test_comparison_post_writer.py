from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base
from backend.models import AuditLog, ContentAsset, Workspace
from backend.schemas import ComparisonPostRequest
from backend.services import comparison_post_writer as comparison_service


def valid_payload(**overrides):
    data = {
        "topic": "Analytics products comparison",
        "audience": "Small affiliate publishers",
        "products": [
            {"name": "Alpha", "facts": {"Price": "$20", "Integrations": "Email"}, "source_urls": ["https://vendor.example/alpha"]},
            {"name": "Beta", "facts": {"Price": "$35"}, "source_urls": ["https://vendor.example/beta"]},
        ],
        "decision_criteria": ["Price", "Integrations", "Support"],
        "affiliate_disclosure": "Disclosure: I may earn a commission from qualifying purchases.",
        "minimum_words": 500,
    }
    data.update(overrides)
    return data


def test_comparison_request_requires_distinct_products_and_safe_https_source_urls():
    payload = ComparisonPostRequest(**valid_payload())
    assert [product.name for product in payload.products] == ["Alpha", "Beta"]
    with pytest.raises(ValidationError):
        ComparisonPostRequest(**valid_payload(products=[
            {"name": "Alpha", "facts": {"Price": "$20"}},
            {"name": " alpha ", "facts": {"Price": "$35"}},
        ]))
    with pytest.raises(ValidationError):
        ComparisonPostRequest(**valid_payload(products=[
            {"name": "Alpha", "facts": {"Price": "$20"}, "source_urls": ["http://vendor.example/alpha"]},
            {"name": "Beta", "facts": {"Price": "$35"}},
        ]))

    with pytest.raises(ValidationError, match="credential-like query parameters"):
        ComparisonPostRequest(**valid_payload(products=[
            {"name": "Alpha", "facts": {"Price": "$20"}, "source_urls": ["https://vendor.example/alpha?api_key=DO_NOT_STORE"]},
            {"name": "Beta", "facts": {"Price": "$35"}},
        ]))
    with pytest.raises(ValidationError):
        ComparisonPostRequest(**valid_payload(products=[
            {"name": "Alpha", "facts": {"Price": "$20"}, "source_urls": ["https://127.0.0.1/private"]},
            {"name": "Beta", "facts": {"Price": "$35"}},
        ]))

    with pytest.raises(ValidationError):
        ComparisonPostRequest(**valid_payload(products=[
            {"name": "Alpha", "facts": {"Price": "$20"}, "source_urls": [f"https://vendor.example/a{i}" for i in range(6)]},
            {"name": "Beta", "facts": {"Price": "$35"}, "source_urls": [f"https://vendor.example/b{i}" for i in range(6)]},
        ]))


@pytest.mark.asyncio
async def test_comparison_writer_fetches_bounded_sources_and_matches_only_product_scoped_exact_text(monkeypatch):
    observed = {"source_fetches": [], "prompt": ""}

    async def fake_fetch(url, *, max_bytes, timeout):
        observed["source_fetches"].append((url, max_bytes, timeout))
        if url.endswith("/alpha"):
            body = "<html><head><title>Alpha pricing</title></head><body><nav>menu</nav><p>Product Alpha costs $20 and includes Email integrations.</p><script>secretClaim()</script></body></html>"
        else:
            body = "<html><head><title>Beta product</title></head><body><p>Product Beta analytics service. Contact the vendor for current pricing.</p></body></html>"
        return body, "text/html; charset=utf-8", 200

    async def fake_complete(system_prompt, user_prompt, **kwargs):
        observed["prompt"] = user_prompt
        return {
            "text": '<p onclick="steal()">Compare choices by fit.</p><script>alert(1)</script>'
                    '<a href="javascript:alert(2)" onclick="steal()">unsafe link</a>',
            "sources": [],
            "provider": "test-model",
        }

    monkeypatch.setattr(comparison_service, "fetch_public_page", fake_fetch)
    monkeypatch.setattr(comparison_service.llm_service, "complete", fake_complete)
    request = ComparisonPostRequest(**valid_payload())
    result = await comparison_service.build_comparison_post(
        topic=request.topic,
        audience=request.audience,
        products=[item.model_dump() for item in request.products],
        decision_criteria=request.decision_criteria,
        affiliate_disclosure=request.affiliate_disclosure,
        minimum_words=request.minimum_words,
    )
    assert len(observed["source_fetches"]) == 2
    assert all(max_bytes == 1_000_000 and timeout == 12.0 for _, max_bytes, timeout in observed["source_fetches"])
    assert "untrusted reference data" in observed["prompt"]
    assert "source_snapshots" in observed["prompt"] and "deterministic_fact_evidence" in observed["prompt"]
    assert "Alpha" in observed["prompt"] and "Beta" in observed["prompt"]
    assert "<script" not in result["html"].lower()
    assert "onclick=" not in result["html"].lower()
    assert "javascript:" not in result["html"].lower()
    assert result["html"].index('<p class="affiliate-disclosure"') < result["html"].index("<h1>")
    assert "$20" in result["html"] and "$35" in result["html"]
    assert "Not supplied — verify" in result["html"]
    assert "Fetched source snapshots and provenance" in result["html"]
    assert result["unknown_fact_count"] >= 1
    assert result["evidence_status"] == "public_snapshot_captured_not_fact_verified"
    assert result["product_facts_independently_verified"] is False
    assert result["external_product_sources_fetched"] is True
    assert result["publishing_started"] is False
    assert result["provider_write_access_verified"] is False
    assert result["provider"] == "test-model"
    assert [snapshot["status"] for snapshot in result["source_snapshots"]] == ["fetched", "fetched"]
    assert all(len(snapshot["excerpt_sha256"]) == 64 for snapshot in result["source_snapshots"])
    assert "secretClaim" not in result["source_snapshots"][0]["excerpt"]
    matches = {(item["product"], item["fact_name"]): item for item in result["fact_evidence"]}
    assert matches[("Alpha", "Price")]["evidence_status"] == "exact_text_observed"
    assert matches[("Alpha", "Integrations")]["exact_text_match"] is True
    assert matches[("Beta", "Price")]["evidence_status"] == "exact_text_not_found"
    assert result["evidence_summary"]["source_snapshots_fetched"] == 2
    assert result["evidence_summary"]["exact_text_match_count"] == 2
    assert result["evidence_summary"]["exact_text_not_found_count"] == 1
    assert result["source_urls"] == ["https://vendor.example/alpha", "https://vendor.example/beta"]


@pytest.mark.asyncio
async def test_comparison_writer_rejects_credential_query_before_network(monkeypatch):
    fetched = []

    async def should_not_fetch(url, *, max_bytes, timeout):
        fetched.append(url)
        return "<html><body>not expected</body></html>", "text/html", 200

    monkeypatch.setattr(comparison_service, "fetch_public_page", should_not_fetch)
    products = [
        {"name": "Alpha", "facts": {"Price": "$20"}, "source_urls": ["https://vendor.example/alpha?token=DO_NOT_STORE"]},
        {"name": "Beta", "facts": {"Price": "$35"}, "source_urls": ["https://vendor.example/beta"]},
    ]
    with pytest.raises(ValueError, match="credential-like query parameters"):
        await comparison_service.build_comparison_post(
            topic="Analytics products comparison",
            audience="Small affiliate publishers",
            products=products,
            decision_criteria=["Price"],
            affiliate_disclosure="Disclosure: I may earn a commission from qualifying purchases.",
            minimum_words=500,
        )
    assert fetched == []


@pytest.mark.asyncio
async def test_comparison_writer_does_not_persist_transport_tokens(monkeypatch):
    called = []

    async def leaking_error_fetch(url, *, max_bytes, timeout):
        called.append(url)
        raise RuntimeError("request failed for https://vendor.example/alpha?token=SUPER_SECRET_VALUE")

    async def fake_complete(system_prompt, user_prompt, **kwargs):
        return {"text": "<p>Review the supplied options.</p>", "sources": [], "provider": "test-model"}

    monkeypatch.setattr(comparison_service, "fetch_public_page", leaking_error_fetch)
    monkeypatch.setattr(comparison_service.llm_service, "complete", fake_complete)
    products = [
        {"name": "Alpha", "facts": {"Price": "$20"}, "source_urls": ["https://vendor.example/alpha"]},
        {"name": "Beta", "facts": {"Price": "$35"}, "source_urls": ["https://vendor.example/beta"]},
    ]
    result = await comparison_service.build_comparison_post(
        topic="Analytics products comparison",
        audience="Small affiliate publishers",
        products=products,
        decision_criteria=["Price"],
        affiliate_disclosure="Disclosure: I may earn a commission from qualifying purchases.",
        minimum_words=500,
    )
    assert len(called) == 2
    assert "SUPER_SECRET_VALUE" not in json.dumps(result)
    assert all("Public source fetch failed" in source["detail"] for source in result["source_snapshots"])
    assert result["product_facts_independently_verified"] is False
    assert result["publishing_started"] is False


@pytest.mark.asyncio
async def test_comparison_writer_keeps_fetch_failures_explicit_and_never_marks_facts_verified(monkeypatch):
    async def failed_fetch(url, *, max_bytes, timeout):
        raise ValueError("redirect not followed")

    async def fake_complete(system_prompt, user_prompt, **kwargs):
        return {"text": "<p>Review the supplied options.</p>", "sources": [], "provider": "test-model"}

    monkeypatch.setattr(comparison_service, "fetch_public_page", failed_fetch)
    monkeypatch.setattr(comparison_service.llm_service, "complete", fake_complete)
    request = ComparisonPostRequest(**valid_payload())
    result = await comparison_service.build_comparison_post(
        topic=request.topic,
        audience=request.audience,
        products=[item.model_dump() for item in request.products],
        decision_criteria=request.decision_criteria,
        affiliate_disclosure=request.affiliate_disclosure,
        minimum_words=request.minimum_words,
    )
    assert result["evidence_status"] == "source_fetch_failed_unverified"
    assert result["external_product_sources_fetched"] is False
    assert result["evidence_summary"]["source_snapshots_failed"] == 2
    assert all(item["status"] == "fetch_failed" for item in result["source_snapshots"])
    assert all(item["evidence_status"] == "source_fetch_failed" for item in result["fact_evidence"])
    assert "Snapshot fetch failed" in result["html"]
    assert result["product_facts_independently_verified"] is False
    assert result["publishing_started"] is False


def test_comparison_post_api_persists_workspace_draft_and_audit_without_provider_claims(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    active = {"workspace_id": "comparison-workspace"}

    async def override_session():
        async with sessions() as session:
            yield session

    async def auth_user():
        return {
            "email": "editor@example.invalid",
            "user_id": "editor-1",
            "workspace_id": active["workspace_id"],
            "workspace_role": "owner",
            "is_admin": False,
        }

    async def no_rate_limit(*args, **kwargs):
        return None

    async def prepare_database():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            session.add(Workspace(
                id=active["workspace_id"],
                name="Comparison Workspace",
                slug="comparison-workspace",
            ))
            await session.commit()

    async def fake_writer(**kwargs):
        assert kwargs["topic"] == "Analytics products comparison"
        return {
            "title": "Analytics products comparison — Product Comparison",
            "html": "<!doctype html><html><body><article><p>Draft only.</p></article></body></html>",
            "word_count": 8,
            "minimum_word_target": 500,
            "minimum_word_target_met": False,
            "product_count": 2,
            "products": kwargs["products"],
            "decision_criteria": ["Price", "Support"],
            "comparison_table": [{"criterion": "Price", "values": [
                {"product": "Alpha", "value": "$20"},
                {"product": "Beta", "value": "Not supplied — verify"},
            ]}],
            "unknown_fact_count": 1,
            "source_urls": ["https://vendor.example/alpha", "https://vendor.example/beta"],
            "evidence_status": "public_snapshot_captured_not_fact_verified",
            "source_snapshots": [{"source_id": "S01", "url": "https://vendor.example/alpha", "status": "fetched", "title": "Alpha", "product_names": ["Alpha"], "http_status": 200, "content_type": "text/html", "fetched_at": "2026-10-29T00:00:00+00:00", "excerpt": "Price $20", "excerpt_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "error_type": None, "detail": None}],
            "fact_evidence": [{"product": "Alpha", "fact_name": "Price", "supplied_value": "$20", "evidence_status": "exact_text_observed", "exact_text_match": True}],
            "evidence_summary": {"source_snapshots_fetched": 1, "source_snapshots_failed": 0, "exact_text_match_count": 1, "exact_text_not_found_count": 0},
            "product_facts_independently_verified": False,
            "external_product_sources_fetched": True,
            "requires_review": True,
            "publishing_started": False,
            "provider_write_access_verified": False,
            "provider": "test-model",
            "rag_sources": [],
        }

    asyncio.run(prepare_database())
    monkeypatch.setitem(main.app.dependency_overrides, main.get_session, override_session)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, auth_user)
    monkeypatch.setattr(main, "workspace_generation_rate_limit", no_rate_limit)
    monkeypatch.setattr(main, "comparison_post_writer_service", fake_writer)
    try:
        with TestClient(main.app) as client:
            response = client.post("/api/content/comparison-post", json=valid_payload())
        assert response.status_code == 201, response.text
        result = response.json()
        assert result["asset_id"]
        assert result["asset_status"] == "draft"
        assert result["publishing_started"] is False
        assert result["product_facts_independently_verified"] is False
        assert result["external_product_sources_fetched"] is True
        assert result["evidence_summary"]["source_snapshots_fetched"] == 1
        assert result["unknown_fact_count"] == 1

        async def read_records():
            async with sessions() as session:
                asset = await session.get(ContentAsset, result["asset_id"])
                audit = await session.scalar(select(AuditLog).where(
                    AuditLog.action == "content_comparison_post.created",
                    AuditLog.resource_id == result["asset_id"],
                ))
            return asset, audit

        asset, audit = asyncio.run(read_records())
        assert asset is not None and asset.workspace_id == active["workspace_id"]
        assert asset.asset_type == "comparison_post" and asset.status == "draft"
        assert asset.metadata_json["evidence_status"] == "public_snapshot_captured_not_fact_verified"
        assert asset.metadata_json["source_snapshots"][0]["excerpt_sha256"] == "a" * 64
        assert asset.metadata_json["fact_evidence"][0]["evidence_status"] == "exact_text_observed"
        assert asset.metadata_json["comparison_table"][0]["values"][1]["value"] == "Not supplied — verify"
        assert audit is not None and audit.outcome == "draft"
        assert audit.details_json["publishing_started"] is False
        assert audit.details_json["source_snapshots_fetched"] == 1
        assert audit.details_json["exact_text_match_count"] == 1
    finally:
        main.app.dependency_overrides.pop(main.get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)
        asyncio.run(engine.dispose())
