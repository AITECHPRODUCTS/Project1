from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import main
from backend.database import Base, get_session
from backend.models import MerchantOffer, Workspace
from backend.schemas import MarketplaceApplicationCreateRequest
from backend.tenancy import workspace_scope


def application_payload():
    return {
        "publisher_website_url": "https://publisher.example.com",
        "audience_description": "Readers who need careful, evidence-based creator software comparisons.",
        "traffic_sources": ["seo", "blog", "email_opt_in"],
        "intended_regions": ["us", "GB", "IN"],
        "promotion_plan": "We will publish carefully sourced comparison content, retain dated terms evidence, disclose affiliate links clearly, and respect the merchant's permitted regions and traffic restrictions.",
        "offer_terms_reviewed": True,
        "traffic_restrictions_reviewed": True,
        "affiliate_disclosure_ready": True,
        "contact_sharing_consent": True,
    }


def seed_offer(merchant_workspace_id: str) -> MerchantOffer:
    return MerchantOffer(
        workspace_id=merchant_workspace_id,
        created_by="merchant@example.com",
        name="Marketplace creator suite",
        product_url="https://seller.example.com/product",
        description="Creator software with workflow features for independent publishers.",
        category="creator-software",
        commission_type="recurring_percentage",
        commission_value=Decimal("25.0000"),
        commission_currency="USD",
        terms_version="terms-2026-10",
        commission_terms_url="https://seller.example.com/affiliate-terms",
        seller_authorization_url="https://seller.example.com/brand-authorization",
        allowed_regions_json=["US", "GB"],
        restricted_traffic_sources_json=["incentivized"],
        affiliate_disclosure="Affiliate disclosure: publishers may earn commissions from qualifying purchases.",
        status="approved",
        terms_verified=True,
        seller_authorization_verified=True,
        activation_allowed=True,
        affiliate_network_approval_status="not_configured",
        marketplace_listed=False,
    )


def make_client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'marketplace-applications.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            merchant = Workspace(name="Seller workspace", slug="marketplace-seller")
            wrong_merchant = Workspace(name="Unrelated seller", slug="marketplace-other-seller")
            publisher = Workspace(name="Publisher workspace", slug="marketplace-publisher")
            another_publisher = Workspace(name="Other publisher", slug="marketplace-other-publisher")
            db.add_all([merchant, wrong_merchant, publisher, another_publisher])
            await db.flush()
            merchant_id, wrong_merchant_id, publisher_id, another_publisher_id = (
                merchant.id, wrong_merchant.id, publisher.id, another_publisher.id
            )
            offer = seed_offer(merchant_id)
            with workspace_scope(merchant_id):
                db.add(offer)
                await db.flush()
            await db.commit()
            return merchant_id, wrong_merchant_id, publisher_id, another_publisher_id, offer.id

    merchant_id, wrong_merchant_id, publisher_id, another_publisher_id, offer_id = asyncio.run(setup())
    user = {
        "workspace_id": publisher_id, "workspace_role": "owner",
        "email": "publisher@example.com", "user_id": "publisher-user", "is_admin": False,
    }

    async def override_session():
        async with sessions() as db:
            yield db

    async def override_auth():
        return user

    main.app.dependency_overrides[get_session] = override_session
    main.app.dependency_overrides[main.require_auth] = override_auth
    return engine, user, merchant_id, wrong_merchant_id, publisher_id, another_publisher_id, offer_id, TestClient(main.app)


def cleanup(engine, client):
    main.app.dependency_overrides.pop(get_session, None)
    main.app.dependency_overrides.pop(main.require_auth, None)
    client.close()
    asyncio.run(engine.dispose())


