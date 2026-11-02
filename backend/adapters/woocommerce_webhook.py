"""Native WooCommerce webhook verification and order normalization (inbound only)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


def verify_woocommerce_webhook_signature(raw_body: bytes, supplied_signature: str, secret: str) -> bool:
    """Verify WooCommerce Base64 HMAC-SHA256 over the exact raw request body."""
    if not isinstance(raw_body, bytes) or not isinstance(supplied_signature, str):
        return False
    if not isinstance(secret, str) or len(secret) < 32:
        return False
    candidate = supplied_signature.strip()
    if not candidate or len(candidate) > 128:
        return False
    expected = base64.b64encode(
        hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    ).decode("ascii")
    return hmac.compare_digest(expected, candidate)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _order_id(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value) if value > 0 else None
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,17}", value.strip()):
        return value.strip()
    return None


def _decimal_amount(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None
    return amount if amount.is_finite() else None


def _meta_value(meta_data: Any, keys: tuple[str, ...]) -> str | None:
    wanted = set(keys)
    if isinstance(meta_data, Mapping):
        for key in keys:
            value = meta_data.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).strip():
                return str(value).strip()
    elif isinstance(meta_data, list):
        for item in meta_data:
            row = _mapping(item)
            value = row.get("value")
            if row.get("key") in wanted and isinstance(value, (str, int)) and not isinstance(value, bool):
                normalized = str(value).strip()
                if normalized:
                    return normalized
    return None


def _paid_at(order: Mapping[str, Any]) -> datetime | None:
    """Use WooCommerce's GMT paid timestamp, or an explicitly offset local timestamp."""
    for key in ("date_paid_gmt", "date_paid"):
        raw = order.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        value = raw.strip()
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            if key != "date_paid_gmt":
                continue
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def normalize_woocommerce_webhook_event(
    order: Mapping[str, Any], topic: str, delivery_id: str,
) -> tuple[dict[str, Any] | None, str]:
    """Normalize paid WooCommerce orders; quarantine ambiguous attribution/refund states.

    Conversion identity is stable per order ID. Subscription renewals must set
    order-level omni_original_order_id metadata. Full refunds are automatic only if
    status=refunded and all refund records sum exactly to the original order total.
    """
    if not isinstance(order, Mapping):
        return None, "invalid_order_payload"
    topic = str(topic or "").strip().lower()
    if topic not in {"order.created", "order.updated"}:
        return None, "unsupported_woocommerce_topic"
    delivery_id = str(delivery_id or "").strip()
    if not delivery_id or len(delivery_id) > 200 or any(ord(ch) < 33 for ch in delivery_id):
        return None, "missing_or_invalid_delivery_id"
    order_id = _order_id(order.get("id"))
    if not order_id:
        return None, "invalid_woocommerce_order_id"
    stable_event_id = f"wc-order-{order_id}"
    status = str(order.get("status") or "").strip().lower()
    currency = str(order.get("currency") or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        return None, "invalid_woocommerce_currency"
    total = _decimal_amount(order.get("total"))
    if total is None or total < 0:
        return None, "invalid_woocommerce_order_total"

    refunds = order.get("refunds")
    has_refunds = isinstance(refunds, list) and bool(refunds)
    if has_refunds or status == "refunded":
        if not isinstance(refunds, list) or not refunds:
            return None, "refund_details_missing"
        refund_total = Decimal("0")
        for refund in refunds:
            refund_row = _mapping(refund)
            if not _order_id(refund_row.get("id")):
                return None, "refund_details_invalid"
            amount = _decimal_amount(refund_row.get("total"))
            if amount is None:
                return None, "refund_details_invalid"
            refund_total += abs(amount)
        if refund_total <= 0:
            return None, "refund_details_invalid"
        if refund_total < total:
            return None, "partial_refund_requires_reconciliation"
        if refund_total != total or status != "refunded":
            return None, "refund_total_inconsistent_requires_reconciliation"
        return {
            "event_id": f"{stable_event_id}-full-refund",
            "event_type": "refund",
            "original_event_id": stable_event_id,
            "revenue": "0",
            "currency": currency,
            "source_provider_event_id": delivery_id,
            "occurred_at": None,
        }, ""

    if status not in {"processing", "completed"}:
        return None, "woocommerce_order_not_paid"
    if total <= 0:
        return None, "paid_order_zero_total_requires_review"

    click_id = _meta_value(order.get("meta_data"), (
        "omni_click_id", "affiliate_click_id", "click_id", "subid",
    ))
    original_raw = _meta_value(order.get("meta_data"), ("omni_original_order_id",))
    original_order_id = _order_id(original_raw) if original_raw else None
    if original_order_id == order_id:
        return None, "invalid_original_subscription_order"
    if not click_id and not original_order_id:
        return None, "missing_affiliate_click_reference"
    paid_at = _paid_at(order)
    if paid_at is None:
        return None, "paid_order_missing_utc_payment_time"

    result = {
        "event_id": stable_event_id,
        "event_type": "subscription_renewal" if original_order_id else "sale",
        "revenue": format(total, "f"),
        "currency": currency,
        "source_provider_event_id": delivery_id,
        "occurred_at": paid_at.isoformat(),
    }
    if click_id:
        result["click_id"] = click_id
    if original_order_id:
        result["original_event_id"] = f"wc-order-{original_order_id}"
    return result, ""
