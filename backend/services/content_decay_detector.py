from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlparse


_PRIORITY_ORDER = {"P0-critical": 0, "P1-high": 1, "P2-medium": 2, "P3-low": 3}
_REVENUE_SCORE = {"high": 5, "medium": 3, "low": 1, "unknown": 3}
_TIMEFRAME_LABEL = {"30d": "30 days", "90d": "90 days", "6m": "six months", "1y": "one year"}


def _paired_decline(previous: int | float | None, current: int | float | None) -> float | None:
    if previous is None or current is None or previous <= 0:
        return None
    return round(((previous - current) / previous) * 100.0, 1)


def _position_worsening(previous: int | float | None, current: int | float | None) -> float | None:
    if previous is None or current is None:
        return None
    return round(float(current) - float(previous), 1)


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _title(page: dict[str, Any]) -> str:
    title = str(page.get("title") or "").strip()
    if title:
        return title
    path = urlparse(str(page.get("url") or "")).path.rstrip("/")
    tail = path.rsplit("/", 1)[-1] if path else ""
    return tail.replace("-", " ").replace("_", " ").strip().title() or str(page.get("url") or "Untitled page")


def _refresh_actions(signals: list[str], page: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    if "clicks_declined_20_percent_or_more" in signals or "impressions_declined_20_percent_or_more" in signals:
        actions.append("Compare the affected query and device segments, then review whether the title, description and opening section still match the search intent.")
    if "search_position_worsened_5_or_more" in signals:
        actions.append("Inspect current search intent and page-one result formats; update the outline and answer the highest-value intent gaps without copying competitor text.")
    if "outdated_information_reported" in signals:
        items = page.get("outdated_elements") or []
        detail = "; ".join(str(item) for item in items[:3])
        actions.append("Verify and update the reported stale facts against authoritative sources" + (f": {detail}." if detail else "."))
    if "competitor_refresh_observed" in signals:
        actions.append("Compare the newer competing page's coverage and evidence, then add original, decision-useful sections where this page has a real gap.")
    if "serp_displacement_observed" in signals:
        actions.append("Review changes to the result page and the target query; test an appropriate result format and review structured data only where eligible.")
    if not actions:
        actions.append("Review the page manually against current search intent, sources, internal links and accessibility before changing the draft.")
    actions.extend([
        "Refresh the last-reviewed date and recheck title, meta description, headings, factual claims and broken links.",
        "Review contextual internal links to and from related pages; do not publish until an editor confirms each change.",
    ])
    return list(dict.fromkeys(actions))


def _age_signal(page: dict[str, Any], today: date) -> str | None:
    last_updated = _as_date(page.get("last_updated"))
    published = _as_date(page.get("publish_date"))
    candidate = last_updated or published
    if candidate and (today - candidate).days >= 365:
        return "content_not_updated_for_365_days_or_more"
    return None


def build_content_decay_report(
    *,
    site_url: str,
    timeframe: str,
    pages: list[dict[str, Any]],
    today: date | None = None,
) -> dict[str, Any]:
    """Rank refresh candidates from supplied metrics and observations only; never crawls or predicts recovery."""
    today = today or datetime.now(timezone.utc).date()
    decaying: list[dict[str, Any]] = []
    healthy: list[str] = []
    needs_data: list[dict[str, Any]] = []

    for page in pages:
        url = str(page.get("url") or "").strip()
        title = _title(page)
        clicks_decline = _paired_decline(page.get("previous_clicks"), page.get("current_clicks"))
        impressions_decline = _paired_decline(page.get("previous_impressions"), page.get("current_impressions"))
        position_worsening = _position_worsening(page.get("previous_avg_position"), page.get("current_avg_position"))
        metrics = {
            "clicks_decline_pct": clicks_decline,
            "impressions_decline_pct": impressions_decline,
            "position_worsening": position_worsening,
        }
        available_metric_count = sum(value is not None for value in metrics.values())
        signals: list[str] = []
        if clicks_decline is not None and clicks_decline >= 20:
            signals.append("clicks_declined_20_percent_or_more")
        if impressions_decline is not None and impressions_decline >= 20:
            signals.append("impressions_declined_20_percent_or_more")
        if position_worsening is not None and position_worsening >= 5:
            signals.append("search_position_worsened_5_or_more")
        if page.get("outdated_elements"):
            signals.append("outdated_information_reported")
        if page.get("competitor_refresh_observed") is True:
            signals.append("competitor_refresh_observed")
        if page.get("serp_displacement_observed") is True:
            signals.append("serp_displacement_observed")

        old_content_signal = _age_signal(page, today)
        preliminary_signals = [old_content_signal] if old_content_signal else []
        if signals:
            actions = _refresh_actions(signals, page)
            revenue_impact = str(page.get("revenue_impact") or "unknown")
            if revenue_impact not in _REVENUE_SCORE:
                revenue_impact = "unknown"
            revenue_score = 1 if page.get("contains_affiliate_links") is False else _REVENUE_SCORE[revenue_impact]
            severity = min(5, max(1, len(signals) + 1))
            effort_source = "operator_supplied" if page.get("refresh_effort_hours") is not None else "heuristic_estimate"
            effort = (
                round(float(page["refresh_effort_hours"]), 1)
                if page.get("refresh_effort_hours") is not None
                else round(min(12.0, max(1.0, 1.0 + 0.75 * len(actions))), 1)
            )
            fix_ease = 5 if effort <= 1 else 4 if effort <= 3 else 3 if effort <= 6 else 2 if effort <= 12 else 1
            competitor_score = 5 if page.get("competitor_refresh_observed") is True else 1 if page.get("competitor_refresh_observed") is False else 3
            priority_score = round((revenue_score * severity * fix_ease * competitor_score) / 6.25, 1)
            priority = "P0-critical" if priority_score >= 55 else "P1-high" if priority_score >= 35 else "P2-medium" if priority_score >= 18 else "P3-low"
            quant_signal_count = sum((
                clicks_decline is not None and clicks_decline >= 20,
                impressions_decline is not None and impressions_decline >= 20,
                position_worsening is not None and position_worsening >= 5,
            ))
            observed_content_count = sum((
                bool(page.get("outdated_elements")),
                page.get("competitor_refresh_observed") is True,
                page.get("serp_displacement_observed") is True,
            ))
            confidence = "medium" if quant_signal_count >= 2 or observed_content_count >= 2 or (quant_signal_count and observed_content_count) else "low"
            decaying.append({
                "url": url,
                "title": title,
                "target_keyword": str(page.get("target_keyword") or "").strip(),
                "priority": priority,
                "priority_score": priority_score,
                "decay_signals": signals,
                "preliminary_signals": preliminary_signals,
                "refresh_actions": actions,
                "estimated_effort_hours": effort,
                "effort_source": effort_source,
                "revenue_impact": revenue_impact,
                "contains_affiliate_links": page.get("contains_affiliate_links"),
                "metrics": metrics,
                "evidence_confidence": confidence,
                "data_provenance": "operator_supplied_unverified",
                "requires_review": True,
            })
        elif available_metric_count > 0 and not preliminary_signals:
            healthy.append(url)
        else:
            missing_data = []
            if clicks_decline is None:
                missing_data.append("matched previous/current click totals with a non-zero previous period")
            if impressions_decline is None:
                missing_data.append("matched previous/current impression totals with a non-zero previous period")
            if position_worsening is None:
                missing_data.append("matched previous/current average search positions")
            if not page.get("outdated_elements"):
                missing_data.append("an editor's notes about potentially outdated facts or features")
            if page.get("competitor_refresh_observed") is None:
                missing_data.append("a manually verified competitor-refresh observation (optional)")
            if page.get("serp_displacement_observed") is None:
                missing_data.append("a manually verified result-page displacement observation (optional)")
            if old_content_signal:
                missing_data.insert(0, "freshness review: content age alone does not establish performance decay")
            needs_data.append({
                "url": url,
                "title": title,
                "missing_data": list(dict.fromkeys(missing_data)),
                "preliminary_signals": preliminary_signals,
                "data_provenance": "operator_supplied_unverified",
            })

    decaying.sort(key=lambda item: (_PRIORITY_ORDER[item["priority"]], -item["priority_score"], item["url"]))
    total_effort = round(sum(item["estimated_effort_hours"] for item in decaying), 1)
    priority_queues = {
        key: [item["url"] for item in decaying if item["priority"] == key]
        for key in _PRIORITY_ORDER
    }
    return {
        "site": site_url,
        "timeframe": timeframe,
        "timeframe_label": _TIMEFRAME_LABEL.get(timeframe, timeframe),
        "pages_analyzed": len(pages),
        "pages_decaying": len(decaying),
        "total_refresh_effort_hours": total_effort,
        "decaying_pages": decaying,
        "healthy_pages": healthy,
        "pages_needing_more_data": needs_data,
        "priority_queues": priority_queues,
        "monthly_maintenance_schedule": {
            "week_1_p0": priority_queues["P0-critical"],
            "week_2_p1": priority_queues["P1-high"],
            "week_3_p2": priority_queues["P2-medium"],
            "week_4_p3_and_recheck": priority_queues["P3-low"],
        },
        "search_console_connected": False,
        "competitor_data_checked": False,
        "external_search_performed": False,
        "metrics_source": "operator_supplied_unverified",
        "traffic_recovery_estimate_supported": False,
        "requires_review": True,
        "publishing_started": False,
        "chain_metadata": {
            "skill_slug": "content-decay-detector",
            "stage": "blog",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "suggested_next": [
                "affiliate-blog-builder",
                "seo-audit",
                "internal-linking-optimizer",
                "keyword-cluster-architect",
            ],
        },
        "note": (
            "This review uses only operator-supplied comparable-period metrics and observations. "
            "No Search Console connection, live competitor/SERP lookup or page crawl was performed. "
            "Age alone is a review prompt, not proof of decay; traffic recovery is not forecast."
        ),
    }
