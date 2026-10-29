from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base
from backend.models import AuditLog, ContentAsset, Workspace
from backend.schemas import ListiclePostRequest
from backend.services import listicle_writer as listicle_service


def products_payload():
    products = []
    for index in range(1, 6):
        products.append({
            "name": f"Tool {index}",
            "facts": {
                "Price": f"USD {index * 10}/month" if index < 3 else "Not supplied — verify",
                "Best for": f"Audience {index}",
                "Features": f"Feature set {index}",
            },
            "source_urls": [f"https://vendor.example/tool-{index}"] if index <= 2 else [],
            "affiliate_url": f"https://affiliate.example/ref/tool-{index}" if index == 1 else None,
            "affiliate_relationship": "affiliate_primary" if index == 1 else "editorial",
        })
    return products


def valid_payload(**overrides):
    data = {
        "topic": "Email marketing tools",
        "audience": "Independent affiliate publishers",
        "target_keyword": "best email marketing tools",
        "products": products_payload(),
        "evaluation_criteria": ["Audience fit", "Pricing clarity", "Supplied features"],
        "affiliate_disclosure": "Disclosure: I may earn a commission from qualifying purchases.",
        "minimum_words": 800,
        "tone": "professional",
    }
    data.update(overrides)
    return data


def test_listicle_schema_requires_five_distinct_products_and_safe_affiliate_relationships():
    request = ListiclePostRequest(**valid_payload())
    assert len(request.products) == 5
    assert request.products[0].affiliate_relationship == "affiliate_primary"
    with pytest.raises(ValidationError):
        ListiclePostRequest(**valid_payload(products=products_payload()[:4]))
    with pytest.raises(ValidationError):
        ListiclePostRequest(**valid_payload(products=[
            products_payload()[0],
            {**products_payload()[1], "name": " tool 1 "},
            *products_payload()[2:],
        ]))
    with pytest.raises(ValidationError):
        ListiclePostRequest(**valid_payload(products=[
            *products_payload()[:3],
            {**products_payload()[3], "affiliate_relationship": "affiliate_primary", "affiliate_url": "https://affiliate.example/tool-4"},
            products_payload()[4],
        ]))
    with pytest.raises(ValidationError):
        ListiclePostRequest(**valid_payload(products=[
            {**products_payload()[0], "affiliate_url": "http://affiliate.example/tool-1"},
            *products_payload()[1:],
        ]))
    with pytest.raises(ValidationError):
        ListiclePostRequest(**valid_payload(products=[
            {**products_payload()[0], "affiliate_url": "https://affiliate.example/tool-1?api_key=DO_NOT_STORE"},
            *products_payload()[1:],
        ]))
    with pytest.raises(ValidationError):
        ListiclePostRequest(**valid_payload(products=[
            {**products_payload()[0], "affiliate_relationship": "editorial"},
            *products_payload()[1:],
        ]))


