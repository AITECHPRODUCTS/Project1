from __future__ import annotations
import asyncio
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.schemas import MerchantOfferTermSnapshotCreateRequest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend import main
from backend.database import Base, get_session
from backend.models import Workspace
from backend.schemas import MerchantOfferCreateRequest


def offer_payload():
    return {
        "name": "Verified merchant offer packet",
        "product_url": "https://merchant.example.com/product",
        "description": "A detailed description of the merchant product and intended customer use cases.",
        "category": "creator-software",
        "commission_type": "recurring_percentage",
        "commission_value": "25.0000",
        "commission_currency": "usd",
        "terms_version": "terms-2026-10",
        "commission_terms_url": "https://merchant.example.com/affiliate-terms",
        "seller_authorization_url": "https://merchant.example.com/brand-authorization",
        "allowed_regions": ["us", "GB", "IN"],
        "restricted_traffic_sources": ["incentivized", "spam"],
        "affiliate_disclosure": "Affiliate disclosure: publishers may earn commissions from qualifying purchases.",
    }


def make_client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'merchant-offers.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            workspace_a = Workspace(name="Merchant workspace A", slug="merchant-workspace-a")
            workspace_b = Workspace(name="Merchant workspace B", slug="merchant-workspace-b")
            db.add_all([workspace_a, workspace_b])
            await db.commit()
            return workspace_a.id, workspace_b.id
    workspace_a, workspace_b = asyncio.run(setup())
    user = {"workspace_id": workspace_a, "workspace_role": "owner", "email": "creator@example.com",
            "user_id": "creator", "is_admin": False}
    async def override_session():
        async with sessions() as db:
            yield db
    async def override_auth():
        return user
    main.app.dependency_overrides[get_session] = override_session
    main.app.dependency_overrides[main.require_auth] = override_auth
    return engine, user, workspace_b, TestClient(main.app)


def cleanup(engine, client):
    main.app.dependency_overrides.pop(get_session, None)
    main.app.dependency_overrides.pop(main.require_auth, None)
    client.close()
    asyncio.run(engine.dispose())


def test_offer_is_workspace_scoped_and_network_approval_is_never_implied(tmp_path):
    engine, user, workspace_b, client = make_client(tmp_path)
    try:
        with client:
            created = client.post("/api/merchant/offers", json=offer_payload())
            assert created.status_code == 201, created.text
            body = created.json()
            assert body["status"] == "draft"
            assert body["activation_allowed"] is False
            assert body["terms_verified"] is False
            assert body["seller_authorization_verified"] is False
            assert body["affiliate_network_approval_status"] == "not_configured"
            assert body["affiliate_network_approved"] is False
            assert body["provider_submission_performed"] is False
            assert client.get("/api/merchant/offers").json()["count"] == 1
            user["workspace_id"] = workspace_b
            isolated = client.get("/api/merchant/offers")
            assert isolated.status_code == 200
            assert isolated.json()["count"] == 0
    finally:
        cleanup(engine, client)


def test_approval_requires_submit_distinct_reviewer_and_explicit_evidence_review(tmp_path):
    engine, user, _, client = make_client(tmp_path)
    try:
        with client:
            created = client.post("/api/merchant/offers", json=offer_payload())
            assert created.status_code == 201, created.text
            offer_id = created.json()["id"]
            submitted = client.post(f"/api/merchant/offers/{offer_id}/submit")
            assert submitted.status_code == 200, submitted.text
            assert submitted.json()["status"] == "submitted_for_review"
            assert submitted.json()["activation_allowed"] is False
            self_review = client.post(f"/api/merchant/offers/{offer_id}/review", json={
                "decision": "approve", "seller_authorization_verified": True,
                "commission_terms_verified": True,
            })
            assert self_review.status_code == 403, self_review.text
            user["email"] = "reviewer@example.com"
            user["workspace_role"] = "admin"
            missing_check = client.post(f"/api/merchant/offers/{offer_id}/review", json={
                "decision": "approve", "seller_authorization_verified": True,
                "commission_terms_verified": False, "reviewer_notes": "Terms not yet verified.",
            })
            assert missing_check.status_code == 409, missing_check.text
            approved = client.post(f"/api/merchant/offers/{offer_id}/review", json={
                "decision": "approve", "seller_authorization_verified": True,
                "commission_terms_verified": True, "reviewer_notes": "Seller authorization and terms reviewed.",
            })
            assert approved.status_code == 200, approved.text
            body = approved.json()
            assert body["status"] == "approved"
            assert body["activation_allowed"] is True
            assert body["terms_verified"] is True
            assert body["seller_authorization_verified"] is True
            assert body["affiliate_network_approval_status"] == "not_configured"
            assert body["affiliate_network_approved"] is False
            suspended = client.post(f"/api/merchant/offers/{offer_id}/review", json={
                "decision": "suspend", "reviewer_notes": "Suspend pending policy re-review.",
            })
            assert suspended.status_code == 200, suspended.text
            assert suspended.json()["status"] == "suspended"
            assert suspended.json()["activation_allowed"] is False
    finally:
        cleanup(engine, client)


def test_member_cannot_create_merchant_offers(tmp_path):
    engine, user, _, client = make_client(tmp_path)
    try:
        with client:
            user["workspace_role"] = "member"
            denied = client.post("/api/merchant/offers", json=offer_payload())
            assert denied.status_code == 403, denied.text
    finally:
        cleanup(engine, client)


def test_private_urls_and_percentage_values_are_rejected():
    payload = offer_payload()
    payload["seller_authorization_url"] = "http://127.0.0.1/private"
    with pytest.raises(ValidationError):
        MerchantOfferCreateRequest.model_validate(payload)
    payload = offer_payload()
    payload["commission_value"] = "100.0001"
    with pytest.raises(ValidationError):
        MerchantOfferCreateRequest.model_validate(payload)



