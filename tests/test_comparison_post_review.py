from __future__ import annotations

import asyncio
import hashlib

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base
from backend.models import AuditLog, ContentAsset, Workspace
from backend.schemas import ComparisonPostReviewRequest
from backend.tenancy import workspace_scope
from backend.services.comparison_integrity import build_source_snapshot_manifest, comparison_evidence_payload_sha256, sha256_text, source_snapshot_manifest_sha256


def review_payload(content_sha256: str, **overrides):
    result = {
        "decision": "approve",
        "expected_content_sha256": content_sha256,
        "reviewer_notes": "",
        "confirm_editorial_reviewed": True,
    }
    result.update(overrides)
    return result


def test_comparison_review_request_requires_hash_and_notes_for_nonapproval():
    valid_hash = "a" * 64
    payload = ComparisonPostReviewRequest(**review_payload(valid_hash))
    assert payload.expected_content_sha256 == valid_hash
    with pytest.raises(ValidationError):
        ComparisonPostReviewRequest(**review_payload("not-a-sha256"))
    with pytest.raises(ValidationError, match="require reviewer notes"):
        ComparisonPostReviewRequest(**review_payload(valid_hash, decision="request_changes", confirm_editorial_reviewed=False))
    with pytest.raises(ValidationError, match="require reviewer notes"):
        ComparisonPostReviewRequest(**review_payload(valid_hash, decision="reject"))


