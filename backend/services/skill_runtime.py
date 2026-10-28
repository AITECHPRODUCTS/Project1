from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any

from backend.services.ad_guardrails import evaluate_ad_budget_guardrail

from backend.services.offer_intelligence import compute_offer_metrics

SUPPORTED_RUNTIME_HANDLERS = (
    "none",
    "content.extractive_summary",
    "research.keyword_extract",
    "research.offer_metrics",
    "ads.guardrail_review",
    "analytics.roas_calculator",
)

_HANDLER_DESCRIPTIONS = {
    "none": "Declarative-only package; instructions are not executed.",
    "content.extractive_summary": "Deterministic local extractive summary from supplied text; no model or network call.",
    "research.keyword_extract": "Deterministic frequency-based keyword extraction from supplied text; no search-volume claim.",
    "research.offer_metrics": "Evidence-dependent EPC, conversion rate and gravity calculations from supplied offer and measured data; no provider claims.",
    "ads.guardrail_review": "Evaluate supplied provider-verified ad observations, freshness and spend caps; review-only, no provider action.",
    "analytics.roas_calculator": "Decimal-based ROAS calculation and review-only stop-loss signal; no campaign action.",
}


def describe_runtime_handlers() -> list[dict[str, str]]:
    return [
        {"key": key, "description": _HANDLER_DESCRIPTIONS[key], "external_side_effects": "none"}
        for key in SUPPORTED_RUNTIME_HANDLERS
    ]


def _require_input_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Skill runtime input must be a JSON object")
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Skill runtime input must contain finite JSON values only") from exc
    if len(encoded.encode("utf-8")) > 32 * 1024:
        raise ValueError("Skill runtime input exceeds the 32 KiB execution limit")
    return value


def _text_extract_summary(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload.get("text")
    limit = payload.get("max_sentences")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if len(text) > 20000:
        raise ValueError("text exceeds the 20,000 character runtime limit")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
        raise ValueError("max_sentences must be an integer from 1 to 10")
    normalized = " ".join(text.split())
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]
    selected = sentences[:limit]
    return {
        "summary": " ".join(selected),
        "sentence_count": len(selected),
        "source_character_count": len(normalized),
    }


_STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "your", "you", "are",
    "was", "were", "has", "have", "had", "into", "about", "when", "where",
    "how", "why", "can", "will", "not", "but", "its", "their", "our", "use",
    "using", "through", "then", "than", "they", "them", "all", "new", "per",
}


def _keyword_extract(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload.get("text")
    limit = payload.get("limit")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if len(text) > 20000:
        raise ValueError("text exceeds the 20,000 character runtime limit")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("limit must be an integer from 1 to 20")
    tokens = re.findall(r"[a-z0-9][a-z0-9'-]{1,}", text.casefold())
    counts = Counter(token.strip("'-") for token in tokens)
    candidates = {word: count for word, count in counts.items() if len(word) >= 3 and word not in _STOP_WORDS}
    ranked = sorted(candidates, key=lambda word: (-candidates[word], word))[:limit]
    return {
        "keywords": ranked,
        "keyword_count": len(ranked),
        "source_token_count": len(tokens),
    }



def _offer_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    """Calculate offer metrics from explicit inputs without inventing missing measurements."""
    allowed = {"offer", "clicks", "conversions", "total_revenue", "gravity_weight"}
    unexpected = sorted(set(payload) - allowed)
    if unexpected:
        raise ValueError("unsupported offer-metrics input fields: " + ", ".join(unexpected[:8]))
    offer = payload.get("offer")
    if not isinstance(offer, dict):
        raise ValueError("offer must be a JSON object")
    return compute_offer_metrics(
        offer,
        clicks=payload.get("clicks"),
        conversions=payload.get("conversions"),
        total_revenue=payload.get("total_revenue"),
        gravity_weight=payload.get("gravity_weight", 1.0),
    )



def _guardrail_decimal(value: Any, field: str, *, nullable: bool = False) -> Decimal | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{field} must be a finite non-negative amount")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a finite non-negative amount") from exc
    if not result.is_finite() or result < 0 or result > Decimal("1000000000000"):
        raise ValueError(f"{field} must be a finite non-negative amount within the supported range")
    return result


