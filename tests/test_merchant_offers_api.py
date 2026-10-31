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
            "user_id": "creator", "is_admin": False, "account_type": "merchant_product_owner"}
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
            assert [row["sequence_number"] for row in history.json()["data"]] == [3, 2, 1]
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


class _FakeTermsResponse:
    def __init__(self, status_code=200, headers=None, body=b""):
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body

    async def aiter_bytes(self):
        for offset in range(0, len(self._body), 137):
            yield self._body[offset:offset + 137]


def _patch_terms_response(monkeypatch, response, calls=None, failure=None):
    from contextlib import asynccontextmanager

    observed = calls if calls is not None else []

    @asynccontextmanager
    async def fake_open(url, **kwargs):
        observed.append({"url": url, **kwargs})
        if failure is not None:
            raise failure
        yield response

    monkeypatch.setattr(main, "open_public_http_response", fake_open)
    return observed


def test_explicit_terms_fetch_persists_hash_excerpt_and_never_verifies_offer(tmp_path, monkeypatch):
    import hashlib

    engine, user, _, client = make_client(tmp_path)
    body = b"<html><head><title>Terms</title><script>do_not_store_this()</script></head><body><h1>Affiliate Terms</h1><p>Recurring commission is 25 percent.</p><style>.hidden{}</style></body></html>"
    response = _FakeTermsResponse(200, {
        "content-type": "text/html; charset=utf-8",
        "content-length": str(len(body)),
        "etag": '"terms-v7"',
        "last-modified": "Tue, 27 Oct 2026 10:00:00 GMT",
    }, body)
    calls = _patch_terms_response(monkeypatch, response)
    try:
        with client:
            created = client.post("/api/merchant/offers", json=offer_payload())
            assert created.status_code == 201, created.text
            offer_id = created.json()["id"]
            saved = client.post(
                f"/api/merchant/offers/{offer_id}/term-snapshots",
                json=term_snapshot_payload(),
            )
            assert saved.status_code == 201, saved.text
            snapshot_id = saved.json()["id"]

            fetched = client.post(
                f"/api/merchant/offers/{offer_id}/term-snapshots/{snapshot_id}/fetch-evidence"
            )
            assert fetched.status_code == 201, fetched.text
            result = fetched.json()
            assert result["fetch_status"] == "fetched"
            assert result["http_status_code"] == 200
            assert result["response_bytes"] == len(body)
            assert result["content_sha256"] == hashlib.sha256(body).hexdigest()
            assert "Recurring commission is 25 percent." in result["text_excerpt"]
            assert "do_not_store_this" not in result["text_excerpt"]
            assert result["etag"] == '"terms-v7"'
            assert result["last_modified"] == "Tue, 27 Oct 2026 10:00:00 GMT"
            assert result["provider_verified"] is False
            assert len(calls) == 1 and calls[0]["url"] == "https://merchant.example.com/affiliate-terms"
            assert calls[0]["timeout"] == main.MERCHANT_TERMS_FETCH_TIMEOUT_SECONDS
            current_offer = client.get("/api/merchant/offers").json()["data"][0]
            assert current_offer["terms_verified"] is False
            assert current_offer["activation_allowed"] is False
            history = client.get(
                f"/api/merchant/offers/{offer_id}/term-snapshots/{snapshot_id}/fetches"
            )
            assert history.status_code == 200, history.text
            assert history.json()["count"] == 1
            assert history.json()["data"][0]["content_sha256"] == result["content_sha256"]
    finally:
        cleanup(engine, client)


@pytest.mark.parametrize(
    "status_code,headers,expected_status,expected_error",
    [
        (302, {"content-type": "text/html", "location": "http://127.0.0.1/admin"}, "redirect_blocked", "redirect_not_followed"),
        (200, {"content-type": "application/pdf"}, "unsupported_content_type", "text_content_required"),
        (403, {"content-type": "text/html"}, "http_error", "upstream_http_error"),
    ],
)
def test_terms_fetch_records_redirect_content_type_and_http_failures(
    tmp_path, monkeypatch, status_code, headers, expected_status, expected_error
):
    engine, user, _, client = make_client(tmp_path)
    response = _FakeTermsResponse(status_code, headers, b"ignored")
    calls = _patch_terms_response(monkeypatch, response)
    try:
        with client:
            created = client.post("/api/merchant/offers", json=offer_payload())
            offer_id = created.json()["id"]
            saved = client.post(
                f"/api/merchant/offers/{offer_id}/term-snapshots",
                json=term_snapshot_payload(),
            )
            snapshot_id = saved.json()["id"]
            result = client.post(
                f"/api/merchant/offers/{offer_id}/term-snapshots/{snapshot_id}/fetch-evidence"
            )
            assert result.status_code == 201, result.text
            assert result.json()["fetch_status"] == expected_status
            assert result.json()["error_code"] == expected_error
            assert len(calls) == 1
            assert result.json()["provider_verified"] is False
    finally:
        cleanup(engine, client)