def test_comparison_review_is_owner_admin_only_hash_bound_audited_and_never_publishes(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    active = {"workspace_id": "review-workspace", "workspace_role": "owner"}
    asset_id = "review-comparison-asset"
    content = "<!doctype html><html><body><article><h1>Saved version</h1><p>Review this exact body.</p></article></body></html>"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    baseline_evidence_hash: dict[str, str] = {}

    async def override_session():
        async with sessions() as session:
            yield session

    async def auth_user():
        return {
            "email": "editor@example.invalid",
            "user_id": "editor-1",
            "workspace_id": active["workspace_id"],
            "workspace_role": active["workspace_role"],
            "is_admin": False,
        }

    async def prepare_database():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            session.add(Workspace(id="review-workspace", name="Review Workspace", slug="review-workspace"))
            session.add(Workspace(id="other-review-workspace", name="Other Review Workspace", slug="other-review-workspace"))
            await session.flush()
            snapshot_excerpt = "Official product page supplied for the review test."
            snapshots = [{
                "source_id": "S01",
                "url": "https://vendor.example/product",
                "product_names": ["Reviewable comparison"],
                "title": "Product page",
                "status": "fetched",
                "http_status": 200,
                "content_type": "text/html",
                "fetched_at": "2026-10-29T10:00:00+00:00",
                "excerpt": snapshot_excerpt,
                "excerpt_sha256": sha256_text(snapshot_excerpt),
                "error_type": None,
                "detail": None,
            }]
            snapshot_manifest = build_source_snapshot_manifest(snapshots)
            snapshot_manifest_hash = source_snapshot_manifest_sha256(snapshot_manifest)
            review_metadata = {
                "schema_version": 1,
                "asset_title": "Reviewable comparison",
                "source_urls": ["https://vendor.example/product"],
                "topic": "Reviewable comparison",
                "audience": "Test editors",
                "affiliate_disclosure": "Disclosure: This is a review test disclaimer.",
                "revision_number": 2,
                "revision_of_asset_id": None,
                "revision_root_asset_id": asset_id,
                "products": [{"name": "Reviewable comparison", "facts": {"Price": "$20"}}],
                "decision_criteria": ["Price"],
                "comparison_table": [{"criterion": "Price", "values": [{"product": "Reviewable comparison", "value": "$20"}]}],
                "unknown_fact_count": 0,
                "word_count": 8,
                "minimum_word_target": 300,
                "minimum_word_target_met": False,
                "evidence_status": "operator_supplied_unverified",
                "product_facts_independently_verified": False,
                "external_product_sources_fetched": False,
                "source_snapshots": snapshots,
                "source_snapshot_manifest": snapshot_manifest,
                "source_snapshot_manifest_sha256": snapshot_manifest_hash,
                "fact_evidence": [{"product": "Reviewable comparison", "fact_name": "Price", "supplied_value": "$20"}],
                "evidence_summary": {"exact_text_match_count": 1},
                "model_provider": "test-model",
                "content_sha256": content_hash,
                "publishing_started": False,
            }
            evidence_payload_hash = comparison_evidence_payload_sha256(review_metadata)
            baseline_evidence_hash["value"] = evidence_payload_hash
            review_metadata["evidence_payload_sha256"] = evidence_payload_hash
            review_metadata["review_status"] = "pending_review"
            review_metadata["review_history"] = []
            review_metadata["requires_review"] = True
            with workspace_scope("review-workspace"):
                session.add(ContentAsset(
                    id=asset_id,
                    workspace_id="review-workspace",
                    asset_type="comparison_post",
                    title="Reviewable comparison",
                    body=content,
                    status="draft",
                    source_urls=["https://vendor.example/product"],
                    metadata_json=review_metadata,
                ))
                await session.flush()
                session.add(AuditLog(
                    workspace_id="review-workspace",
                    actor="fixture",
                    action="content_comparison_post.created",
                    resource_type="content_asset",
                    resource_id=asset_id,
                    outcome="draft",
                    details_json={
                        "content_sha256": content_hash,
                        "source_snapshot_manifest_sha256": snapshot_manifest_hash,
                        "evidence_payload_sha256": evidence_payload_hash,
                    },
                ))
            await session.commit()

    asyncio.run(prepare_database())
    monkeypatch.setitem(main.app.dependency_overrides, main.get_session, override_session)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, auth_user)
    try:
        with TestClient(main.app) as client:
            active["workspace_role"] = "member"
            denied = client.post(
                f"/api/content/comparison-posts/{asset_id}/review",
                json=review_payload(content_hash),
            )
            assert denied.status_code == 403

            active["workspace_role"] = "owner"
            wrong_hash = client.post(
                f"/api/content/comparison-posts/{asset_id}/review",
                json=review_payload("0" * 64),
            )
            assert wrong_hash.status_code == 409
            unconfirmed = client.post(
                f"/api/content/comparison-posts/{asset_id}/review",
                json=review_payload(content_hash, confirm_editorial_reviewed=False),
            )
            assert unconfirmed.status_code == 409

            active["workspace_id"] = "other-review-workspace"
            foreign = client.post(
                f"/api/content/comparison-posts/{asset_id}/review",
                json=review_payload(content_hash),
            )
            assert foreign.status_code == 404

            active["workspace_id"] = "review-workspace"
            approved = client.post(
                f"/api/content/comparison-posts/{asset_id}/review",
                json=review_payload(content_hash, reviewer_notes="Reviewed wording and disclosure."),
            )
            assert approved.status_code == 200, approved.text
            result = approved.json()
            assert result["review_status"] == "approved"
            assert result["asset_status"] == "draft"
            assert result["content_sha256"] == content_hash
            assert result["requires_review"] is False
            assert result["publishing_started"] is False
            assert result["external_publication_started"] is False
            assert result["product_facts_independently_verified"] is False
            assert result["affiliate_eligibility_verified"] is False
            assert result["publication_authorized"] is False
            assert result["editorial_review_only"] is True

            duplicate = client.post(
                f"/api/content/comparison-posts/{asset_id}/review",
                json=review_payload(content_hash),
            )
            assert duplicate.status_code == 409
            detail = client.get(f"/api/content/comparison-posts/{asset_id}")
            assert detail.status_code == 200
            assert detail.headers["cache-control"] == "no-store"
            assert detail.json()["review_status"] == "approved"
            assert detail.json()["content_sha256"] == content_hash
            assert detail.json()["evidence_payload_integrity_status"] == "verified"
            assert detail.json()["review_history"][-1]["content_sha256"] == content_hash

        async def read_records():
            async with sessions() as session:
                row = await session.get(ContentAsset, asset_id)
                audit = await session.scalar(select(AuditLog).where(
                    AuditLog.action == "content_comparison_post.reviewed",
                    AuditLog.resource_id == asset_id,
                ))
            return row, audit

        row, audit = asyncio.run(read_records())
        assert row is not None and row.workspace_id == "review-workspace"
        assert row.status == "draft" and row.body == content
        assert row.metadata_json["review_status"] == "approved"
        assert row.metadata_json["reviewed_content_sha256"] == content_hash
        assert row.metadata_json["publishing_started"] is False
        assert audit is not None and audit.outcome == "editorial_approved"
        assert audit.details_json["content_sha256"] == content_hash
        assert audit.details_json["evidence_payload_sha256"] == baseline_evidence_hash["value"]
        assert audit.details_json["publishing_started"] is False
        assert audit.details_json["product_facts_independently_verified"] is False
    finally:
        main.app.dependency_overrides.pop(main.get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)
        asyncio.run(engine.dispose())