def _guardrail_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or len(value) > 64 or "T" not in value:
        raise ValueError(f"{field} must be an ISO-8601 timestamp with an explicit timezone")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include an explicit timezone")
    return parsed


def _guardrail_count(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000_000:
        raise ValueError(f"{field} must be a non-negative integer within the supported range")
    return value


def _ad_guardrail_review(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate supplied observations against configured guardrails without changing ad accounts."""
    allowed_top = {"policy", "observations", "now", "plan_daily_budget_usd"}
    unexpected = sorted(set(payload) - allowed_top)
    if unexpected:
        raise ValueError("unsupported ad-guardrail input fields: " + ", ".join(unexpected[:8]))

    raw_policy = payload.get("policy")
    if not isinstance(raw_policy, dict):
        raise ValueError("policy must be a JSON object")
    policy_fields = {
        "id", "campaign_plan_id", "daily_spend_cap_usd", "campaign_spend_cap_usd",
        "minimum_roas", "maximum_cpa_usd", "minimum_verified_impressions",
        "minimum_verified_clicks", "minimum_verified_conversions",
    }
    missing = sorted(policy_fields - set(raw_policy))
    extra = sorted(set(raw_policy) - policy_fields)
    if missing:
        raise ValueError("policy is missing fields: " + ", ".join(missing[:8]))
    if extra:
        raise ValueError("unsupported policy fields: " + ", ".join(extra[:8]))

    policy_id = raw_policy["id"]
    plan_id = raw_policy["campaign_plan_id"]
    for value, field in ((policy_id, "policy.id"), (plan_id, "policy.campaign_plan_id")):
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            raise ValueError(f"{field} must be a non-empty string of at most 128 characters")

    daily_cap = _guardrail_decimal(raw_policy["daily_spend_cap_usd"], "policy.daily_spend_cap_usd")
    campaign_cap = _guardrail_decimal(raw_policy["campaign_spend_cap_usd"], "policy.campaign_spend_cap_usd")
    minimum_roas = _guardrail_decimal(raw_policy["minimum_roas"], "policy.minimum_roas")
    maximum_cpa = _guardrail_decimal(raw_policy["maximum_cpa_usd"], "policy.maximum_cpa_usd", nullable=True)
    if daily_cap == 0 or campaign_cap == 0 or daily_cap > campaign_cap:
        raise ValueError("policy spend caps must be positive and daily cap cannot exceed campaign cap")
    if minimum_roas > Decimal("1000000"):
        raise ValueError("policy.minimum_roas exceeds the supported upper bound")

    normalized_policy = {
        "id": policy_id.strip(),
        "campaign_plan_id": plan_id.strip(),
        "daily_spend_cap_usd": daily_cap,
        "campaign_spend_cap_usd": campaign_cap,
        "minimum_roas": minimum_roas,
        "maximum_cpa_usd": maximum_cpa,
        "minimum_verified_impressions": _guardrail_count(raw_policy["minimum_verified_impressions"], "policy.minimum_verified_impressions"),
        "minimum_verified_clicks": _guardrail_count(raw_policy["minimum_verified_clicks"], "policy.minimum_verified_clicks"),
        "minimum_verified_conversions": _guardrail_count(raw_policy["minimum_verified_conversions"], "policy.minimum_verified_conversions"),
    }

    now = _guardrail_timestamp(payload.get("now"), "now")
    raw_observations = payload.get("observations")
    if not isinstance(raw_observations, list) or len(raw_observations) > 1000:
        raise ValueError("observations must be a list with at most 1000 entries")
    observation_fields = {
        "platform", "creative_id", "observed_at", "spend_usd", "commission_usd",
        "impressions", "clicks", "conversions", "evidence_status",
    }
    normalized_observations = []
    for index, item in enumerate(raw_observations):
        if not isinstance(item, dict):
            raise ValueError(f"observations[{index}] must be a JSON object")
        missing_observation = observation_fields - set(item)
        unexpected_observation = set(item) - observation_fields
        if missing_observation:
            raise ValueError(f"observations[{index}] is missing required fields")
        if unexpected_observation:
            raise ValueError(f"observations[{index}] contains unsupported fields")
        for field, limit in (("platform", 40), ("creative_id", 255), ("evidence_status", 60)):
            value = item[field]
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError(f"observations[{index}].{field} must be a non-empty string of at most {limit} characters")
        normalized_observations.append(SimpleNamespace(
            platform=item["platform"].strip().lower(),
            creative_id=item["creative_id"].strip(),
            observed_at=_guardrail_timestamp(item["observed_at"], f"observations[{index}].observed_at"),
            spend_usd=_guardrail_decimal(item["spend_usd"], f"observations[{index}].spend_usd"),
            commission_usd=_guardrail_decimal(item["commission_usd"], f"observations[{index}].commission_usd"),
            impressions=_guardrail_count(item["impressions"], f"observations[{index}].impressions"),
            clicks=_guardrail_count(item["clicks"], f"observations[{index}].clicks"),
            conversions=_guardrail_count(item["conversions"], f"observations[{index}].conversions"),
            evidence_status=item["evidence_status"].strip().lower(),
        ))

    plan_budget = None
    if "plan_daily_budget_usd" in payload:
        plan_budget = _guardrail_decimal(payload["plan_daily_budget_usd"], "plan_daily_budget_usd")
    return evaluate_ad_budget_guardrail(
        policy=SimpleNamespace(**normalized_policy),
        observations=normalized_observations,
        now=now,
        plan_daily_budget_usd=plan_budget,
    )


def _roas_calculator(payload: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Decimal] = {}
    monetary_limit = Decimal("999999999999.999999")
    threshold_limit = Decimal("1000000")
    scale = Decimal("0.000001")
    for key in ("spend_usd", "commission_usd", "minimum_roas"):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError(f"{key} must be a finite non-negative number")
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"{key} must be a finite non-negative number") from exc
        if not decimal_value.is_finite() or decimal_value < 0:
            raise ValueError(f"{key} must be a finite non-negative number")
        try:
            normalized = decimal_value.quantize(scale)
        except InvalidOperation as exc:
            raise ValueError(f"{key} exceeds the supported numeric precision or range") from exc
        if normalized != decimal_value:
            raise ValueError(f"{key} supports at most six meaningful decimal places")
        limit = threshold_limit if key == "minimum_roas" else monetary_limit
        if normalized > limit:
            raise ValueError(f"{key} exceeds the supported upper bound")
        values[key] = normalized

    spend = values["spend_usd"]
    commission = values["commission_usd"]
    minimum = values["minimum_roas"]
    common = {
        "roas_available": spend > 0,
        "pause_recommended": False,
        "minimum_roas": float(minimum),
        "requires_human_review": True,
    }
    if spend == 0:
        return {**common, "reason": "ROAS is unavailable because spend is zero."}
    ratio = commission / spend
    if ratio > Decimal("1000000000000"):
        raise ValueError("computed ROAS exceeds the supported output range")
    try:
        rounded_ratio = ratio.quantize(scale)
    except InvalidOperation as exc:
        raise ValueError("computed ROAS exceeds the supported output precision") from exc
    below = ratio < minimum
    return {
        **common,
        "roas": float(rounded_ratio),
        "pause_recommended": bool(below),
        "reason": (
            "Below threshold; review only. Confirm attribution-window maturity before any pause."
            if below else
            "At or above threshold; no remote campaign action was taken."
        ),
    }


def execute_skill_handler(handler_key: str, input_value: Any) -> dict[str, Any]:
    """Execute one code-owned pure handler. Package Markdown and authored code are never executed."""
    if handler_key not in SUPPORTED_RUNTIME_HANDLERS:
        raise ValueError("Unsupported runtime handler")
    if handler_key == "none":
        raise ValueError("This package has no executable runtime handler")
    payload = _require_input_object(input_value)
    if handler_key == "content.extractive_summary":
        return _text_extract_summary(payload)
    if handler_key == "research.keyword_extract":
        return _keyword_extract(payload)
    if handler_key == "research.offer_metrics":
        return _offer_metrics(payload)
    if handler_key == "ads.guardrail_review":
        return _ad_guardrail_review(payload)
    if handler_key == "analytics.roas_calculator":
        return _roas_calculator(payload)
    raise ValueError("Unsupported runtime handler")
