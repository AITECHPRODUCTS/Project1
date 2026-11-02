from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Any


TERM_FIELDS = (
    "terms_version",
    "commission_type",
    "commission_value",
    "commission_currency",
    "cookie_days",
    "attribution_window_days",
    "allowed_regions",
    "restricted_traffic_sources",
)


def normalize_term_values(values: dict[str, Any]) -> dict[str, Any]:
    """Return stable, JSON-safe term values; unknown values stay None."""
    try:
        amount = Decimal(str(values["commission_value"])).quantize(Decimal("0.0001"))
    except (KeyError, InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("commission_value must be a finite decimal amount") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("commission_value must be a positive finite decimal amount")

    normalized: dict[str, Any] = {
        "terms_version": str(values.get("terms_version") or "").strip(),
        "commission_type": str(values.get("commission_type") or "").strip().lower(),
        "commission_value": format(amount, "f"),
        "commission_currency": str(values.get("commission_currency") or "").strip().upper(),
        "cookie_days": values.get("cookie_days"),
        "attribution_window_days": values.get("attribution_window_days"),
        "allowed_regions": sorted({
            str(value).strip().upper()
            for value in (values.get("allowed_regions") or [])
            if str(value).strip()
        }),
        "restricted_traffic_sources": sorted({
            str(value).strip().lower()
            for value in (values.get("restricted_traffic_sources") or [])
            if str(value).strip()
        }),
    }
    for field in ("cookie_days", "attribution_window_days"):
        value = normalized[field]
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise ValueError(field + " must be a non-negative integer or None")
    return normalized


def canonical_terms_hash(values: dict[str, Any]) -> str:
    normalized = normalize_term_values(values)
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compare_offer_terms(
    previous: dict[str, Any],
    current: dict[str, Any],
    *,
    has_previous_snapshot: bool,
) -> dict[str, Any]:
    """Compare source-evidenced term inputs without claiming that the source was verified."""
    before = normalize_term_values(previous)
    after = normalize_term_values(current)
    changes = [
        {"field": field, "previous": before[field], "current": after[field]}
        for field in TERM_FIELDS
        if before[field] != after[field]
    ]
    changed_fields = [item["field"] for item in changes]
    if changes:
        status = "changes_detected"
    elif has_previous_snapshot:
        status = "unchanged"
    else:
        status = "baseline_recorded"
    encoded = json.dumps(after, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return {
        "current_terms": after,
        "terms_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "change_status": status,
        "changed_fields": changed_fields,
        "changes": changes,
        "requires_revalidation": bool(changes),
    }
