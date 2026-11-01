from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
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

            held_report = client.get("/api/merchant/payout-readiness")
            assert held_report.status_code == 200, held_report.text
            held_item = held_report.json()["data"][0]
            assert held_item["program_name"] == "Recurring creator platform"
            assert held_item["currency"] == "USD"
            assert held_item["gross_commission"] == "50.000000"
            assert held_item["reversed_commission"] == "25.000000"
            assert held_item["net_commission"] == "25.000000"
            assert held_item["held_commission"] == "25.000000"
            assert held_item["eligible_commission"] == "0.000000"
            assert held_item["payout_state"] == "refund_hold"
            assert held_item["payout_confirmed"] is False
            assert held_item["transfers_initiated"] is False

            async def release_refund_hold_for_test():
                async with sessions() as db:
                    with workspace_scope(merchant_id):
                        merchant_offer = await db.get(MerchantOffer, offer_id)
                        merchant_offer.refund_hold_days = 0
                        await db.commit()
            asyncio.run(release_refund_hold_for_test())
            eligible_report = client.get("/api/merchant/payout-readiness")
            assert eligible_report.status_code == 200, eligible_report.text
            eligible_item = eligible_report.json()["data"][0]
            assert eligible_item["eligible_commission"] == "25.000000"
            assert eligible_item["threshold_reached"] is True
            assert eligible_item["payout_state"] == "eligible_for_manual_review"
            assert eligible_item["payout_confirmed"] is False
            assert eligible_report.json()["money_transferred"] is False
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


def stripe_signed_headers(body: bytes, secret: str) -> dict[str, str]:
    timestamp = int(time.time())
    digest = hmac.new(secret.encode("utf-8"), str(timestamp).encode("ascii") + b"." + body, hashlib.sha256).hexdigest()
    return {"Stripe-Signature": f"t={timestamp},v1={digest}", "Content-Type": "application/json"}


