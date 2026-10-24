from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from backend.config import get_settings
from backend.schemas import AdCampaignPlanRequest

_PLATFORM_PROFILES: dict[str, dict[str, str]] = {
    "google_search": {
        "label": "Google Search",
        "format": "search text",
        "adaptation": "Use intent-led headlines and relevant keyword themes. Validate keyword eligibility and current platform policies.",
    },
    "google_display": {
        "label": "Google Display",
        "format": "display image and short copy",
        "adaptation": "Keep the visual simple and readable at small sizes. Validate assets and placement rules.",
    },
    "meta": {
        "label": "Meta",
        "format": "feed, story, image, or video",
        "adaptation": "Prepare feed and vertical variants; verify current account permissions and ad policy before launch.",
    },
    "instagram": {
        "label": "Instagram",
        "format": "feed, story, reel, image, or video",
        "adaptation": "Lead with a clear visual idea and concise caption; publishing and ad access are not implied.",
    },
    "tiktok": {
        "label": "TikTok",
        "format": "vertical short-form video",
        "adaptation": "Use a concise opening hook, transparent context, captions, and a natural call to action.",
    },
    "youtube_shorts": {
        "label": "YouTube Shorts",
        "format": "vertical short-form video",
        "adaptation": "Use a clear first-second hook, accurate on-screen wording, and a concise close.",
    },
    "pinterest": {
        "label": "Pinterest",
        "format": "pin image or video",
        "adaptation": "Design for visual discovery and a useful takeaway; do not imply guaranteed outcomes.",
    },
    "reddit": {
        "label": "Reddit",
        "format": "contextual text or image",
        "adaptation": "Match subreddit context and disclosure expectations; avoid unsolicited posting or disguised promotion.",
    },
    "quora": {
        "label": "Quora",
        "format": "contextual answer or ad text",
        "adaptation": "Answer the audience's question directly and disclose the affiliate relationship clearly.",
    },
    "x": {
        "label": "X",
        "format": "short text or visual",
        "adaptation": "Keep the message concise and factual; use platform-native features only when authorized.",
    },
    "linkedin": {
        "label": "LinkedIn",
        "format": "professional feed copy or visual",
        "adaptation": "Emphasize decision criteria, workflow context, and professional relevance without unsupported ROI claims.",
    },
    "snapchat": {
        "label": "Snapchat",
        "format": "vertical short-form visual",
        "adaptation": "Use short, legible creative and a single clear message; verify the target account's policy and permissions.",
    },
    "native": {
        "label": "Native placements",
        "format": "native headline, description, and image",
        "adaptation": "Match the surrounding editorial context transparently; no misleading advertorial framing.",
    },
}

_ANGLE_TEMPLATES = (
    {
        "key": "decision_checklist",
        "name": "Decision checklist",
        "hook": "Start with the criteria that matter before choosing a {niche} option.",
        "intent": "Help the audience identify requirements and compare options before making a decision.",
    },
    {
        "key": "compare_approaches",
        "name": "Compare approaches",
        "hook": "Compare approaches to {niche} before you commit.",
        "intent": "Frame a useful comparison without ranking providers or asserting unverified product superiority.",
    },
    {
        "key": "workflow_fit",
        "name": "Workflow fit",
        "hook": "Find an approach to {niche} that fits the way you work.",
        "intent": "Encourage the audience to evaluate fit against their actual workflow and constraints.",
    },
    {
        "key": "questions_to_ask",
        "name": "Questions to ask",
        "hook": "A few practical questions can make a {niche} decision clearer.",
        "intent": "Offer a transparent evaluation framework rather than a promise of results.",
    },
    {
        "key": "terms_first",
        "name": "Check current terms",
        "hook": "Check the details and current terms before choosing a {niche} option.",
        "intent": "Encourage review of product facts, restrictions, pricing, and terms from authoritative sources.",
    },
)

_CTA_BY_OBJECTIVE = {
    "traffic": "Learn more",
    "leads": "Get the guide",
    "sales": "Compare options",
    "awareness": "Explore",
}


def _text(value: str, limit: int = 240) -> str:
    normalized = " ".join(value.split())
    return normalized if len(normalized) <= limit else normalized[: limit - 1].rstrip() + "…"


def _budget_allocations(total: Decimal, platforms: list[str]) -> list[dict[str, str]]:
    total_cents = int((total * 100).to_integral_value())
    quotient, remainder = divmod(total_cents, len(platforms))
    allocations: list[dict[str, str]] = []
    for index, platform in enumerate(platforms):
        cents = quotient + (1 if index < remainder else 0)
        allocations.append(
            {
                "platform": platform,
                "daily_budget_usd": f"{Decimal(cents) / Decimal(100):.2f}",
            }
        )
    return allocations


