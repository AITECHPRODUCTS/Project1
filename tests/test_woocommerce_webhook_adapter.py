from __future__ import annotations

import base64
import hashlib
import hmac

from backend.adapters.woocommerce_webhook import (
    normalize_woocommerce_webhook_event,
    verify_woocommerce_webhook_signature,
)

SECRET = "woo-signing-secret-" + "w" * 40


def _signature(body: bytes) -> str:
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def _order(**updates):
    order = {
        "id": 723, "status": "processing", "currency": "USD", "total": "100.00",
        "date_paid_gmt": "2026-10-31T12:30:00",
        "meta_data": [{"id": 1, "key": "omni_click_id", "value": "click-123"}],
        "refunds": [],
    }
    order.update(updates)
    return order


def test_signature_checks_exact_body_and_rejects_invalid_signature_or_secret():
    body = b'{"id":723,"status":"processing"}'
    signature = _signature(body)
    assert verify_woocommerce_webhook_signature(body, signature, SECRET)
    assert not verify_woocommerce_webhook_signature(body + b" ", signature, SECRET)
    assert not verify_woocommerce_webhook_signature(body, signature, "short")
    assert not verify_woocommerce_webhook_signature(body, "not-base64", SECRET)


def test_paid_order_maps_to_stable_sale_event_and_preserves_delivery_id():
    normalized, reason = normalize_woocommerce_webhook_event(_order(), "order.updated", "delivery-001")
    assert reason == ""
    assert normalized == {
        "event_id": "wc-order-723", "event_type": "sale", "click_id": "click-123",
        "revenue": "100.00", "currency": "USD",
        "source_provider_event_id": "delivery-001",
        "occurred_at": "2026-10-31T12:30:00+00:00",
    }


def test_unpaid_or_unsupported_topics_are_not_sales():
    unpaid, reason = normalize_woocommerce_webhook_event(
        _order(status="pending"), "order.created", "delivery-002",
    )
    assert unpaid is None and reason == "woocommerce_order_not_paid"
    ignored, reason = normalize_woocommerce_webhook_event(
        _order(), "product.updated", "delivery-003",
    )
    assert ignored is None and reason == "unsupported_woocommerce_topic"


def test_missing_click_reference_is_manual_review():
    normalized, reason = normalize_woocommerce_webhook_event(
        _order(meta_data=[]), "order.updated", "delivery-004",
    )
    assert normalized is None and reason == "missing_affiliate_click_reference"


def test_subscription_renewal_requires_explicit_original_order_metadata():
    renewal = _order(meta_data=[{"key": "omni_original_order_id", "value": "700"}])
    normalized, reason = normalize_woocommerce_webhook_event(renewal, "order.updated", "delivery-005")
    assert reason == ""
    assert normalized["event_type"] == "subscription_renewal"
    assert normalized["event_id"] == "wc-order-723"
    assert normalized["original_event_id"] == "wc-order-700"


def test_partial_and_inconsistent_refunds_are_not_auto_reversed():
    partial = _order(refunds=[{"id": 1, "total": "-25.00"}])
    normalized, reason = normalize_woocommerce_webhook_event(partial, "order.updated", "delivery-006")
    assert normalized is None and reason == "partial_refund_requires_reconciliation"
    inconsistent = _order(status="refunded", refunds=[{"id": 1, "total": "-110.00"}])
    normalized, reason = normalize_woocommerce_webhook_event(inconsistent, "order.updated", "delivery-007")
    assert normalized is None and reason == "refund_total_inconsistent_requires_reconciliation"


def test_only_exact_full_refund_is_normalized_as_reversal():
    full = _order(status="refunded", refunds=[
        {"id": 1, "total": "-40.00"}, {"id": 2, "total": "-60.00"},
    ])
    normalized, reason = normalize_woocommerce_webhook_event(full, "order.updated", "delivery-008")
    assert reason == ""
    assert normalized["event_type"] == "refund"
    assert normalized["event_id"] == "wc-order-723-full-refund"
    assert normalized["original_event_id"] == "wc-order-723"


def test_missing_gmt_payment_time_is_not_inferred_from_local_clock():
    normalized, reason = normalize_woocommerce_webhook_event(
        _order(date_paid_gmt=None, date_paid="2026-10-31T12:30:00"),
        "order.updated", "delivery-009",
    )
    assert normalized is None and reason == "paid_order_missing_utc_payment_time"
