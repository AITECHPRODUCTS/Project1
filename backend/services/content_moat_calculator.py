from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
from typing import Any


_CAPACITY_PER_WEEK = {"1/week": 1, "2/week": 2, "3/week": 3, "5/week": 5}


def analyze_content_moat(
    *,
    niche: str,
    hub_keyword: str = "",
    your_current_pages: int = 0,
    publishing_capacity: str = "2/week",
    competitors: list[dict[str, Any]],
) -> dict[str, Any]:
    """Estimate content volume from manually supplied competitor counts; no ranking data is fetched."""
    niche = " ".join(str(niche or "").split())
    hub_keyword = " ".join(str(hub_keyword or "").split()) or niche
    if len(niche) < 3:
        raise ValueError("A niche or topic of at least three characters is required")
    if not isinstance(your_current_pages, int) or isinstance(your_current_pages, bool) or your_current_pages < 0:
        raise ValueError("Current page count must be a non-negative integer")
    if publishing_capacity not in _CAPACITY_PER_WEEK:
        raise ValueError("Publishing capacity must be 1/week, 2/week, 3/week or 5/week")
    if not 1 <= len(competitors) <= 5:
        raise ValueError("Supply between one and five manually researched competitors")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in competitors:
        domain = " ".join(str(item.get("domain") or "").strip().lower().split()).rstrip(".")
        if not domain or domain in seen:
            raise ValueError("Competitor domains must be non-empty and unique")
        seen.add(domain)
        pages = item.get("pages_on_topic")
        if not isinstance(pages, int) or isinstance(pages, bool) or pages < 0:
            raise ValueError("Competitor page counts must be non-negative integers")
        quality = str(item.get("content_quality") or "average")
        freshness = str(item.get("freshness") or "recent")
        if quality not in {"thin", "average", "deep"} or freshness not in {"stale", "recent", "actively_updated"}:
            raise ValueError("Competitor quality or freshness value is invalid")
        normalized.append({
            "domain": domain,
            "pages_on_topic": pages,
            "content_quality": quality,
            "freshness": freshness,
            "evidence_note": " ".join(str(item.get("evidence_note") or "").split()),
            "data_source": "operator_supplied_unverified",
        })

    average_pages = sum(item["pages_on_topic"] for item in normalized) / len(normalized)
    moat_target = ceil(average_pages * 1.5)
    content_gap = max(0, moat_target - your_current_pages)
    capacity = _CAPACITY_PER_WEEK[publishing_capacity]
    weeks_to_moat = ceil(content_gap / capacity) if content_gap else 0
    if moat_target < 20:
        feasibility = "green"
    elif moat_target <= 50:
        feasibility = "yellow"
    elif moat_target <= 100:
        feasibility = "orange"
    else:
        feasibility = "red"

    foundation_pages = min(content_gap, 5)
    remaining = max(0, content_gap - foundation_pages)
    supporting_pages = ceil(remaining * 0.6)
    authority_pages = max(0, remaining - supporting_pages)
    phases = [
        {"phase": "Foundation", "content": "Hub page plus core spokes", "pages": foundation_pages, "weeks": ceil(foundation_pages / capacity) if foundation_pages else 0},
        {"phase": "Supporting", "content": "Intent-specific tutorials, comparisons and long-tail spokes", "pages": supporting_pages, "weeks": ceil(supporting_pages / capacity) if supporting_pages else 0},
        {"phase": "Authority", "content": "Original research, proprietary evidence and differentiated resources", "pages": authority_pages, "weeks": ceil(authority_pages / capacity) if authority_pages else 0},
    ]

    authority_gaps: list[str] = []
    for competitor in normalized:
        if competitor["pages_on_topic"] > your_current_pages:
            authority_gaps.append(
                f"{competitor['domain']} has {competitor['pages_on_topic'] - your_current_pages} more reported topic pages than your current inventory; validate topic intent and page quality before treating volume as a competitive barrier."
            )
        if competitor["content_quality"] == "deep":
            authority_gaps.append(f"Review {competitor['domain']} for depth, evidence and unique assets that a page-count comparison cannot measure.")
        if competitor["freshness"] == "stale":
            authority_gaps.append(f"{competitor['domain']} was reported stale; verify the pages and dates before assuming a freshness opportunity.")
        if competitor["freshness"] == "actively_updated":
            authority_gaps.append(f"{competitor['domain']} was reported actively updated; plan a realistic maintenance cadence if competing directly.")
    if not authority_gaps:
        authority_gaps.append("The supplied competitor sample shows no specific page-count gap; validate the sample and inspect search intent, evidence quality and demand.")

    competitive_advantages = [
        "Prioritize distinct search intents and useful page types; a raw page count is not a ranking guarantee.",
        "Build an evidence advantage with original tests, first-party data, expert review or genuinely useful interactive resources.",
        "Use a hub-and-spoke structure and contextual internal links so readers can move between related pages naturally.",
        "Schedule maintenance and measure actual performance before expanding volume solely to reach the calculated target.",
    ]
    if any(item["content_quality"] == "deep" for item in normalized):
        competitive_advantages.insert(0, "Where competitors are deep, narrow the target intent and build stronger source-backed coverage instead of copying their breadth.")

    if content_gap == 0:
        assessment = f"The supplied page-count benchmark is met: you report {your_current_pages} pages against a modeled target of {moat_target}. Audit intent coverage, quality, freshness and measured performance before creating more pages."
        recommendation = "No page-count expansion is implied by this model. Validate the competitor sample and prioritize coverage gaps and maintenance."
    elif feasibility == "green":
        assessment = f"The modeled target is {moat_target} pages, leaving a gap of {content_gap}; at {capacity} page(s) per week the arithmetic schedule is about {weeks_to_moat} weeks. This is a manageable planning scenario, not a ranking forecast."
        recommendation = "Proceed with a narrow, evidence-led plan and reassess after the first content cluster."
    elif feasibility == "yellow":
        assessment = f"The modeled target is {moat_target} pages with a gap of {content_gap}; the arithmetic schedule is about {weeks_to_moat} weeks at the supplied capacity. This requires a sustained publishing and maintenance commitment."
        recommendation = "Proceed only if the publishing capacity is realistic; prioritize commercial intent, cluster coverage and original evidence."
    elif feasibility == "orange":
        assessment = f"The modeled target is {moat_target} pages with a gap of {content_gap}; the arithmetic schedule is about {weeks_to_moat} weeks. Page volume suggests a major investment and does not account for research, editing, links or maintenance."
        recommendation = "Narrow the niche or select a focused sub-topic before committing to a broad content roadmap."
    else:
        assessment = f"The modeled target is {moat_target} pages with a gap of {content_gap}; the arithmetic schedule is about {weeks_to_moat} weeks at the supplied capacity. This is a high content-production burden and makes a broad go decision risky."
        recommendation = "Treat the broad niche as a no-go until the scope is narrowed or a defensible differentiated asset is identified."

    return {
        "niche": niche,
        "hub_keyword": hub_keyword,
        "competitors_analyzed": len(normalized),
        "competitors": normalized,
        "average_competitor_pages": round(average_pages, 1),
        "moat_multiplier": 1.5,
        "moat_target": moat_target,
        "your_current_pages": your_current_pages,
        "content_gap": content_gap,
        "publishing_capacity": publishing_capacity,
        "publishing_capacity_pages_per_week": capacity,
        "weeks_to_moat": weeks_to_moat,
        "feasibility": feasibility,
        "assessment": assessment,
        "recommendation": recommendation,
        "phase_roadmap": phases,
        "authority_gaps": list(dict.fromkeys(authority_gaps)),
        "competitive_advantages": competitive_advantages,
        "competitor_data_verified": False,
        "live_search_performed": False,
        "search_volume_validated": False,
        "ranking_outcome_guaranteed": False,
        "data_provenance": "operator_supplied_unverified",
        "requires_review": True,
        "publishing_started": False,
        "chain_metadata": {
            "skill_slug": "content-moat-calculator",
            "stage": "blog",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "suggested_next": [
                "affiliate-blog-builder",
                "keyword-cluster-architect",
                "proprietary-data-generator",
                "content-decay-detector",
            ],
        },
        "note": (
            "This is a planning heuristic based on operator-supplied competitor counts, labels and publishing capacity. "
            "No web search, domain crawl, keyword-volume measurement or competitor verification was performed. "
            "Page count is not a ranking forecast; validate the sample and quality before deciding."
        ),
    }