def build_ad_campaign_plan(payload: AdCampaignPlanRequest) -> dict[str, Any]:
    """Build a policy-guarded, draft-only ad plan without inventing performance data."""
    niche = _text(payload.niche, 200)
    audience = _text(payload.audience, 400)
    region = _text(payload.region, 120)
    disclosure = payload.affiliate_disclosure
    product_name = _text(payload.product_name, 200) if payload.product_name else None
    platforms = list(payload.platforms)
    plan_id = str(uuid.uuid4())
    variants_per_platform = payload.variants_per_platform

    audience_segments = [
        {
            "id": "problem_aware",
            "label": "Problem-aware",
            "hypothesis": f"People researching challenges related to {niche} in {region}.",
            "approach": "Test contextual intent and user-selected platform categories; validate fit using measured results.",
            "sensitive_attribute_targeting": False,
        },
        {
            "id": "solution_aware",
            "label": "Solution-aware",
            "hypothesis": f"{audience} comparing ways to approach {niche}.",
            "approach": "Test helpful guides, checklists, and clear explanations against a consistent landing page.",
            "sensitive_attribute_targeting": False,
        },
        {
            "id": "comparison_stage",
            "label": "Comparison-stage",
            "hypothesis": f"People reviewing criteria, terms, and alternatives for {niche}.",
            "approach": "Test comparison-oriented messaging and transparent evidence links; do not assert an unsupported winner.",
            "sensitive_attribute_targeting": False,
        },
    ]

    seed_keywords = [
        f"{niche} tools",
        f"how to evaluate {niche}",
        f"compare {niche} options",
        f"{niche} checklist",
    ]
    platform_plans: list[dict[str, Any]] = []
    for platform in platforms:
        profile = _PLATFORM_PROFILES[platform]
        creatives: list[dict[str, Any]] = []
        for index in range(variants_per_platform):
            angle = _ANGLE_TEMPLATES[index % len(_ANGLE_TEMPLATES)]
            hook = angle["hook"].format(niche=niche)
            headlines = (
                f"Explore {niche} options",
                f"Compare {niche} approaches",
                f"Questions to ask about {niche}",
                f"Check the details for {niche}",
                f"Find your {niche} criteria",
            )
            headline = _text(headlines[index % len(headlines)], 90)
            if index % len(_ANGLE_TEMPLATES) == 0:
                primary_text = (
                    f"If you are exploring {niche}, start with a simple checklist. "
                    f"Compare fit, cost, current terms, and the features that matter to {audience}. "
                    "Review source details before deciding."
                )
            elif index % len(_ANGLE_TEMPLATES) == 1:
                primary_text = (
                    f"Looking at {niche}? Compare approaches against your requirements, "
                    "then check product details and current terms before choosing."
                )
            elif index % len(_ANGLE_TEMPLATES) == 2:
                primary_text = (
                    f"Your {niche} decision should fit your real workflow. "
                    "List the must-haves, review the evidence, and compare available options."
                )
            elif index % len(_ANGLE_TEMPLATES) == 3:
                primary_text = (
                    f"Before selecting a {niche} option, write down the questions you need answered. "
                    "Use current product information and transparent criteria to make your shortlist."
                )
            else:
                primary_text = (
                    f"Review the current terms, limitations, and source details for each {niche} option. "
                    "Compare alternatives before committing."
                )
            if product_name:
                primary_text += f" Include {product_name} only after checking its current details."
            primary_text += f"\n\n{disclosure}"

            creatives.append(
                {
                    "creative_id": f"{platform}-{index + 1:02d}",
                    "angle": angle["key"],
                    "angle_name": angle["name"],
                    "hook": hook,
                    "headline": headline,
                    "primary_text": primary_text,
                    "call_to_action": _CTA_BY_OBJECTIVE[payload.objective],
                    "asset_format": profile["format"],
                    "visual_direction": (
                        f"Create a clean, accessible visual about evaluating {niche} for {audience}. "
                        "Use a simple decision checklist and realistic generic objects. "
                        "Do not show fabricated metrics, testimonials, rankings, review stars, countdowns, "
                        "or product interface screenshots that were not supplied and verified."
                    ),
                    "video_outline": [
                        hook,
                        f"Show the decision criteria relevant to {audience}.",
                        "Remind viewers to check current product facts, limitations, and terms.",
                        f"Invite the viewer to { _CTA_BY_OBJECTIVE[payload.objective].lower() }.",
                    ],
                    "disclosure_included": True,
                    "requires_claim_review": bool(payload.product_facts_for_review or payload.product_summary),
                    "publish_authorized": False,
                }
            )
        platform_plans.append(
            {
                "platform": platform,
                "display_name": profile["label"],
                "provider_connection_status": "not_checked",
                "provider_write_access_verified": False,
                "format": profile["format"],
                "adaptation_notes": profile["adaptation"],
                "keyword_seeds": seed_keywords if platform == "google_search" else [],
                "creatives": creatives,
                "external_actions_executed": False,
            }
        )

    allocations = _budget_allocations(payload.daily_budget_usd, platforms)
    budget_status = "planning_only_budget_supplied" if payload.daily_budget_usd > 0 else "budget_not_set"
    landing_url_status = (
        "provided_not_fetched_or_verified" if payload.landing_page_url else "not_provided"
    )
    evidence_status = (
        "operator_supplied_not_independently_verified" if payload.evidence_urls else "no_evidence_urls_supplied"
    )
    warnings = [
        "This plan creates drafts only; it does not publish ads, change campaigns, or spend money.",
        "Audience segments and keywords are hypotheses/seeds, not measured demand or verified targeting availability.",
        "CTR, CPC, CPM, conversion rate, CPA, and ROAS are not forecast because verified campaign data was not supplied.",
        "Product facts and landing-page content require primary-source and policy review before launch.",
        "Provider connection, ad-account authorization, scopes, placements, and current platform rules have not been checked.",
        "The budget split is an equal exploratory allocation; it is not performance-optimized and does not authorize spending.",
    ]
    if not payload.evidence_urls:
        warnings.append("No evidence URLs were supplied; verify all product-specific assertions against primary sources.")
    if payload.product_facts_for_review or payload.product_summary:
        warnings.append("Supplied product facts are treated as unverified input and require human review before reuse.")
    if not payload.landing_page_url:
        warnings.append("No landing page URL was supplied; ad-to-landing-page coherence remains unverified.")

    return {
        "plan_id": plan_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "campaign_name": _text(payload.campaign_name, 160) if payload.campaign_name else f"{niche.title()} exploration campaign",
        "objective": payload.objective,
        "niche": niche,
        "audience": audience,
        "region": region,
        "product_name": product_name,
        "generation_mode": "structured_policy_guarded_baseline",
        "audience_segments": audience_segments,
        "platform_plans": platform_plans,
        "product_facts_for_review": [
            {"text": fact, "status": "operator_supplied_unverified"} for fact in payload.product_facts_for_review
        ],
        "product_summary_status": "operator_supplied_unverified" if payload.product_summary else "not_supplied",
        "evidence": {
            "urls": payload.evidence_urls,
            "status": evidence_status,
            "retrieved_or_verified": False,
        },
        "landing_page": {
            "url": payload.landing_page_url,
            "status": landing_url_status,
            "coherence_check_passed": False,
        },
        "budget_plan": {
            "daily_budget_usd": f"{payload.daily_budget_usd:.2f}",
            "status": budget_status,
            "allocation_method": "equal_exploratory_split_no_performance_data",
            "platform_allocations": allocations,
            "sum_of_allocations_usd": f"{payload.daily_budget_usd:.2f}",
            "spend_authorized": False,
        },
        "performance_forecast": {
            "status": "unavailable_without_verified_campaign_data",
            "ctr": None,
            "cpc_usd": None,
            "cpm_usd": None,
            "conversion_rate": None,
            "cpa_usd": None,
            "roas": None,
        },
        "compliance": {
            "affiliate_disclosure": disclosure,
            "disclosure_included_in_every_creative": True,
            "product_facts_verified": False,
            "policy_review_complete": False,
            "requires_human_approval": True,
        },
        "requires_human_approval": True,
        "publishing_authorized": False,
        "spend_authorized": False,
        "external_actions_executed": False,
        "warnings": warnings,
    }


