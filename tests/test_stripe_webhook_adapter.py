from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from backend.adapters.stripe_webhook import normalize_stripe_webhook_event, verify_stripe_webhook_signature
import backend.services.merchant_webhooks as merchant_webhooks

SECRET = "whsec_" + "s" * 40


def event(event_type: str, obj: dict, event_id: str = "evt_test"):
    return {
        "id": event_id, "object": "event", "type": event_type,
        "created": int(time.time()), "data": {"object": obj},
    }


def test_signature_checks_exact_raw_body_multiple_v1_and_timestamp():
    body = b'{"id":"evt_1","type":"payment_intent.succeeded"}'
    timestamp = int(time.time())
    digest = hmac.new(SECRET.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={'0' * 64},v1={digest}"
    assert verify_stripe_webhook_signature(body, header, SECRET)
    assert not verify_stripe_webhook_signature(body + b" ", header, SECRET)
    assert not verify_stripe_webhook_signature(body, header, "invalid")
    assert not verify_stripe_webhook_signature(body, f"t={timestamp-301},v1={digest}", SECRET, now=timestamp)
    assert not verify_stripe_webhook_signature(body, f"t={timestamp+301},v1={digest}", SECRET, now=timestamp)
    assert not verify_stripe_webhook_signature(body, "v1=" + "0" * 64, SECRET, now=timestamp)


def test_payment_intent_succeeded_maps_sale_and_preserves_provider_event_id():
    envelope = event("payment_intent.succeeded", {
        "id": "pi_sale_1", "object": "payment_intent", "status": "succeeded",
        "amount_received": 12345, "currency": "usd",
        "metadata": {"omni_click_id": "click-123"},
    }, "evt_pi_sale")
    normalized, reason = normalize_stripe_webhook_event(envelope)
    assert reason == "" and normalized is not None
    assert normalized["event_id"] == "pi_sale_1"
    assert normalized["event_type"] == "sale"
    assert normalized["click_id"] == "click-123"
    assert normalized["revenue"] == "123.450000"
    assert normalized["currency"] == "USD"
    assert normalized["source_provider_event_id"] == "evt_pi_sale"
    assert normalized["occurred_at"] == datetime.fromtimestamp(envelope["created"], tz=timezone.utc).isoformat()


def test_subscription_payment_intent_event_is_ignored_to_prevent_double_count():
    envelope = event("payment_intent.succeeded", {
        "id": "pi_subscription", "status": "succeeded", "invoice": "in_123",
        "amount_received": 2500, "currency": "usd",
        "metadata": {"omni_click_id": "click-1"},
    })
    normalized, reason = normalize_stripe_webhook_event(envelope)
    assert normalized is None
    assert reason == "subscription_payment_intent_handled_by_invoice_paid"


def test_invoice_paid_supports_legacy_and_current_payment_reference_shapes():
    initial = event("invoice.paid", {
        "id": "in_initial", "status": "paid", "billing_reason": "subscription_create",
        "payment_intent": "pi_start", "amount_paid": 2500, "currency": "usd",
        "metadata": {"omni_click_id": "click-1"},
    }, "evt_invoice_start")
    first, reason = normalize_stripe_webhook_event(initial)
    assert reason == "" and first
    assert first["event_type"] == "sale" and first["event_id"] == "pi_start"

    modern = event("invoice.paid", {
        "id": "in_cycle", "status": "paid", "billing_reason": "subscription_cycle",
        "amount_paid": 2500, "currency": "usd",
        "payments": {"data": [{
            "status": "paid", "amount_paid": 2500,
            "payment": {"type": "payment_intent", "payment_intent": "pi_cycle"},
        }]},
        "parent": {"subscription_details": {"metadata": {
            "omni_original_payment_intent_id": "pi_start",
        }}},
    }, "evt_invoice_cycle")
    recurring, reason = normalize_stripe_webhook_event(modern)
    assert reason == "" and recurring
    assert recurring["event_type"] == "subscription_renewal"
    assert recurring["original_event_id"] == "pi_start"
    assert recurring["event_id"] == "pi_cycle"


def test_zero_decimal_currencies_and_legacy_ugx_charge_units():
    jpy = event("payment_intent.succeeded", {
        "id": "pi_jpy", "status": "succeeded", "amount_received": 1200,
        "currency": "jpy", "metadata": {"click_id": "click-jpy"},
    })
    normalized, reason = normalize_stripe_webhook_event(jpy)
    assert reason == "" and normalized
    assert Decimal(normalized["revenue"]) == Decimal("1200.000000")

    ugx = event("payment_intent.succeeded", {
        "id": "pi_ugx", "status": "succeeded", "amount_received": 500,
        "currency": "ugx", "metadata": {"click_id": "click-ugx"},
    })
    normalized, reason = normalize_stripe_webhook_event(ugx)
    assert reason == "" and normalized
    assert Decimal(normalized["revenue"]) == Decimal("5.000000")


def test_out_of_band_invoice_partial_refunds_and_disputes_go_to_manual_review():
    out_of_band = event("invoice.paid", {
        "id": "in_manual", "status": "paid", "paid_out_of_band": True,
        "billing_reason": "subscription_create", "payment_intent": "pi_manual",
        "amount_paid": 1000, "currency": "usd", "metadata": {"click_id": "click-manual"},
    })
    normalized, reason = normalize_stripe_webhook_event(out_of_band)
    assert normalized is None and reason == "out_of_band_invoice_requires_manual_reconciliation"

    partial = event("charge.refunded", {
        "id": "ch_1", "payment_intent": "pi_1", "amount": 10000,
        "amount_refunded": 1200, "currency": "usd",
    }, "evt_partial")
    normalized, reason = normalize_stripe_webhook_event(partial)
    assert normalized is None and reason == "partial_refund_requires_reconciliation"

    dispute = event("charge.dispute.created", {
        "id": "dp_1", "charge": "ch_1", "amount": 10000, "currency": "usd",
    }, "evt_dispute")
    normalized, reason = normalize_stripe_webhook_event(dispute)
    assert normalized is None and reason == "chargeback_requires_manual_reconciliation"


def test_full_refund_maps_to_original_payment_intent():
    refund = event("charge.refunded", {
        "id": "ch_1", "payment_intent": "pi_original", "amount": 10000,
        "amount_refunded": 10000, "currency": "usd",
    }, "evt_full_refund")
    normalized, reason = normalize_stripe_webhook_event(refund)
    assert reason == "" and normalized
    assert normalized["event_type"] == "refund"
    assert normalized["event_id"] == "evt_full_refund"
    assert normalized["original_event_id"] == "pi_original"


def test_rotated_signing_secret_version_is_still_decryptable(monkeypatch):
    monkeypatch.setattr(
        merchant_webhooks, "get_settings",
        lambda: SimpleNamespace(app_session_secret="a sufficiently long test application session secret"),
    )
    secret = "whsec_" + "r" * 40
    encrypted = merchant_webhooks.encrypt_merchant_webhook_secret(secret)
    assert merchant_webhooks.decrypt_merchant_webhook_secret(encrypted, 2) == secret