def test_terms_fetch_refuses_http_without_network_request(tmp_path, monkeypatch):
    engine, user, _, client = make_client(tmp_path)
    try:
        with client:
            created = client.post("/api/merchant/offers", json=offer_payload())
            offer_id = created.json()["id"]
            saved = client.post(
                f"/api/merchant/offers/{offer_id}/term-snapshots",
                json=term_snapshot_payload(source_url="http://merchant.example.com/terms"),
            )
            assert saved.status_code == 201, saved.text
            snapshot_id = saved.json()["id"]
            calls = _patch_terms_response(monkeypatch, None)
            result = client.post(
                f"/api/merchant/offers/{offer_id}/term-snapshots/{snapshot_id}/fetch-evidence"
            )
            assert result.status_code == 201, result.text
            assert result.json()["fetch_status"] == "blocked_target"
            assert result.json()["error_code"] == "https_required"
            assert calls == []
    finally:
        cleanup(engine, client)


def test_terms_fetch_private_resolution_is_recorded_without_request(tmp_path, monkeypatch):
    from contextlib import asynccontextmanager

    engine, user, _, client = make_client(tmp_path)

    @asynccontextmanager
    async def block_private(url, **kwargs):
        raise ValueError("Private, loopback, link-local, multicast or reserved destinations are blocked")
        yield  # pragma: no cover

    monkeypatch.setattr(main, "open_public_http_response", block_private)
    try:
        with client:
            created = client.post("/api/merchant/offers", json=offer_payload())
            offer_id = created.json()["id"]
            saved = client.post(
                f"/api/merchant/offers/{offer_id}/term-snapshots",
                json=term_snapshot_payload(),
            )
            snapshot_id = saved.json()["id"]
            result = client.post(
                f"/api/merchant/offers/{offer_id}/term-snapshots/{snapshot_id}/fetch-evidence"
            )
            assert result.status_code == 201, result.text
            assert result.json()["fetch_status"] == "blocked_target"
            assert result.json()["error_code"] == "public_destination_rejected"
            assert result.json()["content_sha256"] is None
    finally:
        cleanup(engine, client)


def test_terms_fetch_history_is_workspace_scoped(tmp_path, monkeypatch):
    engine, user, workspace_b, client = make_client(tmp_path)
    try:
        with client:
            created = client.post("/api/merchant/offers", json=offer_payload())
            offer_id = created.json()["id"]
            saved = client.post(
                f"/api/merchant/offers/{offer_id}/term-snapshots",
                json=term_snapshot_payload(),
            )
            snapshot_id = saved.json()["id"]
            user["workspace_id"] = workspace_b
            route = f"/api/merchant/offers/{offer_id}/term-snapshots/{snapshot_id}/fetches"
            assert client.get(route).status_code == 404
    finally:
        cleanup(engine, client)


def test_terms_fetch_compares_successful_page_hashes_without_claiming_terms_verified(tmp_path, monkeypatch):
    import hashlib
    from contextlib import asynccontextmanager

    engine, user, _, client = make_client(tmp_path)
    body_a = b"<html><body><p>Commission is twenty five percent.</p></body></html>"
    body_b = b"<html><body><p>Commission is twenty percent.</p></body></html>"
    responses = [
        _FakeTermsResponse(200, {"content-type": "text/html", "content-length": str(len(body_a))}, body_a),
        _FakeTermsResponse(200, {"content-type": "text/html", "content-length": str(len(body_a))}, body_a),
        _FakeTermsResponse(200, {"content-type": "text/html", "content-length": str(len(body_b))}, body_b),
    ]

    @asynccontextmanager
    async def fake_open(url, **kwargs):
        yield responses.pop(0)

    monkeypatch.setattr(main, "open_public_http_response", fake_open)
    try:
        with client:
            created = client.post("/api/merchant/offers", json=offer_payload())
            offer_id = created.json()["id"]
            saved = client.post(
                f"/api/merchant/offers/{offer_id}/term-snapshots",
                json=term_snapshot_payload(),
            )
            snapshot_id = saved.json()["id"]
            endpoint = f"/api/merchant/offers/{offer_id}/term-snapshots/{snapshot_id}/fetch-evidence"

            first_response = client.post(endpoint)
            assert first_response.status_code == 201, first_response.text
            first = first_response.json()
            assert first["content_change_status"] == "baseline_recorded"
            assert first["previous_content_sha256"] is None
            assert first["requires_human_review"] is False
            assert first["content_sha256"] == hashlib.sha256(body_a).hexdigest()

            second = client.post(endpoint).json()
            assert second["content_change_status"] == "unchanged"
            assert second["previous_content_sha256"] == first["content_sha256"]
            assert second["requires_human_review"] is False

            third = client.post(endpoint).json()
            assert third["content_change_status"] == "content_changed"
            assert third["previous_content_sha256"] == second["content_sha256"]
            assert third["content_sha256"] == hashlib.sha256(body_b).hexdigest()
            assert third["requires_human_review"] is True
            assert third["provider_verified"] is False

            current_offer = client.get("/api/merchant/offers").json()["data"][0]
            assert current_offer["terms_verified"] is False
            assert current_offer["activation_allowed"] is False
            history = client.get(
                f"/api/merchant/offers/{offer_id}/term-snapshots/{snapshot_id}/fetches"
            ).json()
            assert history["count"] == 3
            assert [item["content_change_status"] for item in history["data"]] == [
                "content_changed", "unchanged", "baseline_recorded"
            ]
    finally:
        cleanup(engine, client)


