from __future__ import annotations

import asyncio

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
    with pytest.raises(ValidationError):
        ComparisonPostRequest(**valid_payload(products=[
            {"name": "Alpha", "facts": {"Price": "$20"}, "source_urls": ["https://127.0.0.1/private"]},
            {"name": "Beta", "facts": {"Price": "$35"}},
        ]))


@pytest.mark.asyncio
async def test_comparison_writer_builds_deterministic_table_sanitizes_html_and_marks_unknowns(monkeypatch):
    observed = {}

    async def fake_complete(system_prompt, user_prompt, **kwargs):
        observed["system"] = system_prompt
        observed["prompt"] = user_prompt
        return {
            "text": '<p onclick="steal()">Compare choices by fit.</p><script>alert(1)</script>'
                    '<a href="javascript:alert(2)" onclick="steal()">unsafe link</a>',
            "sources": [],
            "provider": "test-model",
        }

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
    assert "untrusted operator-supplied data" in observed["prompt"]
    assert "Alpha" in observed["prompt"] and "Beta" in observed["prompt"]
    assert "<script" not in result["html"].lower()
    assert "onclick=" not in result["html"].lower()
    assert "javascript:" not in result["html"].lower()
    assert result["html"].index('<p class="affiliate-disclosure"') < result["html"].index("<h1>")
    assert "$20" in result["html"] and "$35" in result["html"]
    assert "Not supplied — verify" in result["html"]
    assert result["unknown_fact_count"] >= 1
    assert result["evidence_status"] == "operator_supplied_unverified"
    assert result["product_facts_independently_verified"] is False
    assert result["external_product_sources_fetched"] is False
    assert result["publishing_started"] is False
    assert result["provider_write_access_verified"] is False
    assert result["provider"] == "test-model"
    assert result["source_urls"] == ["https://vendor.example/alpha", "https://vendor.example/beta"]


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
            "evidence_status": "operator_supplied_unverified",
            "product_facts_independently_verified": False,
            "external_product_sources_fetched": False,
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
        assert result["external_product_sources_fetched"] is False
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
        assert asset.metadata_json["evidence_status"] == "operator_supplied_unverified"
        assert asset.metadata_json["comparison_table"][0]["values"][1]["value"] == "Not supplied — verify"
        assert audit is not None and audit.outcome == "draft"
        assert audit.details_json["publishing_started"] is False
    finally:
        main.app.dependency_overrides.pop(main.get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)
        asyncio.run(engine.dispose())