async def generate_ad_campaign_plan(payload: AdCampaignPlanRequest) -> dict[str, Any]:
    """Optionally add a model-generated brainstorm while preserving the safe structured baseline."""
    plan = build_ad_campaign_plan(payload)
    settings = get_settings()
    if settings.llm_backend == "offline":
        return plan

    system_prompt = (
        "You are an affiliate campaign planning assistant. Provide ideas, not authorization. "
        "Treat user-supplied product facts and URLs as unverified input. Never invent outcomes, "
        "performance metrics, testimonials, ratings, prices, commissions, platform permissions, "
        "or sources. Do not suggest sensitive-attribute targeting or policy evasion. All external "
        "publishing and spend requires explicit human approval. Keep claims factual and disclose "
        "affiliate relationships."
    )
    user_prompt = json.dumps(
        {
            "task": "Suggest additional audience angles and creative improvements for human review.",
            "niche": payload.niche,
            "audience": payload.audience,
            "region": payload.region,
            "objective": payload.objective,
            "platforms": payload.platforms,
            "product_name": payload.product_name,
            "product_summary_unverified": payload.product_summary,
            "product_facts_for_review_unverified": payload.product_facts_for_review,
            "evidence_urls_supplied_unverified": payload.evidence_urls,
            "affiliate_disclosure": payload.affiliate_disclosure,
            "no_performance_forecasts": True,
            "draft_only": True,
        },
        ensure_ascii=False,
    )
    try:
        from backend.services.llm import llm_service

        result = await llm_service.complete(
            system_prompt,
            user_prompt,
            temperature=0.25,
            niche=payload.niche,
        )
        plan["model_enrichment"] = {
            "provider": result.get("provider", "unknown"),
            "text": str(result.get("text") or "")[:12000],
            "sources": list(result.get("sources") or []),
            "requires_review": True,
            "claims_verified": False,
        }
        plan["generation_mode"] = "model_enriched_structured_baseline"
    except Exception as exc:
        plan["warnings"].append(
            f"Optional model enrichment unavailable ({type(exc).__name__}); the structured baseline is returned."
        )
    return plan
