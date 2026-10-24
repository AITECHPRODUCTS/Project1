from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, Iterable

from backend.models import AdPerformanceObservation
from backend.services.ad_manager import evaluate_roas


def _metrics(rows: Iterable[AdPerformanceObservation]) -> dict[str, Any]:
    rows = list(rows)
    impressions = sum(int(row.impressions or 0) for row in rows)
    clicks = sum(int(row.clicks or 0) for row in rows)
    conversions = sum(int(row.conversions or 0) for row in rows)
    spend = sum((Decimal(row.spend_usd or 0) for row in rows), Decimal("0.00"))
    commission = sum((Decimal(row.commission_usd or 0) for row in rows), Decimal("0.00"))
    return {
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "spend_usd": f"{spend:.2f}",
        "commission_usd": f"{commission:.2f}",
        "ctr": round(clicks / impressions, 6) if impressions else None,
        "cpc_usd": round(float(spend / clicks), 4) if clicks else None,
        "conversion_rate": round(conversions / clicks, 6) if clicks else None,
        "cpa_usd": round(float(spend / conversions), 4) if conversions else None,
        "commission_to_spend_ratio": round(float(commission / spend), 4) if spend > 0 else None,
    }


def summarize_ad_performance(rows: Iterable[AdPerformanceObservation]) -> list[dict[str, Any]]:
    """Summarize reported metrics while keeping unverified records out of optimization."""
    grouped: dict[tuple[str | None, str, str], list[AdPerformanceObservation]] = defaultdict(list)
    for row in rows:
        grouped[(row.campaign_plan_id, row.platform, row.creative_id)].append(row)

    summaries: list[dict[str, Any]] = []
    for (plan_id, platform, creative_id), group in sorted(
        grouped.items(),
        key=lambda item: (item[0][0] or "", item[0][1], item[0][2]),
    ):
        verified_rows = [row for row in group if row.evidence_status == "provider_verified"]
        all_verified = len(verified_rows) == len(group)
        has_verified = bool(verified_rows)
        evidence_status = (
            "provider_verified" if all_verified
            else "mixed_verified_and_unverified" if has_verified
            else "operator_supplied_unverified"
        )
        verified_metrics = _metrics(verified_rows) if verified_rows else None

        if not verified_rows:
            optimization = {
                "eligible": False,
                "status": "blocked_pending_provider_verification",
                "pause_recommended": False,
                "automatic_action_executed": False,
                "reason": "Reported inputs are unverified. Validate source evidence before using them to pause or scale a campaign.",
            }
        else:
            metrics = verified_metrics or _metrics([])
            decision = evaluate_roas(
                campaign_id=plan_id or f"{platform}:{creative_id}",
                spend=float(metrics["spend_usd"]),
                commission=float(metrics["commission_usd"]),
            )
            optimization = {
                "eligible": True,
                "status": "verified_metrics_review_required",
                "roas": decision.roas,
                "threshold": decision.threshold,
                "pause_recommended": decision.pause_recommended,
                "automatic_action_executed": False,
                "reason": decision.reason,
            }

        summaries.append({
            "campaign_plan_id": plan_id,
            "platform": platform,
            "creative_id": creative_id,
            "observation_count": len(group),
            "evidence_status": evidence_status,
            "reported_metrics_unverified": _metrics(group),
            "verified_metrics": verified_metrics,
            "optimization": optimization,
        })
    return summaries
