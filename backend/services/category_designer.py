from __future__ import annotations

import re
from typing import Any

_STOP_WORDS = frozenset("a an and are as at be been by for from how in into is it of on or the their this to with your".split())


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", str(value or "").casefold())
        if token not in _STOP_WORDS and len(token) > 1
    }


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").casefold()).strip("-")
    return slug[:80].strip("-") or "category"


def _overlap_score(proposed: set[str], existing: set[str]) -> int:
    if not proposed:
        return 0
    return round(100 * len(proposed & existing) / len(proposed))


def design_category_taxonomy(
    *, niche: str, target_audience: str, topic_candidates: list[str], existing_categories: list[str] | None = None
) -> dict[str, Any]:
    """Build a review-only hierarchy from supplied topics, without inventing demand or search volume."""
    niche = " ".join(str(niche or "").split())
    audience = " ".join(str(target_audience or "").split())
    candidates = list(dict.fromkeys(" ".join(str(item or "").split()) for item in topic_candidates if str(item or "").strip()))
    existing = list(dict.fromkeys(" ".join(str(item or "").split()) for item in (existing_categories or []) if str(item or "").strip()))
    if len(niche) < 3 or len(audience) < 2:
        raise ValueError("A niche and target audience are required")
    if not 3 <= len(candidates) <= 15:
        raise ValueError("Provide between three and fifteen distinct topic candidates")
    if any(len(topic) > 120 for topic in candidates):
        raise ValueError("Each topic candidate must be at most 120 characters")
    if any(len(category) > 120 for category in existing):
        raise ValueError("Each existing category must be at most 120 characters")

    existing_tokens = [(category, _tokens(category)) for category in existing]
    used_slugs: set[str] = set()
    categories: list[dict[str, Any]] = []
    for index, topic in enumerate(candidates, start=1):
        base_slug = _slug(topic)
        slug = base_slug
        suffix = 2
        while slug in used_slugs:
            tail = f"-{suffix}"
            slug = base_slug[:80 - len(tail)].rstrip("-") + tail
            suffix += 1
        used_slugs.add(slug)
        proposed_tokens = _tokens(topic)
        best_category = None
        best_overlap = 0
        for existing_name, existing_set in existing_tokens:
            score = _overlap_score(proposed_tokens, existing_set)
            if score > best_overlap:
                best_overlap = score
                best_category = existing_name
        flags = []
        if best_overlap >= 60:
            flags.append("possible_duplicate_or_near_duplicate")
        elif best_overlap >= 35:
            flags.append("review_category_scope_overlap")
        categories.append({
            "name": topic,
            "slug": slug,
            "parent_category": niche,
            "description": (
                f"Resources about {topic} for {audience} within {niche}, "
                "with practical guidance and clearly sourced explanations."
            ),
            "overlap_score_vs_existing": best_overlap if existing else None,
            "matched_existing_category": best_category,
            "flags": flags,
            "origin": "operator_supplied_topic_candidate",
        })

    flagged_count = sum(bool(item["flags"]) for item in categories)
    recommendations = [
        "Validate the proposed hierarchy with actual visitor tasks and editorial owners before publishing.",
        "Search volume, search intent, traffic potential and commercial value have not been measured.",
        "Review slug collisions, existing-category overlaps and canonical/navigation effects before applying this taxonomy.",
    ]
    if not existing:
        recommendations.append("No existing category inventory was supplied, so duplicate/overlap checks against the current site are incomplete.")
    return {
        "root_category": niche,
        "target_audience": audience,
        "categories": categories,
        "category_count": len(categories),
        "existing_category_count": len(existing),
        "categories_flagged_for_review": flagged_count,
        "taxonomy_method": "operator_supplied_topics_with_deterministic_slug_and_lexical_overlap_checks",
        "search_volume_validated": False,
        "taxonomy_evaluated": False,
        "publishing_started": False,
        "requires_review": True,
        "recommendations": recommendations,
        "note": "This is a taxonomy draft from supplied labels, not an evaluated SEO architecture or a demand forecast.",
    }
