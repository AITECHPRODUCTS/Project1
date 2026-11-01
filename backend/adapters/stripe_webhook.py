"""Native Stripe webhook verification and affiliate-event normalization."""
from __future__ import annotations

import hashlib
import hmac
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

ZERO_DECIMAL_CURRENCIES = frozenset({
    "BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA", "PYG",
    "RWF", "VND", "VUV", "XAF", "XOF", "XPF",
})
SIGNATURE_TOLERANCE_SECONDS = 300


def verify_stripe_webhook_signature(
    raw_body: bytes, signature_header: str, secret: str, *,
    now: int | None = None, tolerance_seconds: int = SIGNATURE_TOLERANCE_SECONDS,
) -> bool:
    """Verify Stripe's timestamped HMAC-SHA256 signature against exact raw bytes."""
    if not isinstance(raw_body, bytes) or not isinstance(signature_header, str):
        return False
    if not isinstance(secret, str) or not secret.startswith("whsec_") or len(secret) < 24:
        return False
    if not isinstance(tolerance_seconds, int) or tolerance_seconds < 0:
        return False
    timestamp: int | None = None
    signatures: list[str] = []
    for part in signature_header.split(","):
        key, separator, value = part.strip().partition("=")
        if not separator:
            continue
        if key == "t":
            if timestamp is not None or not value.isdigit():
                return False
            timestamp = int(value)
        elif key == "v1" and re.fullmatch(r"[0-9a-fA-F]{64}", value):
            signatures.append(value.lower())
    if timestamp is None or not signatures:
        return False
    current_time = int(datetime.now(timezone.utc).timestamp()) if now is None else now
    if abs(current_time - timestamp) > tolerance_seconds:
        return False
    signed_payload = str(timestamp).encode("ascii") + b"." + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, supplied) for supplied in signatures)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _identifier(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, Mapping):
        return _identifier(value.get("id"))
    return None