def test_listed_offer_is_visible_to_other_workspaces_and_application_is_reviewed_by_owner(tmp_path):
    engine, user, merchant_id, wrong_merchant_id, publisher_id, another_publisher_id, offer_id, client = make_client(tmp_path)
    try:
        with client:
            assert client.get("/api/marketplace/offers").json()["count"] == 0
            hidden_apply = client.post(f"/api/marketplace/offers/{offer_id}/applications", json=application_payload())
            assert hidden_apply.status_code == 404, hidden_apply.text

            user["workspace_id"] = merchant_id
            listed = client.post(f"/api/merchant/offers/{offer_id}/list")
            assert listed.status_code == 200, listed.text
            assert listed.json()["marketplace_listed"] is True
            assert listed.json()["affiliate_network_approval_status"] == "not_configured"

            user["workspace_id"] = publisher_id
            catalog = client.get("/api/marketplace/offers")
            assert catalog.status_code == 200, catalog.text
            assert catalog.json()["count"] == 1
            public_offer = catalog.json()["data"][0]
            assert public_offer["id"] == offer_id
            assert public_offer["affiliate_network_approved"] is False
            assert public_offer["provider_submission_performed"] is False
            assert "seller_authorization_url" not in public_offer
            assert "reviewer_notes" not in public_offer
            assert "created_by" not in public_offer

            submitted = client.post(f"/api/marketplace/offers/{offer_id}/applications", json=application_payload())
            assert submitted.status_code == 201, submitted.text
            application = submitted.json()
            assert application["status"] == "pending_review"
            assert application["terms_snapshot"]["terms_version"] == "terms-2026-10"
            assert application["compliance_answers"]["contact_sharing_consent"] is True
            assert application["provider_submission_status"] == "not_configured"
            assert application["affiliate_network_approved"] is False
            duplicate = client.post(f"/api/marketplace/offers/{offer_id}/applications", json=application_payload())
            assert duplicate.status_code == 409, duplicate.text
            assert client.get("/api/marketplace/applications").json()["count"] == 1

            user["workspace_id"] = another_publisher_id
            assert client.get("/api/marketplace/applications").json()["count"] == 0
            assert client.get("/api/marketplace/offers").json()["count"] == 1

            user["workspace_id"] = wrong_merchant_id
            assert client.get("/api/merchant/applications").json()["count"] == 0
            wrong_review = client.post(f"/api/merchant/applications/{application['id']}/review", json={"decision": "approve"})
            assert wrong_review.status_code == 404, wrong_review.text

            user["workspace_id"] = merchant_id
            incoming = client.get("/api/merchant/applications")
            assert incoming.status_code == 200
            assert incoming.json()["count"] == 1
            reviewed = client.post(f"/api/merchant/applications/{application['id']}/review", json={
                "decision": "approve", "reviewer_notes": "Publisher plan and compliance declarations reviewed."
            })
            assert reviewed.status_code == 200, reviewed.text
            assert reviewed.json()["status"] == "approved"
            assert reviewed.json()["affiliate_network_approved"] is False
            assert reviewed.json()["provider_submission_performed"] is False

            user["workspace_id"] = publisher_id
            outgoing = client.get("/api/marketplace/applications")
            assert outgoing.json()["data"][0]["status"] == "approved"

            user["workspace_id"] = merchant_id
            unlisted = client.post(f"/api/merchant/offers/{offer_id}/unlist")
            assert unlisted.status_code == 200, unlisted.text
            assert unlisted.json()["marketplace_listed"] is False
            user["workspace_id"] = publisher_id
            assert client.get("/api/marketplace/offers").json()["count"] == 0
    finally:
        cleanup(engine, client)


def test_merchant_can_reject_an_application_and_review_is_one_time(tmp_path):
    engine, user, merchant_id, _, publisher_id, _, offer_id, client = make_client(tmp_path)
    try:
        with client:
            user["workspace_id"] = merchant_id
            assert client.post(f"/api/merchant/offers/{offer_id}/list").status_code == 200
            user["workspace_id"] = publisher_id
            submitted = client.post(f"/api/marketplace/offers/{offer_id}/applications", json=application_payload())
            assert submitted.status_code == 201, submitted.text
            user["workspace_id"] = merchant_id
            rejected = client.post(f"/api/merchant/applications/{submitted.json()['id']}/review", json={
                "decision": "reject", "reviewer_notes": "Traffic-source plan needs changes."
            })
            assert rejected.status_code == 200, rejected.text
            assert rejected.json()["status"] == "rejected"
            again = client.post(f"/api/merchant/applications/{submitted.json()['id']}/review", json={"decision": "approve"})
            assert again.status_code == 409
    finally:
        cleanup(engine, client)


def test_member_cannot_publish_marketplace_offers_or_review_applications(tmp_path):
    engine, user, merchant_id, _, _, _, offer_id, client = make_client(tmp_path)
    try:
        with client:
            user["workspace_id"] = merchant_id
            user["workspace_role"] = "member"
            assert client.post(f"/api/merchant/offers/{offer_id}/list").status_code == 403
            assert client.get("/api/merchant/applications").status_code == 403
    finally:
        cleanup(engine, client)


def test_marketplace_application_requires_compliance_attestations_and_public_url():
    payload = application_payload()
    payload["contact_sharing_consent"] = False
    with pytest.raises(ValidationError):
        MarketplaceApplicationCreateRequest.model_validate(payload)
    payload = application_payload()
    payload["publisher_website_url"] = "http://127.0.0.1/private"
    with pytest.raises(ValidationError):
        MarketplaceApplicationCreateRequest.model_validate(payload)