def test_native_stripe_webhook_creates_conversion_and_full_refund_reversal(tmp_path):
    engine, sessions, user, merchant_id, publisher_id, offer_id, application_id, client = setup_client(tmp_path)
    try:
        with client:
            approved = client.post(
                f"/api/merchant/applications/{application_id}/review",
                json={"decision": "approve", "reviewer_notes": "Reviewed publisher traffic and disclosures."},
            )
            assert approved.status_code == 200, approved.text

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
            created = client.post(
                f"/api/merchant/offers/{offer_id}/stripe-integration",
                json={"display_name": "Stripe checkout endpoint"},
            )
            assert created.status_code == 201, created.text
            integration = created.json()
            assert integration["integration_type"] == "stripe_webhook"
            assert integration["signing_secret_configured"] is False
            assert "charge.dispute.created" in integration["setup_events"]

            secret = "whsec_" + "t" * 40
            configured = client.post(
                f"/api/merchant/integrations/{integration['id']}/stripe-secret",
                json={"webhook_signing_secret": secret},
            )
            assert configured.status_code == 200, configured.text
            assert configured.json()["signing_secret_configured"] is True
            assert configured.json()["secret_fingerprint"] != integration["secret_fingerprint"]
            listing = client.get("/api/merchant/integrations")
            assert listing.status_code == 200
            assert secret not in listing.text
            assert "secret_ciphertext" not in listing.text

            envelope = {
                "id": "evt_pi_success_1", "object": "event", "type": "payment_intent.succeeded",
                "created": int(time.time()),
                "data": {"object": {
                    "id": "pi_affiliate_1", "object": "payment_intent", "status": "succeeded",
                    "invoice": None, "amount_received": 10000, "currency": "usd",
                    "metadata": {"omni_click_id": click_id},
                }},
            }
            raw = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
            invalid = client.post(
                f"/api/webhooks/merchant-integrations/{integration['id']}",
                content=raw, headers={"Stripe-Signature": "t=1,v1=" + "0" * 64},
            )
            assert invalid.status_code == 401
            sale = client.post(
                f"/api/webhooks/merchant-integrations/{integration['id']}",
                content=raw, headers=stripe_signed_headers(raw, secret),
            )
            assert sale.status_code == 200, sale.text
            assert sale.json()["status"] == "recorded"
            assert sale.json()["commission"] == "25.000000"
            assert sale.json()["payout_status"] == "not_confirmed"

            duplicate = client.post(
                f"/api/webhooks/merchant-integrations/{integration['id']}",
                content=raw, headers=stripe_signed_headers(raw, secret),
            )
            assert duplicate.status_code == 200
            assert duplicate.json()["status"] == "duplicate_ignored"

            partial_envelope = {
                "id": "evt_partial_refund", "object": "event", "type": "charge.refunded",
                "created": int(time.time()),
                "data": {"object": {
                    "id": "ch_affiliate_1", "payment_intent": "pi_affiliate_1",
                    "amount": 10000, "amount_refunded": 1500, "currency": "usd",
                }},
            }
            partial_raw = json.dumps(partial_envelope, separators=(",", ":")).encode("utf-8")
            partial = client.post(
                f"/api/webhooks/merchant-integrations/{integration['id']}",
                content=partial_raw, headers=stripe_signed_headers(partial_raw, secret),
            )
            assert partial.status_code == 202
            assert partial.json()["status"] == "manual_review_required"
            assert partial.json()["stored"] is True
            assert partial.json()["receipt_id"]

            duplicate_partial = client.post(
                f"/api/webhooks/merchant-integrations/{integration['id']}",
                content=partial_raw, headers=stripe_signed_headers(partial_raw, secret),
            )
            assert duplicate_partial.status_code == 200
            assert duplicate_partial.json()["status"] == "duplicate_ignored"
            assert duplicate_partial.json()["receipt_id"] == partial.json()["receipt_id"]

            manual_queue = client.get(
                f"/api/merchant/integrations/{integration['id']}/manual-review-events"
            )
            assert manual_queue.status_code == 200, manual_queue.text
            assert manual_queue.json()["count"] == 1
            assert manual_queue.json()["data"][0]["provider_event_id"] == "evt_partial_refund"
            assert manual_queue.json()["data"][0]["outcome"] == "partial_refund_review"

            dispute_envelope = {
                "id": "evt_dispute", "object": "event", "type": "charge.dispute.created",
                "created": int(time.time()),
                "data": {"object": {"id": "dp_1", "amount": 10000, "currency": "usd"}},
            }
            dispute_raw = json.dumps(dispute_envelope, separators=(",", ":")).encode("utf-8")
            dispute = client.post(
                f"/api/webhooks/merchant-integrations/{integration['id']}",
                content=dispute_raw, headers=stripe_signed_headers(dispute_raw, secret),
            )
            assert dispute.status_code == 202
            assert dispute.json()["status"] == "manual_review_required"
            assert dispute.json()["stored"] is True
            updated_queue = client.get(
                f"/api/merchant/integrations/{integration['id']}/manual-review-events"
            )
            assert updated_queue.status_code == 200, updated_queue.text
            assert updated_queue.json()["count"] == 2
            assert {row["outcome"] for row in updated_queue.json()["data"]} == {
                "partial_refund_review", "dispute_review",
            }

            refund_envelope = {
                "id": "evt_full_refund", "object": "event", "type": "charge.refunded",
                "created": int(time.time()),
                "data": {"object": {
                    "id": "ch_affiliate_1", "payment_intent": "pi_affiliate_1",
                    "amount": 10000, "amount_refunded": 10000, "currency": "usd",
                }},
            }
            refund_raw = json.dumps(refund_envelope, separators=(",", ":")).encode("utf-8")
            refund = client.post(
                f"/api/webhooks/merchant-integrations/{integration['id']}",
                content=refund_raw, headers=stripe_signed_headers(refund_raw, secret),
            )
            assert refund.status_code == 200, refund.text
            assert refund.json()["status"] == "reversed"
            assert refund.json()["commission"] == "-25.000000"

            async def inspect():
                async with sessions() as db:
                    with workspace_scope(publisher_id):
                        conversions = list((await db.scalars(select(Conversion).where(
                            Conversion.network == "merchant-" + integration["id"]
                        ))).all())
                        ledger = list((await db.scalars(select(ConversionLedgerEntry).where(
                            ConversionLedgerEntry.network == "merchant-" + integration["id"]
                        ))).all())
                    with workspace_scope(merchant_id):
                        saved = await db.get(MerchantWebhookIntegration, integration["id"])
                    return conversions, ledger, saved
            conversions, ledger, saved = asyncio.run(inspect())
            assert len(conversions) == 2
            assert len(ledger) == 2
            original = next(row for row in conversions if row.external_event_id == "pi_affiliate_1")
            assert original.status == "reversed"
            assert original.event_json["source_provider"] == "stripe"
            assert original.event_json["source_provider_event_id"] == "evt_pi_success_1"
            assert saved.status == "connected_write"
            assert saved.secret_version == 2
            assert saved.last_error_code is None
    finally:
        cleanup(engine, client)