@pytest.mark.parametrize(
    "decision,expected_review_status,expected_offer_status,expected_terms_verified",
    [
        ("no_material_change", "reviewed_no_material_change", "approved", True),
        ("material_change_found", "material_change_found", "suspended", False),
        ("source_unreliable", "source_unreliable", "suspended", False),
    ],
)
def test_changed_source_requires_independent_review_and_applies_decision(
    tmp_path, monkeypatch, decision, expected_review_status, expected_offer_status, expected_terms_verified
):
    from contextlib import asynccontextmanager

    engine, user, _, client = make_client(tmp_path)
    body_a = b"<html><body><p>Affiliate commission terms version A.</p></body></html>"
    body_b = b"<html><body><p>Affiliate commission terms version B.</p></body></html>"
    responses = [
        _FakeTermsResponse(200, {"content-type": "text/html", "content-length": str(len(body_a))}, body_a),
        _FakeTermsResponse(200, {"content-type": "text/html", "content-length": str(len(body_b))}, body_b),
    ]

    @asynccontextmanager
    async def fake_open(url, **kwargs):
        yield responses.pop(0)

    monkeypatch.setattr(main, "open_public_http_response", fake_open)
    try:
        with client:
            created = client.post("/api/merchant/offers", json=offer_payload())
            assert created.status_code == 201, created.text
            offer_id = created.json()["id"]
            snapshot_response = client.post(
                f"/api/merchant/offers/{offer_id}/term-snapshots",
                json=term_snapshot_payload(),
            )
            assert snapshot_response.status_code == 201, snapshot_response.text
            snapshot_id = snapshot_response.json()["id"]
            submit = client.post(f"/api/merchant/offers/{offer_id}/submit")
            assert submit.status_code == 200, submit.text

            user["email"] = "reviewer@example.com"
            user["workspace_role"] = "admin"
            approved = client.post(f"/api/merchant/offers/{offer_id}/review", json={
                "decision": "approve",
                "seller_authorization_verified": True,
                "commission_terms_verified": True,
                "reviewer_notes": "Checked the supplied seller and terms references.",
            })
            assert approved.status_code == 200, approved.text
            listed = client.post(f"/api/merchant/offers/{offer_id}/list")
            assert listed.status_code == 200 and listed.json()["marketplace_listed"] is True

            fetch_endpoint = f"/api/merchant/offers/{offer_id}/term-snapshots/{snapshot_id}/fetch-evidence"
            assert client.post(fetch_endpoint).json()["content_change_status"] == "baseline_recorded"
            changed_fetch = client.post(fetch_endpoint).json()
            assert changed_fetch["content_change_status"] == "content_changed"
            assert changed_fetch["review_status"] == "pending_review"

            review_endpoint = f"/api/merchant/offers/{offer_id}/term-snapshots/{snapshot_id}/fetches/{changed_fetch['id']}/review"
            user["email"] = "creator@example.com"
            denied = client.post(review_endpoint, json={
                "decision": decision, "reviewer_notes": "Reviewed the changed source content."
            })
            assert denied.status_code == 403, denied.text

            user["email"] = "reviewer@example.com"
            reviewed = client.post(review_endpoint, json={
                "decision": decision,
                "reviewer_notes": "Reviewed the changed source and documented the decision.",
            })
            assert reviewed.status_code == 200, reviewed.text
            result = reviewed.json()
            assert result["review_status"] == expected_review_status
            assert result["review_decision"] == decision
            assert result["reviewed_by"] == "reviewer@example.com"
            assert result["requires_human_review"] is False
            assert result["offer_status"] == expected_offer_status
            assert result["terms_verified"] is expected_terms_verified
            assert result["activation_allowed"] is expected_terms_verified
            assert result["marketplace_listed"] is expected_terms_verified
            repeated = client.post(review_endpoint, json={
                "decision": "no_material_change", "reviewer_notes": "This repeat review must not be accepted."
            })
            assert repeated.status_code == 409
    finally:
        cleanup(engine, client)


def test_changed_source_review_notes_must_be_meaningful():
    from pydantic import ValidationError
    from backend.schemas import MerchantOfferTermEvidenceReviewRequest

    with pytest.raises(ValidationError):
        MerchantOfferTermEvidenceReviewRequest.model_validate({
            "decision": "no_material_change",
            "reviewer_notes": "          ",
        })
