from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import main
from backend.database import Base, get_session
from backend.models import (
    Campaign, ClickEvent, Conversion, ConversionLedgerEntry, MarketplaceApplication,
    MerchantOffer, MerchantWebhookIntegration, MerchantWebhookReceipt, Workspace,
)
from backend.tenancy import workspace_scope


def signed_headers(body: bytes, secret: str) -> dict[str, str]:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return {"X-Omni-Signature": "sha256=" + digest, "Content-Type": "application/json"}


def setup_client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'merchant-partner-lifecycle.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def seed():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            merchant = Workspace(name="Merchant partner workspace", slug="merchant-partner-workspace")
            publisher = Workspace(name="Publisher partner workspace", slug="publisher-partner-workspace")
            db.add_all([merchant, publisher])
            await db.flush()
            offer = MerchantOffer(
                workspace_id=merchant.id, created_by="creator@merchant.example",
                name="Recurring creator platform", product_url="https://merchant.example.com/product",
                description="A workflow platform for independent creators and small publisher teams.",
                category="creator-software", commission_type="recurring_percentage",
                commission_value=Decimal("25.0000"), commission_currency="USD",
                cookie_days=90, attribution_window_days=90, refund_hold_days=15,
                minimum_payout_amount=Decimal("20.00"), payout_schedule="monthly",
                terms_version="terms-v1", commission_terms_url="https://merchant.example.com/affiliate-terms",
                seller_authorization_url="https://merchant.example.com/authorization",
                allowed_regions_json=["US", "GB"], restricted_traffic_sources_json=["incentivized"],
                affiliate_disclosure="Affiliate disclosure: publishers may earn commissions from qualifying purchases.",
                status="approved", terms_verified=True, seller_authorization_verified=True,
                activation_allowed=True, affiliate_network_approval_status="not_configured",
                marketplace_listed=True,
            )
            with workspace_scope(merchant.id):
                db.add(offer)
                await db.flush()
            application = MarketplaceApplication(
                workspace_id=publisher.id, merchant_workspace_id=merchant.id, merchant_offer_id=offer.id,
                applicant_email="publisher@example.com", publisher_website_url="https://publisher.example.com",
                audience_description="Readers evaluating creator software for small teams.",
                traffic_sources_json=["seo", "blog"], intended_regions_json=["US", "GB"],
                promotion_plan="We publish documented product reviews, maintain sources and disclose qualifying affiliate relationships in each relevant asset.",
                compliance_answers_json={"offer_terms_reviewed": True, "traffic_restrictions_reviewed": True,
                                        "affiliate_disclosure_ready": True, "contact_sharing_consent": True},
                terms_snapshot_json={"name": offer.name, "terms_version": "terms-v1"},
                status="pending_review",
            )
            with workspace_scope(publisher.id):
                db.add(application)
                await db.flush()
            await db.commit()
            return merchant.id, publisher.id, offer.id, application.id

    merchant_id, publisher_id, offer_id, application_id = asyncio.run(seed())
    user = {
        "workspace_id": merchant_id, "workspace_role": "owner", "email": "reviewer@merchant.example",
        "user_id": "merchant-reviewer", "is_admin": False, "account_type": "merchant_product_owner",
    }

    async def override_session():
        async with sessions() as db:
            yield db

    async def override_auth():
        return user

    main.app.dependency_overrides[get_session] = override_session
    main.app.dependency_overrides[main.require_auth] = override_auth
    return engine, sessions, user, merchant_id, publisher_id, offer_id, application_id, TestClient(main.app)


def cleanup(engine, client):
    main.app.dependency_overrides.pop(get_session, None)
    main.app.dependency_overrides.pop(main.require_auth, None)
    client.close()
    asyncio.run(engine.dispose())


