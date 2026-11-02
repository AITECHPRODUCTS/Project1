from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any

_REWARD_QUALITY = {"cps_recurring": 5, "cps_lifetime": 5, "cps_one_time": 3, "cpl": 2, "cpc": 1, "other": 2}
_ACTION_ORDER = {"double_down": 0, "optimize": 1, "maintain": 2, "phase_out": 3}
_ACTION_SKILL = {"double_down": "content-angle-ranker", "optimize": "seo-audit", "maintain": "content-decay-detector", "phase_out": "traffic-analyzer"}


def _r(value: float | int | None) -> float | None:
    return round(float(value), 2) if value is not None else None


def _action(p: dict[str, Any], epc: float | None, med_epc: float | None, med_clicks: float | None, med_revenue: float | None, measured_count: int) -> tuple[str, str]:
    status, revenue, clicks = p["status"], p["monthly_revenue"], p["monthly_clicks"]
    if status == "paused":
        return "optimize", "Paused program: verify official terms, pause reason, tracking and payout status before considering reactivation."
    if status in {"new", "considering"} and (revenue is None or clicks is None or clicks < 20):
        return "optimize", "New or considering program lacks mature performance evidence; verify terms and run a bounded test before allocating substantial effort."
    if epc is None:
        if revenue is not None and revenue > 0:
            return "maintain", "Revenue is reported but a comparable positive click count is missing; verify attribution before drawing efficiency conclusions."
        return "optimize", "Collect comparable clicks, approved conversions and payout evidence; do not classify missing data as zero performance."
    if measured_count == 1 and epc > 0:
        return "double_down", "Only program with measurable EPC in this supplied set; test a small controlled expansion rather than assuming future growth."
    if med_epc is not None and epc >= max(0.01, med_epc * 1.2) and (clicks or 0) >= 10:
        return "double_down", "Reported EPC is materially above the portfolio median; test more relevant content/traffic in stages and confirm conversions and payouts."
    if med_epc is not None and med_epc > 0 and epc < med_epc * 0.5 and (clicks or 0) >= 20 and revenue is not None and (med_revenue is None or revenue <= med_revenue):
        return "phase_out", "Reported EPC is below half the portfolio median with at least 20 clicks. Treat as a phase-out candidate only after validating attribution, terms and payouts."
    if med_epc is not None and med_epc > 0 and epc < med_epc and clicks is not None and med_clicks is not None and clicks >= med_clicks:
        return "optimize", "Click volume is meaningful but EPC trails the portfolio median; inspect intent match, CTAs, landing-page fit and tracking."
    return "maintain", "No strong comparative signal supports a major change; refresh content and measure the next comparable period."


def _split_hours(total: float, names: list[str]) -> list[tuple[str, float]]:
    if total <= 0:
        return []
    unique = list(dict.fromkeys(names or ["Portfolio research"]))
    each = round(total / len(unique), 2)
    output: list[tuple[str, float]] = []
    used = 0.0
    for i, name in enumerate(unique):
        hours = round(total - used, 2) if i == len(unique) - 1 else each
        output.append((name, hours))
        used = round(used + hours, 2)
    return output