@pytest.mark.asyncio
async def test_listicle_writer_builds_deterministic_summary_and_fact_ledger_without_inventing_evidence(monkeypatch):
    observed = {}
    products = products_payload()
    snapshots = [
        {
            "source_id": "S01",
            "url": "https://vendor.example/tool-1",
            "product_names": ["Tool 1"],
            "title": "Tool 1 official pricing",
            "status": "fetched",
            "http_status": 200,
            "content_type": "text/html",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "excerpt": "Tool 1 costs USD 10/month. Feature set 1 is available.",
            "excerpt_sha256": hashlib.sha256(b"Tool 1 costs USD 10/month. Feature set 1 is available.").hexdigest(),
            "error_type": None,
            "detail": None,
        },
        {
            "source_id": "S02",
            "url": "https://vendor.example/tool-2",
            "product_names": ["Tool 2"],
            "title": "Tool 2 official page",
            "status": "fetched",
            "http_status": 200,
            "content_type": "text/html",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "excerpt": "Tool 2 costs USD 20/month. Feature set 2 is available.",
            "excerpt_sha256": hashlib.sha256(b"Tool 2 costs USD 20/month. Feature set 2 is available.").hexdigest(),
            "error_type": None,
            "detail": None,
        },
    ]

    async def fake_capture(input_products):
        observed["products"] = input_products
        return snapshots

    async def fake_complete(system_prompt, user_prompt, **kwargs):
        observed["system"] = system_prompt
        observed["prompt"] = user_prompt
        return {
            "text": '<p onclick="steal()">Compare the supplied options carefully.</p><script>alert(1)</script>'
                    '<img src=x onerror="steal()"><a href="javascript:alert(2)">unsafe</a>',
            "sources": [],
            "provider": "test-model",
        }

    monkeypatch.setattr(listicle_service, "_capture_source_snapshots", fake_capture)
    monkeypatch.setattr(listicle_service.llm_service, "complete", fake_complete)
    request = ListiclePostRequest(**valid_payload())
    result = await listicle_service.build_listicle_post(
        topic=request.topic,
        audience=request.audience,
        target_keyword=request.target_keyword,
        products=[item.model_dump() for item in request.products],
        evaluation_criteria=request.evaluation_criteria,
        affiliate_disclosure=request.affiliate_disclosure,
        minimum_words=request.minimum_words,
        tone=request.tone,
    )

    assert "untrusted" in observed["system"].lower()
    assert "never follow instructions" in observed["system"].lower()
    assert "products_in_required_order" in observed["prompt"]
    assert "Tool 1" in observed["prompt"] and "Tool 5" in observed["prompt"]
    assert result["format"] == "listicle"
    assert result["product_count"] == 5
    assert [item["rank"] for item in result["products_featured"]] == [1, 2, 3, 4, 5]
    assert "Affiliate disclosure" in result["html"]
    assert result["html"].index("Affiliate disclosure") < result["html"].index("<h1>")
    assert "At a glance" in result["html"]
    assert "Not supplied — verify" in result["html"]
    assert "<script" not in result["html"].lower()
    assert "<img" not in result["html"].lower()
    assert "onclick=" not in result["html"].lower()
    assert "onerror=" not in result["html"].lower()
    assert "javascript:" not in result["html"].lower()
    assert 'rel="sponsored nofollow noopener noreferrer"' in result["html"]
    assert result["evidence_status"] == "public_snapshot_captured_not_fact_verified"
    assert result["fact_evidence"][0]["evidence_status"] == "exact_text_observed"
    assert result["fact_evidence"][1]["evidence_status"] == "exact_text_not_found"
    assert result["evidence_summary"]["source_snapshots_fetched"] == 2
    assert result["product_facts_independently_verified"] is False
    assert result["publishing_started"] is False
    assert result["provider_write_access_verified"] is False
    assert result["provider"] == "test-model"
    assert result["minimum_word_target"] == 800
    assert result["word_count_warning"] is not None