def test_merchant_approval_issues_partner_link_and_signed_events_create_and_reverse_commission(tmp_path):
    engine, sessions, user, merchant_id, publisher_id, offer_id, application_id, client = setup_client(tmp_path)
    try:
        with client:
            approved = client.post(
                f"/api/merchant/applications/{application_id}/review",
                json={"decision": "approve", "reviewer_notes": "Promotion plan and allowed traffic reviewed."},
            )
            assert approved.status_code == 200, approved.text
            assert approved.json()["status"] == "approved"
            assert approved.json()["promotion_url"].endswith("/r/" + approved.json()["promotion_campaign_id"])

            user.update(workspace_id=publisher_id, account_type="affiliate_publisher", email="publisher@example.com")
            apps = client.get("/api/marketplace/applications")
            assert apps.status_code == 200, apps.text
            partner_app = apps.json()["data"][0]
            assert partner_app["promotion_url"] == approved.json()["promotion_url"]
            assert partner_app["tracked_clicks"] == 0
            assert partner_app["promotion_link_status"] == "active"

            async def seed_click():
                async with sessions() as db:
                    with workspace_scope(publisher_id):
                        campaign = await db.get(Campaign, approved.json()["promotion_campaign_id"])
                        click = ClickEvent(
                            workspace_id=publisher_id, campaign_id=campaign.id,
                            destination_url=campaign.primary_destination,
                            chosen_destination=campaign.primary_destination, status_code=302,
                        )
                        db.add(click)
                        await db.commit()
                        await db.refresh(click)
                        return click.click_id
            click_id = asyncio.run(seed_click())

            user.update(workspace_id=merchant_id, account_type="merchant_product_owner", email="reviewer@merchant.example")
            integration_response = client.post(
                f"/api/merchant/offers/{offer_id}/webhook-integration",
                json={"provider_name": "custom", "display_name": "Merchant checkout events"},
            )
            assert integration_response.status_code == 201, integration_response.text
            integration = integration_response.json()
            secret = integration["signing_secret_once"]
            assert integration["status"] == "pending_authorization"
            assert "secret_ciphertext" not in integration
            listing = client.get("/api/merchant/integrations")
            assert listing.status_code == 200
            assert "signing_secret_once" not in listing.text

            sale = {"event_id": "order-2026-001", "event_type": "sale", "click_id": click_id,
                    "revenue": "100.00", "currency": "USD"}
            raw_sale = json.dumps(sale, separators=(",", ":")).encode("utf-8")
            invalid = client.post(
                "/api/webhooks/merchant-integrations/" + integration["id"],
                content=raw_sale,
                headers={"X-Omni-Signature": "sha256=" + "0" * 64, "Content-Type": "application/json"},
            )
            assert invalid.status_code == 401

            recorded = client.post(
                "/api/webhooks/merchant-integrations/" + integration["id"],
                content=raw_sale, headers=signed_headers(raw_sale, secret),
            )
            assert recorded.status_code == 200, recorded.text
            assert recorded.json()["status"] == "recorded"
            assert recorded.json()["commission"] == "25.000000"
            assert recorded.json()["evidence_status"] == "merchant_signed_webhook_verified"
            assert recorded.json()["payout_status"] == "not_confirmed"

            duplicate = client.post(
                "/api/webhooks/merchant-integrations/" + integration["id"],
                content=raw_sale, headers=signed_headers(raw_sale, secret),
            )
            assert duplicate.status_code == 200
            assert duplicate.json()["status"] == "duplicate_ignored"

            renewal = {
                "event_id": "renewal-2026-001",
                "event_type": "subscription_renewal",
                "original_event_id": "order-2026-001",
                "revenue": "100.00",
                "currency": "USD",
            }
            raw_renewal = json.dumps(renewal, separators=(",", ":")).encode("utf-8")
            renewed = client.post(
                "/api/webhooks/merchant-integrations/" + integration["id"],
                content=raw_renewal, headers=signed_headers(raw_renewal, secret),
            )
            assert renewed.status_code == 200, renewed.text
            assert renewed.json()["status"] == "recorded"
            assert renewed.json()["commission"] == "25.000000"

            conflicting_sale = {**sale, "revenue": "120.00"}
            conflicting_raw = json.dumps(conflicting_sale, separators=(",", ":")).encode("utf-8")
            conflicting = client.post(
                "/api/webhooks/merchant-integrations/" + integration["id"],
                content=conflicting_raw, headers=signed_headers(conflicting_raw, secret),
            )
            assert conflicting.status_code == 409

            refund = {"event_id": "refund-2026-001", "event_type": "refund",
                      "original_event_id": "order-2026-001", "currency": "USD"}
            raw_refund = json.dumps(refund, separators=(",", ":")).encode("utf-8")
            reversed_response = client.post(
                "/api/webhooks/merchant-integrations/" + integration["id"],
                content=raw_refund, headers=signed_headers(raw_refund, secret),
            )
            assert reversed_response.status_code == 200, reversed_response.text
            assert reversed_response.json()["status"] == "reversed"
            assert reversed_response.json()["commission"] == "-25.000000"

            async def inspect():
                async with sessions() as db:
                    with workspace_scope(publisher_id):
                        ledger = list((await db.scalars(select(ConversionLedgerEntry).where(
                            ConversionLedgerEntry.network == "merchant-" + integration["id"]
                        ).order_by(ConversionLedgerEntry.created_at.asc()))).all())
                        conversions = list((await db.scalars(select(Conversion).where(
                            Conversion.network == "merchant-" + integration["id"]
                        ))).all())
                    with workspace_scope(merchant_id):
                        saved_integration = await db.get(MerchantWebhookIntegration, integration["id"])
                    with workspace_scope(None):
                        receipts = list((await db.scalars(select(MerchantWebhookReceipt).where(
                            MerchantWebhookReceipt.integration_id == integration["id"]
                        ))).all())
                    return ledger, conversions, saved_integration, receipts

            ledger, conversions, saved_integration, receipts = asyncio.run(inspect())
            assert len(ledger) == 3
            assert sum((row.commission_amount for row in ledger), Decimal("0")) == Decimal("25.000000")
            assert {row.evidence_status for row in ledger} == {"merchant_signed_webhook_verified"}
            assert len(conversions) == 3
            assert next(row for row in conversions if row.external_event_id == "order-2026-001").status == "reversed"
            assert next(row for row in conversions if row.external_event_id == "renewal-2026-001").status == "pending"
            assert saved_integration.status == "connected_write"
            assert saved_integration.last_event_at is not None
            assert len(receipts) == 3
            assert all(receipt.conversion_id for receipt in receipts)
    finally:
        cleanup(engine, client)


def test_merchant_cannot_create_webhook_for_another_workspace_offer(tmp_path):
    engine, sessions, user, merchant_id, publisher_id, offer_id, application_id, client = setup_client(tmp_path)
    try:
        with client:
            user.update(workspace_id=publisher_id, account_type="merchant_product_owner")
            response = client.post(
                "/api/merchant/offers/" + offer_id + "/webhook-integration",
                json={"provider_name": "custom", "display_name": "Unauthorized integration"},
            )
            assert response.status_code == 404
    finally:
        cleanup(engine, client)