def manage_program_portfolio(*, programs: list[dict[str, Any]], goal: str = "maximize_revenue", budget_hours: float = 10) -> dict[str, Any]:
    """Create a review-only affiliate portfolio scorecard from operator-supplied metrics."""
    if not 1 <= len(programs) <= 30:
        raise ValueError("Supply between one and thirty affiliate programs")
    if goal not in {"maximize_revenue", "diversify", "reduce_risk", "find_gaps"}:
        raise ValueError("Portfolio goal is not supported")
    if not 0 < float(budget_hours) <= 80:
        raise ValueError("Weekly time budget must be greater than 0 and at most 80 hours")

    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in programs:
        name = " ".join(str(raw.get("name") or "").split())
        if len(name) < 2 or name.casefold() in seen:
            raise ValueError("Program names must be non-empty and unique")
        seen.add(name.casefold())
        revenue, clicks = raw.get("monthly_revenue"), raw.get("monthly_clicks")
        if revenue is not None and (isinstance(revenue, bool) or not isinstance(revenue, (int, float)) or revenue < 0):
            raise ValueError("Monthly revenue must be a non-negative number when supplied")
        if clicks is not None and (isinstance(clicks, bool) or not isinstance(clicks, int) or clicks < 0):
            raise ValueError("Monthly clicks must be a non-negative integer when supplied")
        reward_type = str(raw.get("reward_type") or "other")
        status = str(raw.get("status") or "active")
        if reward_type not in _REWARD_QUALITY or status not in {"active", "paused", "new", "considering"}:
            raise ValueError("Unknown commission type or program status")
        cleaned.append({
            "name": name, "affiliate_url": raw.get("affiliate_url"),
            "reward_type": reward_type, "reward_value": " ".join(str(raw.get("reward_value") or "").split()),
            "monthly_revenue": float(revenue) if revenue is not None else None, "monthly_clicks": clicks,
            "niche": " ".join(str(raw.get("niche") or "").split()), "status": status,
        })

    known_revenues = [p["monthly_revenue"] for p in cleaned if p["monthly_revenue"] is not None]
    total_revenue = sum(known_revenues)
    known_clicks = [p["monthly_clicks"] for p in cleaned if p["monthly_clicks"] is not None]
    total_clicks = sum(known_clicks) if known_clicks else None
    measured = [p for p in cleaned if p["monthly_revenue"] is not None and p["monthly_clicks"] is not None and p["monthly_clicks"] > 0]
    epcs = [p["monthly_revenue"] / p["monthly_clicks"] for p in measured]
    med_epc = median(epcs) if epcs else None
    active = [p for p in cleaned if p["status"] == "active"]
    active_clicks = [p["monthly_clicks"] for p in active if p["monthly_clicks"] is not None]
    active_revenue = [p["monthly_revenue"] for p in active if p["monthly_revenue"] is not None]
    med_clicks = float(median(active_clicks)) if active_clicks else None
    med_revenue = float(median(active_revenue)) if active_revenue else None

    by_niche: dict[str, float] = defaultdict(float)
    for p in cleaned:
        if p["niche"]:
            by_niche[p["niche"].casefold()] += p["monthly_revenue"] or 0.0
    ranked: list[dict[str, Any]] = []
    for p in cleaned:
        rev, clicks = p["monthly_revenue"], p["monthly_clicks"]
        epc = rev / clicks if rev is not None and clicks is not None and clicks > 0 else None
        share = rev / total_revenue * 100 if rev is not None and total_revenue > 0 else (0.0 if rev is not None and total_revenue == 0 else None)
        action, reason = _action(p, epc, med_epc, med_clicks, med_revenue, len(measured))
        relative = None
        if rev is not None or epc is not None:
            relative = round((min(100, max(0, share or 0)) * .55) + (min(100, epc / med_epc * 50) * .45 if epc is not None and med_epc and med_epc > 0 else 0), 1)
        ranked.append({
            "name": p["name"], "affiliate_url": p["affiliate_url"], "niche": p["niche"] or "unspecified",
            "reward_type": p["reward_type"], "reward_value": p["reward_value"], "status": p["status"],
            "monthly_revenue": _r(rev), "monthly_clicks": clicks, "epc": _r(epc), "revenue_share": _r(share),
            "commission_quality_score": _REWARD_QUALITY[p["reward_type"]], "relative_score": relative,
            "action": action, "reason": reason, "data_provenance": "operator_supplied_unverified",
        })
    shares = sorted([p["revenue_share"] for p in ranked if p["revenue_share"] is not None], reverse=True)
    if not known_revenues or total_revenue <= 0:
        concentration = "unknown"
    elif shares and shares[0] > 50:
        concentration = "high"
    elif sum(shares[:2]) > 80:
        concentration = "moderate"
    elif shares and shares[0] <= 30:
        concentration = "low"
    else:
        concentration = "moderate"
    niches = {p["niche"].casefold() for p in cleaned if p["niche"]}
    if not niches:
        diversification = "unknown"
    elif len(niches) == 1:
        diversification = "single_niche"
    elif total_revenue > 0 and max(by_niche.values(), default=0) / total_revenue > .75:
        diversification = "overlapping"
    else:
        diversification = "good"
    recurring_revenue = sum((p["monthly_revenue"] or 0.0) for p in cleaned if p["reward_type"] in {"cps_recurring", "cps_lifetime"} and p["monthly_revenue"] is not None)
    if not known_revenues or total_revenue <= 0:
        stability, recurring_share = "unknown", None
    else:
        recurring_share = recurring_revenue / total_revenue * 100
        stability = "stable" if recurring_share >= 60 else "moderate" if recurring_share >= 30 else "volatile"
    revenue_count = sum(p["monthly_revenue"] is not None for p in cleaned)
    click_count = sum(p["monthly_clicks"] is not None for p in cleaned)
    completeness = round(100 * (revenue_count + click_count) / (2 * len(cleaned)), 1)
    ranked.sort(key=lambda p: (_ACTION_ORDER[p["action"]], -(p["relative_score"] if p["relative_score"] is not None else -1), -(p["monthly_revenue"] if p["monthly_revenue"] is not None else -1), p["name"].casefold()))

    recommendations: list[dict[str, Any]] = []
    def add_rec(action: str, program: str, skill: str, task: str) -> None:
        recommendations.append({"action": action, "program": program, "skill": skill, "task": task, "priority": len(recommendations) + 1})
    for item in ranked[:10]:
        task = {
            "double_down": f"Test one high-intent content/distribution expansion for {item['name']}; recheck EPC, confirmed conversions and payout after a comparable period.",
            "maintain": f"Refresh the strongest existing asset for {item['name']} and verify current terms, attribution and payout status.",
            "optimize": f"Audit intent-to-click-to-conversion for {item['name']}; fill missing metric evidence before increasing effort.",
            "phase_out": f"Validate tracking, terms, refunds and payout evidence for {item['name']} before deciding whether to redirect effort.",
        }[item["action"]]
        add_rec(item["action"], item["name"], _ACTION_SKILL[item["action"]], task)
    if concentration == "high":
        add_rec("reduce_concentration", "Portfolio", "multi-program-manager", "Develop a second revenue line and test adjacent programs before reducing exposure to the current leader.")
    if diversification in {"single_niche", "overlapping", "unknown"} and goal in {"diversify", "reduce_risk", "find_gaps"}:
        add_rec("identify_niche_gaps", "Portfolio", "affiliate-program-search", "Research adjacent niches and compare official commission, compliance, product and payout evidence before applying.")
    if completeness < 80:
        add_rec("improve_measurement", "Portfolio", "performance-report", "Collect comparable clicks, approved conversions, reported revenue and payout confirmations for every active program.")
    if not recommendations:
        add_rec("maintain_review", "Portfolio", "performance-report", "Review comparable monthly results and verify terms before changing allocations.")

    best = next((p["name"] for p in ranked if p["status"] == "active"), ranked[0]["name"])
    budget = round(float(budget_hours), 2)
    pools = [
        ("scale", round(budget * .5, 2), [p["name"] for p in ranked if p["action"] == "double_down"] or [best], "Run an evidence-led scale test."),
        ("maintain", round(budget * .2, 2), [p["name"] for p in ranked if p["action"] == "maintain"] or [best], "Refresh useful content and verify affiliate terms."),
        ("optimize", round(budget * .2, 2), [p["name"] for p in ranked if p["action"] == "optimize"] or [best], "Review click quality, CTA, landing page and measurement."),
    ]
    used_hours = round(sum(pool[1] for pool in pools), 2)
    pools.append(("research", round(budget - used_hours, 2), ["Portfolio research"], "Find alternatives and verify official terms before applying."))
    plan: dict[str, dict[str, Any]] = {}
    for _, hours, names, task in pools:
        for name, share_hours in _split_hours(hours, names):
            if share_hours <= 0:
                continue
            row = plan.setdefault(name, {"program": name, "hours": 0.0, "tasks": []})
            row["hours"] = round(row["hours"] + share_hours, 2)
            if task not in row["tasks"]:
                row["tasks"].append(task)
    allocation = sorted(plan.values(), key=lambda p: (-p["hours"], p["program"]))
    allocated = round(sum(row["hours"] for row in allocation), 2)
    if allocation and allocated != budget:
        allocation[-1]["hours"] = round(allocation[-1]["hours"] + budget - allocated, 2)
    goal_note = {
        "maximize_revenue": "Prioritize controlled tests on active programs with comparatively strong supplied EPC.",
        "diversify": "Favor adjacent niches and distinct audiences while retaining evidence-backed core performers.",
        "reduce_risk": "Prioritize lower concentration, recurring revenue where reported, and clean attribution/payout evidence.",
        "find_gaps": "Investigate niche, measurement and program-coverage gaps before adding execution workload.",
    }[goal]
    return {
        "portfolio": {
            "total_programs": len(ranked), "active_programs": sum(p["status"] == "active" for p in ranked),
            "paused_programs": sum(p["status"] == "paused" for p in ranked),
            "total_monthly_revenue": _r(total_revenue) if known_revenues else None,
            "total_monthly_clicks": total_clicks,
            "revenue_share_complete": len(known_revenues) == len(ranked),
            "click_metrics_complete": len(known_clicks) == len(ranked),
            "data_completeness_pct": completeness,
            "top_program_revenue_share": _r(shares[0]) if shares else None,
            "top_two_program_revenue_share": _r(sum(shares[:2])) if shares else None,
            "recurring_revenue_share": _r(recurring_share), "concentration_risk": concentration,
            "niche_diversification": diversification, "revenue_stability": stability,
            "goal": goal, "goal_note": goal_note,
        },
        "programs": ranked, "recommendations": recommendations,
        "weekly_plan": {"total_hours": budget, "allocation": allocation, "category_targets": [
            {"category": "scale", "share_pct": 50}, {"category": "maintain", "share_pct": 20},
            {"category": "optimize", "share_pct": 20}, {"category": "program_research", "share_pct": 10},
        ]},
        "metrics_source": "operator_supplied_unverified", "provider_connected": False,
        "external_search_performed": False, "payouts_verified": False, "program_mutations_started": False,
        "requires_review": True,
        "chain_metadata": {"skill_slug": "multi-program-manager", "stage": "automation", "suggested_next": ["traffic-analyzer", "content-angle-ranker", "content-decay-detector", "affiliate-program-search"]},
        "note": "EPC and revenue-share metrics use operator-supplied inputs and do not prove tracked conversions or paid commissions. No live provider lookup, program changes, payout action or publishing occurred; verify official terms before acting.",
    }
