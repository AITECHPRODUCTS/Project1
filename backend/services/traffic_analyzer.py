from __future__ import annotations

from typing import Any


_WEIGHTS = {"rank": 0.20, "volume": 0.25, "engagement": 0.25, "diversity": 0.15, "brand": 0.15}


def _rank_score(rank: int | None) -> float | None:
    if rank is None:
        return None
    if rank <= 10_000:
        return 100.0
    if rank <= 100_000:
        return 85.0
    if rank <= 1_000_000:
        return 65.0
    if rank <= 10_000_000:
        return 40.0
    return 20.0


def _volume_score(visits: int | None) -> float | None:
    if visits is None:
        return None
    if visits >= 1_000_000:
        return 100.0
    if visits >= 500_000:
        return 90.0
    if visits >= 100_000:
        return 75.0
    if visits >= 50_000:
        return 60.0
    if visits >= 10_000:
        return 40.0
    if visits > 0:
        return 20.0
    return 0.0


def _engagement_score(domain: dict[str, Any]) -> float | None:
    pieces: list[float] = []
    bounce = domain.get("bounce_rate")
    pages = domain.get("pages_per_visit")
    duration = domain.get("avg_duration_seconds")
    if bounce is not None:
        pieces.append(100.0 if bounce < 40 else 75.0 if bounce <= 60 else 50.0 if bounce <= 70 else 25.0)
    if pages is not None:
        pieces.append(100.0 if pages > 4 else 85.0 if pages > 3 else 65.0 if pages >= 2 else 35.0)
    if duration is not None:
        pieces.append(100.0 if duration > 180 else 65.0 if duration >= 60 else 40.0 if duration > 0 else 20.0)
    return round(sum(pieces) / len(pieces), 1) if pieces else None


def _source_diversity_score(sources: dict[str, Any]) -> float | None:
    names = ("direct", "search", "social", "referral", "paid")
    values = [sources.get(name) for name in names]
    if any(value is None for value in values):
        return None
    total = sum(float(value) for value in values)
    if total <= 0:
        return 0.0
    shares = [float(value) / total for value in values]
    diversity = 1.0 - sum(value * value for value in shares)
    return round(max(0.0, min(100.0, diversity / 0.8 * 100.0)), 1)


def _brand_score(direct: float | None) -> float | None:
    if direct is None:
        return None
    return round(min(100.0, max(0.0, direct / 40.0 * 100.0)), 1)


def _traffic_score(components: dict[str, float | None]) -> float | None:
    available = [(key, value) for key, value in components.items() if value is not None]
    if not available:
        return None
    total_weight = sum(_WEIGHTS[key] for key, _ in available)
    return round(sum(float(value) * _WEIGHTS[key] for key, value in available) / total_weight, 1)


def _verdict(score: float | None) -> str:
    if score is None:
        return "insufficient_data"
    if score >= 80:
        return "excellent"
    if score >= 60:
        return "good"
    if score >= 40:
        return "fair"
    if score >= 20:
        return "weak"
    return "red_flag"


def _format_visits(value: int | None) -> str | None:
    if value is None:
        return None
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 10_000:
        return f"{value / 1000:.0f}K"
    if value >= 1000:
        return f"{value / 1000:.1f}K"
    return str(value)


def _interpretation(domain: dict[str, Any], score: float | None, focus: str, missing_count: int) -> tuple[str, list[str]]:
    sources = domain.get("traffic_sources") or {}
    trend = domain.get("visits_trend") or "unknown"
    visits = domain.get("monthly_visits")
    bounce = domain.get("bounce_rate")
    direct = sources.get("direct")
    search = sources.get("search")
    risks: list[str] = []
    if trend == "declining":
        risks.append("operator_reported_traffic_decline")
    if bounce is not None and bounce > 70:
        risks.append("high_bounce_rate")
    if visits is not None and visits < 50_000:
        risks.append("reported_monthly_visits_below_50000")
    if search is not None and search < 10:
        risks.append("reported_search_share_below_10_percent")
    if direct is not None and direct < 10:
        risks.append("reported_direct_share_below_10_percent")
    if score is None:
        base = "There is not enough supplied traffic or engagement data to produce a defensible numeric score."
    else:
        base = f"Using only the supplied metrics, this domain scores {score}/100 ({_verdict(score).replace('_', ' ')})."
    if focus == "affiliate":
        context = "For affiliate promotion, use traffic as one screening signal; separately verify commission terms, product fit, conversion evidence, payout reliability and program legitimacy."
    elif focus == "competitor":
        known = [(name, sources.get(name)) for name in ("direct", "search", "social", "referral", "paid") if sources.get(name) is not None]
        strongest = max(known, key=lambda item: item[1])[0] if known else None
        context = f"The largest supplied traffic-source share is {strongest}; use it as a hypothesis for competitor research, not proof of channel performance." if strongest else "Traffic-source details were not supplied, so the competitor's strongest channel cannot be identified."
    else:
        context = "For advertiser evaluation, traffic and engagement are not proof of legal legitimacy, product quality, financial health or affiliate-program reliability."
    if trend == "declining":
        context += " The operator-reported trend is declining and should be checked against a reliable dated source."
    if missing_count:
        context += f" {missing_count} key metric groups remain incomplete."
    return f"{base} {context} Data is operator-supplied and unverified.", risks