def _minor_to_major(amount: Any, currency: Any) -> Decimal | None:
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        return None
    code = str(currency or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", code):
        return None
    # UGX and ISK retain two-decimal backward compatibility for charge amounts.
    divisor = Decimal("1") if code in ZERO_DECIMAL_CURRENCIES else Decimal("100")
    return (Decimal(amount) / divisor).quantize(Decimal("0.000001"))


def _click_reference(*metadata_sources: Any) -> str | None:
    for source in metadata_sources:
        metadata = _mapping(source)
        for key in ("omni_click_id", "affiliate_click_id", "click_id", "subid"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _original_payment_intent(*metadata_sources: Any) -> str | None:
    for source in metadata_sources:
        value = _mapping(source).get("omni_original_payment_intent_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _invoice_payment_reference(invoice: Mapping[str, Any]) -> tuple[str | None, int | None, str]:
    """Read legacy Invoice.payment_intent or current Invoice.payments collection."""
    legacy_id = _identifier(invoice.get("payment_intent"))
    if legacy_id:
        amount = invoice.get("amount_paid")
        return legacy_id, amount if isinstance(amount, int) and not isinstance(amount, bool) else None, ""
    records = _mapping(invoice.get("payments")).get("data")
    if not isinstance(records, list):
        return None, None, "invoice_payment_reference_not_in_snapshot"
    paid: list[tuple[str, int]] = []
    for record in records:
        item = _mapping(record)
        if item.get("status") != "paid":
            continue
        payment = _mapping(item.get("payment"))
        if payment.get("type") != "payment_intent":
            continue
        payment_id = _identifier(payment.get("payment_intent"))
        amount = item.get("amount_paid")
        if payment_id and isinstance(amount, int) and not isinstance(amount, bool) and amount > 0:
            paid.append((payment_id, amount))
    if len(paid) == 1:
        return paid[0][0], paid[0][1], ""
    if len(paid) > 1:
        return None, None, "multiple_invoice_payments_require_reconciliation"
    return None, None, "invoice_payment_intent_not_found"


def normalize_stripe_webhook_event(
    envelope: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    """Return a normalized merchant event or a safe ignore/manual-review reason.

    Sale/renewal event_id is the Stripe PaymentIntent ID, enabling charge.refunded to
    resolve the original receipt. Stripe envelope event IDs are preserved separately.
    """
    event = _mapping(envelope)
    stripe_event_id = event.get("id")
    event_type = event.get("type")
    obj = _mapping(_mapping(event.get("data")).get("object"))
    if not isinstance(stripe_event_id, str) or not stripe_event_id.strip():
        return None, "invalid_stripe_event_id"
    if not isinstance(event_type, str):
        return None, "invalid_stripe_event_type"
    occurred_at = None
    created = event.get("created")
    if isinstance(created, int) and not isinstance(created, bool) and created > 0:
        try:
            occurred_at = datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None, "invalid_stripe_event_timestamp"
    common = {"source_provider_event_id": stripe_event_id.strip(), "occurred_at": occurred_at}

    if event_type == "payment_intent.succeeded":
        if obj.get("status") != "succeeded":
            return None, "payment_intent_not_succeeded"
        if _identifier(obj.get("invoice")):
            return None, "subscription_payment_intent_handled_by_invoice_paid"
        transaction_id = _identifier(obj.get("id"))
        revenue = _minor_to_major(obj.get("amount_received"), obj.get("currency"))
        click_id = _click_reference(obj.get("metadata"))
        if not transaction_id or revenue is None or revenue <= 0:
            return None, "payment_intent_missing_transaction_amount_or_id"
        if not click_id:
            return None, "missing_affiliate_click_reference"
        return {
            **common, "event_id": transaction_id, "event_type": "sale",
            "click_id": click_id, "revenue": format(revenue, "f"),
            "currency": str(obj.get("currency")).upper(),
        }, ""

    if event_type == "invoice.paid":
        if obj.get("paid") is not True and obj.get("status") != "paid":
            return None, "invoice_not_paid"
        amount_off_stripe = obj.get("amount_paid_off_stripe")
        if obj.get("paid_out_of_band") is True or (
            isinstance(amount_off_stripe, int) and not isinstance(amount_off_stripe, bool) and amount_off_stripe > 0
        ):
            return None, "out_of_band_invoice_requires_manual_reconciliation"
        billing_reason = obj.get("billing_reason")
        if billing_reason not in {"subscription_create", "subscription_cycle"}:
            return None, "unsupported_invoice_billing_reason"
        payment_id, payment_amount, payment_reason = _invoice_payment_reference(obj)
        if not payment_id or payment_amount is None:
            return None, payment_reason or "invoice_payment_intent_not_found"
        revenue = _minor_to_major(payment_amount, obj.get("currency"))
        parent_subscription = _mapping(_mapping(obj.get("parent")).get("subscription_details"))
        legacy_subscription = _mapping(obj.get("subscription_details"))
        click_id = _click_reference(
            obj.get("metadata"), legacy_subscription.get("metadata"), parent_subscription.get("metadata"),
        )
        original_pi = _original_payment_intent(
            obj.get("metadata"), legacy_subscription.get("metadata"), parent_subscription.get("metadata"),
        )
        if revenue is None or revenue <= 0:
            return None, "invoice_missing_payment_amount"
        if billing_reason == "subscription_create":
            if not click_id:
                return None, "missing_affiliate_click_reference"
            return {
                **common, "event_id": payment_id, "event_type": "sale",
                "click_id": click_id, "revenue": format(revenue, "f"),
                "currency": str(obj.get("currency")).upper(),
            }, ""
        if not click_id and not original_pi:
            return None, "missing_subscription_attribution_reference"
        normalized = {
            **common, "event_id": payment_id, "event_type": "subscription_renewal",
            "revenue": format(revenue, "f"), "currency": str(obj.get("currency")).upper(),
        }
        if click_id:
            normalized["click_id"] = click_id
        if original_pi:
            normalized["original_event_id"] = original_pi
        return normalized, ""

    if event_type == "charge.refunded":
        original_amount, refunded_amount = obj.get("amount"), obj.get("amount_refunded")
        if (isinstance(original_amount, bool) or not isinstance(original_amount, int)
                or isinstance(refunded_amount, bool) or not isinstance(refunded_amount, int)
                or original_amount <= 0 or refunded_amount < 0):
            return None, "refund_amount_missing"
        if refunded_amount != original_amount:
            return None, "partial_refund_requires_reconciliation"
        payment_intent_id = _identifier(obj.get("payment_intent"))
        currency = str(obj.get("currency") or "").strip().upper()
        if not payment_intent_id or not re.fullmatch(r"[A-Z]{3}", currency):
            return None, "refund_missing_original_payment_reference"
        return {
            **common, "event_id": stripe_event_id.strip(), "event_type": "refund",
            "original_event_id": payment_intent_id, "currency": currency,
        }, ""

    if event_type == "charge.dispute.created":
        return None, "chargeback_requires_manual_reconciliation"
    return None, "unsupported_stripe_event_type"