def test_stripe_secret_required_and_generic_rotation_cannot_replace_it(tmp_path):
    engine, sessions, user, merchant_id, publisher_id, offer_id, application_id, client = setup_client(tmp_path)
    try:
        with client:
            created = client.post(
                f"/api/merchant/offers/{offer_id}/stripe-integration",
                json={"display_name": "Stripe checkout endpoint"},
            )
            assert created.status_code == 201, created.text
            endpoint = created.json()
            raw = json.dumps({"id": "evt_test", "type": "payment_intent.succeeded"}).encode()
            response = client.post(
                f"/api/webhooks/merchant-integrations/{endpoint['id']}",
                content=raw, headers={"Stripe-Signature": "t=1,v1=" + "0" * 64},
            )
            assert response.status_code == 503
            rotate = client.post(f"/api/merchant/integrations/{endpoint['id']}/rotate-secret")
            assert rotate.status_code == 409
            invalid_secret = client.post(
                f"/api/merchant/integrations/{endpoint['id']}/stripe-secret",
                json={"webhook_signing_secret": "sk_test_not_a_webhook_secret"},
            )
            assert invalid_secret.status_code == 422
    finally:
        cleanup(engine, client)


def test_disabled_custom_endpoint_can_be_reconfigured_as_native_stripe(tmp_path):
    engine, sessions, user, merchant_id, publisher_id, offer_id, application_id, client = setup_client(tmp_path)
    try:
        with client:
            custom = client.post(
                f"/api/merchant/offers/{offer_id}/webhook-integration",
                json={"provider_name": "custom", "display_name": "Legacy custom relay"},
            )
            assert custom.status_code == 201, custom.text
            integration_id = custom.json()["id"]
            disabled = client.post(f"/api/merchant/integrations/{integration_id}/disable")
            assert disabled.status_code == 200, disabled.text
            stripe = client.post(
                f"/api/merchant/offers/{offer_id}/stripe-integration",
                json={"display_name": "Native Stripe"},
            )
            assert stripe.status_code == 201, stripe.text
            assert stripe.json()["id"] == integration_id
            assert stripe.json()["integration_type"] == "stripe_webhook"
            assert stripe.json()["signing_secret_configured"] is False
    finally:
        cleanup(engine, client)



def woocommerce_signed_headers(body: bytes, secret: str, delivery_id: str, topic: str = "order.updated") -> dict[str, str]:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return {
        "X-WC-Webhook-Signature": base64.b64encode(digest).decode("ascii"),
        "X-WC-Webhook-Topic": topic,
        "X-WC-Webhook-Delivery-ID": delivery_id,
        "Content-Type": "application/json",
    }