def term_snapshot_payload(**overrides):
    payload = {
        "terms_version": "terms-2026-10",
        "commission_type": "recurring_percentage",
        "commission_value": "25.0000",
        "commission_currency": "USD",
        "cookie_days": None,
        "attribution_window_days": None,
        "allowed_regions": ["US", "GB", "IN"],
        "restricted_traffic_sources": ["incentivized", "spam"],
        "source_url": "https://merchant.example.com/affiliate-terms",
        "evidence_type": "operator_observed",
        "evidence_excerpt": "Terms manually reviewed by an operator.",
    }
    payload.update(overrides)
    return payload


def test_term_snapshots_record_baseline_changes_and_unverified_provenance(tmp_path):
    engine, user, _, client = make_client(tmp_path)
    try:
        with client:
            created = client.post("/api/merchant/offers", json=offer_payload())
            assert created.status_code == 201, created.text
            offer_id = created.json()["id"]
            endpoint = f"/api/merchant/offers/{offer_id}/term-snapshots"

            baseline = client.post(endpoint, json=term_snapshot_payload())
            assert baseline.status_code == 201, baseline.text
            first = baseline.json()
            assert first["change_status"] == "baseline_recorded"
            assert first["changed_fields"] == []
            assert first["requires_revalidation"] is False
            assert first["provider_verified"] is False
            assert first["source_content_fetched"] is False
            assert first["provenance_status"] == "operator_supplied_unverified"
            assert len(first["terms_sha256"]) == 64

            unchanged = client.post(endpoint, json=term_snapshot_payload())
            assert unchanged.status_code == 201, unchanged.text
            assert unchanged.json()["change_status"] == "unchanged"
            assert unchanged.json()["requires_revalidation"] is False

            changed = client.post(endpoint, json=term_snapshot_payload(
                terms_version="terms-2026-11",
                commission_value="20.0000",
                cookie_days=30,
                attribution_window_days=30,
                evidence_type="network_reported",
            ))
            assert changed.status_code == 201, changed.text
            result = changed.json()
            assert result["change_status"] == "changes_detected"
            assert result["requires_revalidation"] is True
            assert {"terms_version", "commission_value", "cookie_days", "attribution_window_days"} <= set(result["changed_fields"])
            assert result["provider_verified"] is False
            assert result["source_content_fetched"] is False

            history = client.get(endpoint)
            assert history.status_code == 200, history.text
            assert history.json()["count"] == 3
            assert history.json()["data"][0]["terms_sha256"] == result["terms_sha256"]
    finally:
        cleanup(engine, client)


def test_changed_terms_suspend_listed_approved_offer_and_require_revalidation(tmp_path):
    engine, user, _, client = make_client(tmp_path)
    try:
        with client:
            created = client.post("/api/merchant/offers", json=offer_payload())
            assert created.status_code == 201, created.text
            offer_id = created.json()["id"]
            submitted = client.post(f"/api/merchant/offers/{offer_id}/submit")
            assert submitted.status_code == 200, submitted.text

            user["email"] = "different-reviewer@example.com"
            user["workspace_role"] = "admin"
            approved = client.post(f"/api/merchant/offers/{offer_id}/review", json={
                "decision": "approve",
                "seller_authorization_verified": True,
                "commission_terms_verified": True,
                "reviewer_notes": "Evidence reviewed before activating the offer.",
            })
            assert approved.status_code == 200, approved.text
            listed = client.post(f"/api/merchant/offers/{offer_id}/list")
            assert listed.status_code == 200 and listed.json()["marketplace_listed"] is True

            endpoint = f"/api/merchant/offers/{offer_id}/term-snapshots"
            baseline = client.post(endpoint, json=term_snapshot_payload())
            assert baseline.status_code == 201, baseline.text
            assert baseline.json()["offer_status"] == "approved"

            changed = client.post(endpoint, json=term_snapshot_payload(commission_value="18.0000"))
            assert changed.status_code == 201, changed.text
            body = changed.json()
            assert body["requires_revalidation"] is True
            assert body["offer_status"] == "suspended"
            assert body["terms_verified"] is False
            assert body["activation_allowed"] is False
            assert body["marketplace_listed"] is False
            refreshed = client.get("/api/merchant/offers")
            assert refreshed.status_code == 200
            assert refreshed.json()["data"][0]["status"] == "suspended"
    finally:
        cleanup(engine, client)


def test_term_snapshot_history_and_capture_are_workspace_scoped(tmp_path):
    engine, user, workspace_b, client = make_client(tmp_path)
    try:
        with client:
            created = client.post("/api/merchant/offers", json=offer_payload())
            assert created.status_code == 201, created.text
            offer_id = created.json()["id"]
            endpoint = f"/api/merchant/offers/{offer_id}/term-snapshots"
            user["workspace_id"] = workspace_b
            assert client.get(endpoint).status_code == 404
            assert client.post(endpoint, json=term_snapshot_payload()).status_code == 404
    finally:
        cleanup(engine, client)


def test_term_snapshot_request_rejects_private_evidence_urls_naive_timestamps_and_invalid_percentages():
    payload = term_snapshot_payload(source_url="http://127.0.0.1/internal")
    with pytest.raises(ValidationError):
        MerchantOfferTermSnapshotCreateRequest.model_validate(payload)

    payload = term_snapshot_payload(observed_at="2026-10-28T10:00:00")
    with pytest.raises(ValidationError):
        MerchantOfferTermSnapshotCreateRequest.model_validate(payload)

    payload = term_snapshot_payload(commission_value="100.0001")
    with pytest.raises(ValidationError):
        MerchantOfferTermSnapshotCreateRequest.model_validate(payload)
