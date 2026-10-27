from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _number(value: Any) -> Decimal:
    return Decimal(str(value if value is not None else "0"))


def _daily_snapshots(rows: Iterable[Any]) -> list[Any]:
    """Keep the latest provider observation per creative/platform/UTC day."""
    latest: dict[tuple[str, str, date], Any] = {}
    for row in rows:
        observed_at = _as_utc(row.observed_at)
        key = (str(row.platform), str(row.creative_id), observed_at.date())
        previous = latest.get(key)
        if previous is None or _as_utc(previous.observed_at) <= observed_at:
            latest[key] = row
    return list(latest.values())


def evaluate_ad_budget_guardrail(
    *,
    policy: Any,
    observations: Iterable[Any],
    now: datetime,
    plan_daily_budget_usd: Decimal | str | int | None = None,
) -> dict[str, Any]:
    """Evaluate caps from provider-verified evidence only; never invokes ad providers."""
    all_rows = list(observations)
    verified_rows = [row for row in all_rows if getattr(row, "evidence_status", None) == "provider_verified"]
    snapshots = _daily_snapshots(verified_rows)
    now_utc = _as_utc(now)
    daily_rows = [row for row in snapshots if _as_utc(row.observed_at).date() == now_utc.date()]
    daily_spend = sum((_number(row.spend_usd) for row in daily_rows), Decimal("0.00"))
    campaign_spend = sum((_number(row.spend_usd) for row in snapshots), Decimal("0.00"))
    impressions = sum(int(row.impressions or 0) for row in snapshots)
    clicks = sum(int(row.clicks or 0) for row in snapshots)
    conversions = sum(int(row.conversions or 0) for row in snapshots)
    commission = sum((_number(row.commission_usd) for row in snapshots), Decimal("0.00"))
    configured_daily = _number(policy.daily_spend_cap_usd)
    plan_daily = _number(plan_daily_budget_usd)
    effective_daily = min(configured_daily, plan_daily) if plan_daily > 0 else configured_daily
    campaign_cap = _number(policy.campaign_spend_cap_usd)
    roas_floor = _number(policy.minimum_roas)
    max_cpa = _number(policy.maximum_cpa_usd) if policy.maximum_cpa_usd is not None else None
    roas = commission / campaign_spend if campaign_spend > 0 else None
    cpa = campaign_spend / Decimal(conversions) if conversions > 0 else None
    sample_passed = (
        impressions >= int(policy.minimum_verified_impressions)
        and clicks >= int(policy.minimum_verified_clicks)
        and conversions >= int(policy.minimum_verified_conversions)
    )
    complete = bool(all_rows) and len(verified_rows) == len(all_rows)
    result: dict[str, Any] = {
        "policy_id": str(policy.id),
        "campaign_plan_id": str(policy.campaign_plan_id),
        "evaluated_at": now_utc.isoformat(),
        "timezone": "UTC",
        "status": "blocked_pending_provider_verification",
        "reported_observation_count": len(all_rows),
        "verified_observation_count": len(verified_rows),
        "snapshot_observation_count": len(snapshots),
        "unverified_observation_count": len(all_rows) - len(verified_rows),
        "configured_daily_spend_cap_usd": format(configured_daily, ".2f"),
        "plan_daily_budget_usd": format(plan_daily, ".2f"),
        "effective_daily_spend_cap_usd": format(effective_daily, ".2f"),
        "campaign_spend_cap_usd": format(campaign_cap, ".2f"),
        "verified_spend_today_usd": format(daily_spend, ".2f"),
        "verified_campaign_spend_usd": format(campaign_spend, ".2f"),
        "minimum_roas": format(roas_floor, ".4f"),
        "verified_roas": round(float(roas), 6) if roas is not None else None,
        "maximum_cpa_usd": format(max_cpa, ".2f") if max_cpa is not None else None,
        "verified_cpa_usd": round(float(cpa), 4) if cpa is not None else None,
        "sample_gate": {
            "minimum_verified_impressions": int(policy.minimum_verified_impressions),
            "minimum_verified_clicks": int(policy.minimum_verified_clicks),
            "minimum_verified_conversions": int(policy.minimum_verified_conversions),
            "actual_verified_impressions": impressions,
            "actual_verified_clicks": clicks,
            "actual_verified_conversions": conversions,
            "passed": sample_passed,
        },
        "breaches": [],
        "stop_recommended": False,
        "kill_switch_should_engage": False,
        "live_spend_authorized": False,
        "provider_action_executed": False,
        "note": "This is a review signal, not a provider pause. Provider exports must be normalized to daily creative snapshots before spend reconciliation.",
    }
    if not all_rows or not verified_rows:
        result["status"] = "blocked_pending_provider_verification"
        result["note"] = "No complete provider-verified observation set is available. The system fails closed and does not infer spend or profitability."
        return result
    if not complete:
        result["status"] = "blocked_mixed_evidence"
        result["note"] = "At least one linked observation is not provider-verified. Evaluation is blocked rather than mixing reported and verified totals."
        return result

    breaches: list[dict[str, str]] = []
    if daily_spend >= effective_daily:
        breaches.append({"code": "daily_spend_cap_reached", "observed_usd": format(daily_spend, ".2f"), "limit_usd": format(effective_daily, ".2f")})
    if campaign_spend >= campaign_cap:
        breaches.append({"code": "campaign_spend_cap_reached", "observed_usd": format(campaign_spend, ".2f"), "limit_usd": format(campaign_cap, ".2f")})
    if sample_passed:
        if roas is not None and roas < roas_floor:
            breaches.append({"code": "minimum_roas_breach", "observed": format(roas, ".6f"), "limit": format(roas_floor, ".4f")})
        if max_cpa is not None and cpa is not None and cpa > max_cpa:
            breaches.append({"code": "maximum_cpa_breach", "observed_usd": format(cpa, ".4f"), "limit_usd": format(max_cpa, ".2f")})
    result["breaches"] = breaches
    result["stop_recommended"] = bool(breaches)
    result["kill_switch_should_engage"] = bool(breaches)
    result["status"] = "triggered_stop" if breaches else "monitoring"
    return result