def test_native_woocommerce_webhook_records_one_paid_order_and_full_refund(tmp_path):
    engine, sessions, user, merchant_id, publisher_id, offer_id, application_id, client = setup_client(tmp_path)
    try:
        with client:
            approved = client.post(
                f"/api/merchant/applications/{application_id}/review",
                json={"decision": "approve", "reviewer_notes": "Reviewed publisher traffic and disclosures."},
            )
            assert approved.status_code == 200, approved.text

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
            created = client.post(
                f"/api/merchant/offers/{offer_id}/webhook-integration",
                json={"provider_name": "woocommerce", "display_name": "WooCommerce store"},
            )
            assert created.status_code == 201, created.text
            integration = created.json()
            secret = integration["signing_secret_once"]
            assert integration["integration_type"] == "woocommerce_webhook"
            assert integration["setup_events"] == ["order.created", "order.updated"]

            order = {
                "id": 723, "status": "processing", "currency": "USD", "total": "100.00",
                "date_paid_gmt": "2026-10-31T12:30:00",
                "meta_data": [{"id": 1, "key": "omni_click_id", "value": click_id}],
                "refunds": [],
            }
            raw = json.dumps(order, separators=(",", ":")).encode("utf-8")
            invalid = client.post(
                f"/api/webhooks/merchant-integrations/{integration['id']}",
                content=raw, headers={
                    **woocommerce_signed_headers(raw, secret, "delivery-invalid"),
                    "X-WC-Webhook-Signature": "invalid",
                },
            )
            assert invalid.status_code == 401

            sale = client.post(
                f"/api/webhooks/merchant-integrations/{integration['id']}",
                content=raw, headers=woocommerce_signed_headers(raw, secret, "delivery-001"),
            )
            assert sale.status_code == 200, sale.text
            assert sale.json()["status"] == "recorded"
            assert sale.json()["commission"] == "25.000000"
            assert sale.json()["payout_status"] == "not_confirmed"

            duplicate = client.post(
                f"/api/webhooks/merchant-integrations/{integration['id']}",
                content=raw, headers=woocommerce_signed_headers(raw, secret, "delivery-001"),
            )
            assert duplicate.status_code == 200
            assert duplicate.json()["status"] == "duplicate_ignored"

            changed_order = {**order, "customer_note": "updated after payment"}
            changed_raw = json.dumps(changed_order, separators=(",", ":")).encode("utf-8")
            repeated = client.post(
                f"/api/webhooks/merchant-integrations/{integration['id']}",
                content=changed_raw, headers=woocommerce_signed_headers(changed_raw, secret, "delivery-002"),
            )
            assert repeated.status_code == 200
            assert repeated.json()["status"] == "duplicate_ignored"

            partial_order = {**order, "refunds": [{"id": 726, "total": "-25.00"}]}
            partial_raw = json.dumps(partial_order, separators=(",", ":")).encode("utf-8")
            partial = client.post(
                f"/api/webhooks/merchant-integrations/{integration['id']}",
                content=partial_raw, headers=woocommerce_signed_headers(partial_raw, secret, "delivery-003"),
            )
            assert partial.status_code == 202
            assert partial.json()["status"] == "manual_review_required"
            assert partial.json()["stored"] is True

            full_order = {
                **order, "status": "refunded", "refunds": [{"id": 726, "total": "-100.00"}],
            }
            full_raw = json.dumps(full_order, separators=(",", ":")).encode("utf-8")
            full = client.post(
                f"/api/webhooks/merchant-integrations/{integration['id']}",
                content=full_raw, headers=woocommerce_signed_headers(full_raw, secret, "delivery-004"),
            )
            assert full.status_code == 200, full.text
            assert full.json()["status"] == "reversed"

            manual = client.get(f"/api/merchant/integrations/{integration['id']}/manual-review-events")
            assert manual.status_code == 200
            assert any(row["outcome"] == "partial_refund_review" for row in manual.json()["data"])

            async def inspect():
                async with sessions() as db:
                    with workspace_scope(publisher_id):
                        conversions = list((await db.scalars(select(Conversion).where(
                            Conversion.network == "merchant-" + integration["id"]
                        ))).all())
                        ledger = list((await db.scalars(select(ConversionLedgerEntry).where(
                            ConversionLedgerEntry.network == "merchant-" + integration["id"]
                        ))).all())
                    return conversions, ledger
            conversions, ledger = asyncio.run(inspect())
            assert len(conversions) == 2
            assert len(ledger) == 2
            sale_row = next(row for row in conversions if row.external_event_id == "wc-order-723")
            refund_row = next(row for row in conversions if row.external_event_id == "wc-order-723-full-refund")
            assert sale_row.status == "reversed"
            assert refund_row.status == "reversed"
            assert sale_row.event_json["source_provider"] == "woocommerce"
            assert sale_row.event_json["source_provider_event_id"] == "delivery-001"
    finally:
        cleanup(engine, client)
