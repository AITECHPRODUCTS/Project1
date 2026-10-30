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



def _creative_fatigue(rows: list[AdPerformanceObservation]) -> dict[str, Any]:
    """Detect a recent CTR drop from verified daily observations; never auto-pause."""
    if not rows:
        return {"status": "not_assessable_no_data", "review_recommended": False}
    verified_rows = [row for row in rows if row.evidence_status == "provider_verified"]
    if len(verified_rows) != len(rows):
        return {
            "status": "blocked_unverified_or_mixed_evidence",
            "review_recommended": False,
            "note": "Every observation in the time series must be provider-verified.",
        }
    daily: dict[Any, dict[str, int]] = {}
    for row in verified_rows:
        observed = row.observed_at
        day = observed.date() if hasattr(observed, "date") else observed
        bucket = daily.setdefault(day, {"impressions": 0, "clicks": 0})
        bucket["impressions"] += int(row.impressions or 0)
        bucket["clicks"] += int(row.clicks or 0)
    dates = sorted(daily)
    if len(dates) < 4:
        return {
            "status": "insufficient_history",
            "review_recommended": False,
            "verified_days": len(dates),
            "minimum_days": 4,
        }
    baseline_dates, recent_dates = dates[-4:-2], dates[-2:]
    def aggregate(selected: list[Any]) -> dict[str, Any]:
        impressions = sum(daily[day]["impressions"] for day in selected)
        clicks = sum(daily[day]["clicks"] for day in selected)
        return {"impressions": impressions, "clicks": clicks, "ctr": clicks / impressions if impressions else None}
    baseline, recent = aggregate(baseline_dates), aggregate(recent_dates)
    if any(int(period["impressions"]) < 1000 or int(period["clicks"]) < 30 for period in (baseline, recent)):
        return {
            "status": "insufficient_sample",
            "review_recommended": False,
            "baseline": baseline,
            "recent": recent,
            "minimum_impressions_per_period": 1000,
            "minimum_clicks_per_period": 30,
        }
    baseline_ctr, recent_ctr = float(baseline["ctr"] or 0), float(recent["ctr"] or 0)
    if baseline_ctr <= 0:
        return {"status": "not_assessable_zero_baseline_ctr", "review_recommended": False, "baseline": baseline, "recent": recent}
    decline_pct = (baseline_ctr - recent_ctr) / baseline_ctr * 100
    threshold_pct = 30.0
    flagged = decline_pct >= threshold_pct
    return {
        "status": "review_signal_detected" if flagged else "no_material_decline_detected",
        "review_recommended": flagged,
        "baseline_dates": [day.isoformat() for day in baseline_dates],
        "recent_dates": [day.isoformat() for day in recent_dates],
        "baseline_ctr": round(baseline_ctr, 6),
        "recent_ctr": round(recent_ctr, 6),
        "decline_percentage": round(decline_pct, 1),
        "threshold_percentage": threshold_pct,
        "baseline": baseline,
        "recent": recent,
        "automatic_action_executed": False,
        "note": "CTR decline is a heuristic review signal, not proof of fatigue; inspect creative, placement and measurement changes.",
    }


def _optimization_recommendation(
    *,
    plan_id: str | None,
    platform: str,
    creative_id: str,
    verified_metrics: dict[str, Any] | None,
    verified_rows: list[AdPerformanceObservation],
    total_row_count: int,
) -> dict[str, Any]:
    if not verified_rows or verified_metrics is None:
        return {
            "eligible": False,
            "status": "blocked_pending_provider_verification",
            "pause_recommended": False,
            "scale_review_recommended": False,
            "automatic_action_executed": False,
            "requires_human_approval": True,
            "reason": "Reported inputs are unverified. Validate source evidence before stop-loss or scale review.",
        }
    metrics = verified_metrics
    sample_gate = {
        "minimum_verified_impressions": 1000,
        "minimum_verified_clicks": 30,
        "actual_verified_impressions": int(metrics["impressions"]),
        "actual_verified_clicks": int(metrics["clicks"]),
        "actual_verified_conversions": int(metrics["conversions"]),
        "attribution_window_maturity": "not_supplied",
        "passed": int(metrics["impressions"]) >= 1000 and int(metrics["clicks"]) >= 30,
    }
    if not sample_gate["passed"]:
        return {
            "eligible": False,
            "status": "blocked_insufficient_verified_sample",
            "sample_gate": sample_gate,
            "pause_recommended": False,
            "scale_review_recommended": False,
            "automatic_action_executed": False,
            "requires_human_approval": True,
            "reason": "Verified impression and click minimums have not been met.",
        }
    decision = evaluate_roas(
        campaign_id=plan_id or f"{platform}:{creative_id}",
        spend=float(metrics["spend_usd"]),
        commission=float(metrics["commission_usd"]),
    )
    scale_review = (
        decision.roas is not None
        and decision.roas >= decision.threshold * 1.25
        and int(metrics["conversions"]) >= 10
    )
    if decision.pause_recommended:
        status = "stop_loss_review_recommended"
        reason = "Verified ROAS is below the review threshold. Confirm attribution-window maturity before any pause."
    elif scale_review:
        status = "scale_review_recommended"
        reason = "Verified ROAS and conversion-count gates support a human scale review, not spend authorization."
    else:
        status = "monitor_verified_performance"
        reason = "No stop-loss or scale-review trigger was met."
    return {
        "eligible": True,
        "status": status,
        "roas": decision.roas,
        "threshold": decision.threshold,
        "pause_recommended": decision.pause_recommended,
        "scale_review_recommended": scale_review,
        "sample_gate": sample_gate,
        "automatic_action_executed": False,
        "requires_human_approval": True,
        "verified_observation_count": len(verified_rows),
        "total_observation_count": total_row_count,
        "reason": reason,
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

        optimization = _optimization_recommendation(
            plan_id=plan_id,
            platform=platform,
            creative_id=creative_id,
            verified_metrics=verified_metrics,
            verified_rows=verified_rows,
            total_row_count=len(group),
        )
        creative_fatigue = _creative_fatigue(group)

        summaries.append({
            "campaign_plan_id": plan_id,
            "platform": platform,
            "creative_id": creative_id,
            "observation_count": len(group),
            "evidence_status": evidence_status,
            "reported_metrics_unverified": _metrics(group),
            "verified_metrics": verified_metrics,
            "optimization": optimization,
            "creative_fatigue": creative_fatigue,
        })
    return summaries