def analyze_traffic_domains(
    *,
    domains: list[dict[str, Any]],
    focus: str = "affiliate",
    compare: bool | None = None,
) -> dict[str, Any]:
    """Score manually supplied domain metrics without implying a SimilarWeb or web-search integration."""
    if not 1 <= len(domains) <= 5:
        raise ValueError("Supply between one and five domains")
    if focus not in {"affiliate", "competitor", "advertiser"}:
        raise ValueError("Focus must be affiliate, competitor or advertiser")
    normalized_domains: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in domains:
        domain = " ".join(str(raw.get("domain") or "").strip().lower().split()).rstrip(".")
        if not domain or domain in seen:
            raise ValueError("Domain names must be non-empty and unique")
        seen.add(domain)
        visits = raw.get("monthly_visits")
        if visits is not None and (not isinstance(visits, int) or isinstance(visits, bool) or visits < 0):
            raise ValueError("Monthly visits must be a non-negative integer")
        sources = raw.get("traffic_sources") or {}
        if not isinstance(sources, dict):
            raise ValueError("Traffic source shares must be an object")
        normalized_domains.append({**raw, "domain": domain, "traffic_sources": sources})

    analyzed: list[dict[str, Any]] = []
    for domain in normalized_domains:
        source = domain.get("traffic_sources") or {}
        components = {
            "rank": _rank_score(domain.get("global_rank")),
            "volume": _volume_score(domain.get("monthly_visits")),
            "engagement": _engagement_score(domain),
            "diversity": _source_diversity_score(source),
            "brand": _brand_score(source.get("direct")),
        }
        score = _traffic_score(components)
        missing_metrics = []
        if domain.get("global_rank") is None:
            missing_metrics.append("global_rank")
        if domain.get("monthly_visits") is None:
            missing_metrics.append("monthly_visits")
        if domain.get("bounce_rate") is None and domain.get("pages_per_visit") is None and domain.get("avg_duration_seconds") is None:
            missing_metrics.append("engagement")
        if any(source.get(key) is None for key in ("direct", "search", "social", "referral", "paid")):
            missing_metrics.append("complete_traffic_source_breakdown")
        if domain.get("visits_trend", "unknown") == "unknown":
            missing_metrics.append("dated_traffic_trend")
        interpretation, risks = _interpretation(domain, score, focus, len(missing_metrics))
        analyzed.append({
            "domain": domain["domain"],
            "data_source": "operator_supplied_unverified",
            "metrics": {
                "global_rank": domain.get("global_rank"),
                "country_rank": domain.get("country_rank"),
                "country": str(domain.get("country") or ""),
                "monthly_visits": domain.get("monthly_visits"),
                "monthly_visits_formatted": _format_visits(domain.get("monthly_visits")),
                "visits_trend": domain.get("visits_trend", "unknown"),
                "pages_per_visit": domain.get("pages_per_visit"),
                "avg_duration_seconds": domain.get("avg_duration_seconds"),
                "bounce_rate": domain.get("bounce_rate"),
            },
            "traffic_sources": {
                key: source.get(key) for key in ("direct", "search", "social", "referral", "paid")
            },
            "component_scores": components,
            "traffic_score": score,
            "verdict": _verdict(score),
            "risk_flags": risks,
            "missing_metrics": missing_metrics,
            "interpretation": interpretation,
        })

    do_compare = len(analyzed) > 1 if compare is None else bool(compare)
    ranked = [row for row in analyzed if row["traffic_score"] is not None]
    winner = max(ranked, key=lambda item: (item["traffic_score"], item["metrics"]["monthly_visits"] or -1)) if ranked else None
    comparison = None
    if do_compare and len(analyzed) > 1:
        comparison = {
            "winner": winner["domain"] if winner else None,
            "reasoning": (
                f"{winner['domain']} leads on the supplied weighted score ({winner['traffic_score']}/100). "
                "Compare source quality and missing metrics before treating this as a decision."
                if winner else
                "No domain has enough supplied metric data to select a defensible winner."
            ),
            "basis": "operator-supplied weighted score; not independently verified",
        }

    order = {"excellent": 0, "good": 1, "fair": 2, "weak": 3, "red_flag": 4, "insufficient_data": 5}
    analyzed.sort(key=lambda item: (order[item["verdict"]], -(item["traffic_score"] if item["traffic_score"] is not None else -1)))
    if focus == "affiliate":
        recommendation = "Use these traffic indicators as one screen, then verify official affiliate terms, audience fit, conversion evidence and payout conditions before applying or promoting."
        next_skill = "affiliate-program-search"
    elif focus == "competitor":
        recommendation = "Use any reported source-channel differences to choose what to investigate next; verify them with dated analytics or authorized provider data before reallocating your strategy."
        next_skill = "competitor-spy"
    else:
        recommendation = "Treat the score as a traffic-health summary only. Independently verify the advertiser, product, affiliate terms and payment history before committing."
        next_skill = "affiliate-program-search"

    return {
        "focus": focus,
        "domains_analyzed": analyzed,
        "comparison": comparison,
        "recommendation": recommendation,
        "recommended_next_skill": next_skill,
        "scoring_weights": {key: round(value * 100) for key, value in _WEIGHTS.items()},
        "provider_connected": False,
        "external_search_performed": False,
        "traffic_data_verified": False,
        "requires_review": True,
        "publishing_started": False,
        "note": (
            "Scores use only operator-supplied metrics and are unverified. No SimilarWeb/API account, web search, "
            "domain crawl, conversion data, product-quality review or advertiser legitimacy check was performed. "
            "Missing components are omitted and the remaining weights are normalized."
        ),
    }
