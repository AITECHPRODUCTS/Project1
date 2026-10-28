from __future__ import annotations

import math
from numbers import Integral
from typing import Any


def _non_negative_count(name: str, value: int | None) -> int | None:
    """Reject malformed measurement counts instead of silently rewriting source data."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be a non-negative integer")
    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return normalized


def _non_negative_finite_number(name: str, value: float | None) -> float | None:
    """Convert numeric measurements only when finite and non-negative."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite non-negative number")
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite non-negative number") from exc
    if not math.isfinite(normalized) or normalized < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return normalized


def compute_offer_metrics(
    offer: dict[str, Any],
    *,
    clicks: int | None = None,
    conversions: int | None = None,
    total_revenue: float | None = None,
    gravity_weight: float = 1.0,
) -> dict[str, Any]:
    """Calculate evidence-dependent metrics without fabricating missing or invalid measurements.

    Missing observations remain None. Invalid supplied counts/revenue are rejected rather
    than truncated or clamped, and non-finite provider gravity values are treated as unknown.
    """
    if isinstance(gravity_weight, bool):
        raise ValueError("gravity_weight must be a finite number from 0 to 10")
    try:
        weight = float(gravity_weight)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("gravity_weight must be a finite number from 0 to 10") from exc
    if not math.isfinite(weight) or not 0 <= weight <= 10:
        raise ValueError("gravity_weight must be a finite number from 0 to 10")

    normalized_clicks = _non_negative_count("clicks", clicks)
    normalized_conversions = _non_negative_count("conversions", conversions)
    revenue = _non_negative_finite_number("total_revenue", total_revenue)

    if (
        normalized_clicks is not None
        and normalized_conversions is not None
        and normalized_conversions > normalized_clicks
    ):
        raise ValueError("conversions cannot exceed clicks")

    epc = (
        revenue / normalized_clicks
        if revenue is not None and normalized_clicks not in (None, 0)
        else (0.0 if revenue == 0 and normalized_clicks not in (None, 0) else None)
    )
    conversion_rate = (
        normalized_conversions / normalized_clicks
        if normalized_conversions is not None and normalized_clicks not in (None, 0)
        else (
            0.0
            if normalized_conversions == 0 and normalized_clicks not in (None, 0)
            else None
        )
    )

    gravity: float | None = None
    raw_gravity = offer.get("gravity_score")
    if raw_gravity is not None and not isinstance(raw_gravity, bool):
        try:
            candidate = float(raw_gravity)
        except (TypeError, ValueError, OverflowError):
            candidate = None
        if candidate is not None and math.isfinite(candidate) and candidate >= 0:
            gravity = candidate

    normalized_gravity = gravity * weight if gravity is not None else None
    if normalized_gravity is not None and not math.isfinite(normalized_gravity):
        normalized_gravity = None

    reward_type = str(offer.get("reward_type") or "").lower()
    return {
        "gravity_score": gravity,
        "normalized_gravity": normalized_gravity,
        "epc": round(epc, 6) if epc is not None else None,
        "conversion_rate": round(conversion_rate, 6) if conversion_rate is not None else None,
        "recurring_commission": (
            "recurr" in reward_type or offer.get("recurring_commission") is True
        ),
        "recurring_commission_value": (
            offer.get("reward_value") if "recurr" in reward_type else None
        ),
        "measurement_basis": {
            "clicks": normalized_clicks,
            "conversions": normalized_conversions,
            "total_revenue": revenue,
            "gravity_weight": weight,
        },
    }