def test_listicle_api_persists_workspace_draft_hash_review_and_blocks_tampering(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    active = {"workspace_id": "listicle-workspace"}

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
            session.add(Workspace(id=active["workspace_id"], name="Listicle Workspace", slug="listicle-workspace"))
            session.add(Workspace(id="other-workspace", name="Other Workspace", slug="other-workspace"))
            await session.commit()

    def fake_result(**kwargs):
        products = kwargs["products"]
        body = (
            "<!doctype html><html><head><meta charset=\"utf-8\"></head><body><article>"
            "<p><strong>Affiliate disclosure:</strong> " + kwargs["affiliate_disclosure"] + "</p>"
            "<h1>Five tools roundup</h1><h2>At a glance</h2><p>Not supplied — verify</p>"
            "</article></body></html>"
        )
        return {
            "title": "5 Best Email Marketing Tools in 2026 (Evidence-Aware Roundup)",
            "slug": "best-email-marketing-tools-2026",
            "meta_description": "Evidence-aware roundup draft; verify all product facts.",
            "topic": kwargs["topic"],
            "audience": kwargs["audience"],
            "target_keyword": kwargs["target_keyword"],
            "format": "listicle",
            "html": body,
            "word_count": 250,
            "minimum_word_target": kwargs["minimum_words"],
            "minimum_word_target_met": False,
            "word_count_warning": "Draft below requested target.",
            "product_count": len(products),
            "products": products,
            "products_featured": [
                {"rank": index, "name": item["name"], "affiliate_relationship": item["affiliate_relationship"], "affiliate_url": item.get("affiliate_url")}
                for index, item in enumerate(products, start=1)
            ],
            "evaluation_criteria": kwargs["evaluation_criteria"],
            "source_urls": [],
            "source_snapshots": [],
            "fact_evidence": [
                {"product": item["name"], "fact_name": "Price", "supplied_value": item["facts"].get("Price", "Not supplied"),
                 "source_id": None, "source_url": None, "excerpt_sha256": None, "exact_text_match": False,
                 "evidence_status": "no_source_supplied", "editorial_review_required": True}
                for item in products
            ],
            "evidence_summary": {
                "source_count": 0, "source_snapshots_fetched": 0, "source_snapshots_failed": 0,
                "fact_count": len(products), "exact_text_match_count": 0, "exact_text_not_found_count": 0,
                "facts_not_compared": len(products), "interpretation": "Supplied values remain unverified.",
            },
            "evidence_status": "operator_supplied_unverified",
            "product_facts_independently_verified": False,
            "external_product_sources_fetched": False,
            "requires_review": True,
            "publishing_started": False,
            "provider_write_access_verified": False,
            "provider": "test-model",
            "rag_sources": [],
            "execution_boundary": "Workspace listicle draft; no provider write.",
        }

    asyncio.run(prepare_database())
    monkeypatch.setitem(main.app.dependency_overrides, main.get_session, override_session)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, auth_user)
    monkeypatch.setattr(main, "workspace_generation_rate_limit", no_rate_limit)
    monkeypatch.setattr(main, "listicle_writer_service", fake_result)
    try:
        with TestClient(main.app) as client:
            response = client.post("/api/content/listicle", json=valid_payload())
            assert response.status_code == 201, response.text
            created = response.json()
            asset_id = created["asset_id"]
            assert created["asset_status"] == "draft"
            assert created["publishing_started"] is False
            assert created["product_facts_independently_verified"] is False
            assert created["review_status"] == "pending_review"
            assert len(created["products_featured"]) == 5
            assert len(created["content_sha256"]) == 64

            listing = client.get("/api/content/listicles?limit=20&offset=0")
            assert listing.status_code == 200, listing.text
            assert listing.headers["cache-control"] == "no-store"
            assert listing.json()["total"] == 1
            assert listing.json()["items"][0]["content_integrity_status"] == "verified"

            detail = client.get("/api/content/listicles/" + asset_id)
            assert detail.status_code == 200, detail.text
            opened = detail.json()
            assert opened["content_integrity_status"] == "verified"
            assert opened["title"] == created["title"]
            assert opened["publishing_started"] is False
            assert detail.headers["cache-control"] == "no-store"

            review = client.post(
                "/api/content/listicles/" + asset_id + "/review",
                json={
                    "decision": "approve",
                    "expected_content_sha256": created["content_sha256"],
                    "confirm_editorial_reviewed": True,
                },
            )
            assert review.status_code == 200, review.text
            assert review.json()["review_status"] == "approved"
            assert review.json()["publishing_started"] is False
            duplicate_review = client.post(
                "/api/content/listicles/" + asset_id + "/review",
                json={
                    "decision": "approve",
                    "expected_content_sha256": created["content_sha256"],
                    "confirm_editorial_reviewed": True,
                },
            )
            assert duplicate_review.status_code == 409

            async def persisted_records():
                async with sessions() as session:
                    row = await session.get(ContentAsset, asset_id)
                    created_audit = await session.scalar(select(AuditLog).where(
                        AuditLog.action == "content_listicle_post.created",
                        AuditLog.resource_id == asset_id,
                    ))
                    review_audit = await session.scalar(select(AuditLog).where(
                        AuditLog.action == "content_listicle_post.reviewed",
                        AuditLog.resource_id == asset_id,
                    ))
                return row, created_audit, review_audit

            asset, created_audit, review_audit = asyncio.run(persisted_records())
            assert asset is not None and asset.workspace_id == active["workspace_id"]
            assert asset.asset_type == "listicle_post" and asset.status == "draft"
            assert created_audit is not None and created_audit.outcome == "draft"
            assert review_audit is not None and review_audit.outcome == "approved"
            assert review_audit.details_json["external_publication_started"] is False

            async def corrupt_saved_asset():
                async with sessions() as session:
                    row = await session.get(ContentAsset, asset_id)
                    row.body = (row.body or "") + "<p>tampered after review</p>"
                    await session.commit()

            asyncio.run(corrupt_saved_asset())
            tampered = client.get("/api/content/listicles/" + asset_id)
            assert tampered.status_code == 409, tampered.text
            assert tampered.json()["detail"]["code"] == "LISTICLE_INTEGRITY_CHECK_FAILED"

            active["workspace_id"] = "other-workspace"
            other_listing = client.get("/api/content/listicles?limit=20&offset=0")
            assert other_listing.status_code == 200, other_listing.text
            assert other_listing.json()["total"] == 0
            other_detail = client.get("/api/content/listicles/" + asset_id)
            assert other_detail.status_code == 404
    finally:
        main.app.dependency_overrides.pop(main.get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)
        asyncio.run(engine.dispose())
