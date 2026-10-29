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
from backend.services.offer_term_snapshots import TERM_FIELDS, compare_offer_terms

SUPPORTED_RUNTIME_HANDLERS = (
    "none",
    "content.extractive_summary",
    "research.keyword_extract",
    "research.offer_metrics",
    "research.commission_calculator",
    "research.offer_term_change_review",
    "ads.guardrail_review",
    "analytics.roas_calculator",
)

_HANDLER_DESCRIPTIONS = {
    "none": "Declarative-only package; instructions are not executed.",
    "content.extractive_summary": "Deterministic local extractive summary from supplied text; no model or network call.",
    "research.keyword_extract": "Deterministic frequency-based keyword extraction from supplied text; no search-volume claim.",
    "research.offer_metrics": "Evidence-dependent EPC, conversion rate and gravity calculations from supplied offer and measured data; no provider claims.",
    "research.commission_calculator": "Estimate affiliate commission from explicitly supplied traffic, click/conversion-rate assumptions, payout terms and recurring duration; no live metrics or earnings guarantee.",
    "research.offer_term_change_review": "Normalize and compare supplied affiliate offer terms; flags material changes for human revalidation and never authenticates a provider or activates an offer.",
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



def _commission_decimal(
    value: Any,
    field: str,
    *,
    minimum: Decimal = Decimal("0"),
    maximum: Decimal = Decimal("1000000000"),
    allow_zero: bool = False,
) -> Decimal:
    """Parse an explicit monetary/rate assumption with bounded precision and range."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{field} must be a finite decimal amount")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a finite decimal amount") from exc
    if not parsed.is_finite():
        raise ValueError(f"{field} must be a finite decimal amount")
    if parsed < minimum or (not allow_zero and parsed == 0) or parsed > maximum:
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{field} must be a {qualifier} amount within the supported range")
    try:
        normalized = parsed.quantize(Decimal("0.000001"))
    except InvalidOperation as exc:
        raise ValueError(f"{field} exceeds the supported numeric precision or range") from exc
    if normalized != parsed:
        raise ValueError(f"{field} supports at most six meaningful decimal places")
    return normalized


def _commission_amount_string(value: Decimal) -> str:
    """Use fixed-point decimal strings for financial outputs instead of binary floats."""
    return format(value.quantize(Decimal("0.000001")), "f")


def _commission_calculator(payload: dict[str, Any]) -> dict[str, Any]:
    """Project commission from explicit operator assumptions; never fetch or attest metrics."""
    allowed_top = {
        "monthly_visitors",
        "click_through_rate_pct",
        "affiliate_conversion_rate_pct",
        "programs",
    }
    unexpected = sorted(set(payload) - allowed_top)
    if unexpected:
        raise ValueError("unsupported commission-calculator input fields: " + ", ".join(unexpected[:8]))
    missing = sorted(allowed_top - set(payload))
    if missing:
        raise ValueError("commission calculator is missing fields: " + ", ".join(missing))

    visitors = payload["monthly_visitors"]
    if isinstance(visitors, bool) or not isinstance(visitors, int) or not 0 <= visitors <= 1_000_000_000:
        raise ValueError("monthly_visitors must be an integer from 0 to 1000000000")
    ctr = _commission_decimal(
        payload["click_through_rate_pct"], "click_through_rate_pct",
        maximum=Decimal("100"), allow_zero=True,
    )
    conversion_rate = _commission_decimal(
        payload["affiliate_conversion_rate_pct"], "affiliate_conversion_rate_pct",
        maximum=Decimal("100"), allow_zero=True,
    )
    programs = payload["programs"]
    if not isinstance(programs, list) or not 1 <= len(programs) <= 10:
        raise ValueError("programs must contain between 1 and 10 items")

    visitor_count = Decimal(visitors)
    expected_clicks = visitor_count * ctr / Decimal("100")
    expected_conversions = expected_clicks * conversion_rate / Decimal("100")
    currency_seen: str | None = None
    results: list[dict[str, Any]] = []
    reward_types = {"cps_one_time", "cps_recurring", "cpl", "cpa"}

    for index, item in enumerate(programs):
        prefix = f"programs[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{prefix} must be a JSON object")
        allowed_program = {
            "name", "reward_type", "commission_type", "commission_value",
            "currency", "average_order_value", "recurring_paid_months",
        }
        extra = sorted(set(item) - allowed_program)
        if extra:
            raise ValueError(f"{prefix} contains unsupported fields: " + ", ".join(extra[:8]))
        required = {"name", "reward_type", "commission_type", "commission_value", "currency"}
        missing_program = sorted(required - set(item))
        if missing_program:
            raise ValueError(f"{prefix} is missing fields: " + ", ".join(missing_program))

        name = item["name"]
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
            raise ValueError(f"{prefix}.name must be a non-empty string of at most 120 characters")
        reward_type = item["reward_type"]
        if reward_type not in reward_types:
            raise ValueError(f"{prefix}.reward_type is unsupported")
        commission_type = item["commission_type"]
        if commission_type not in {"percentage", "fixed"}:
            raise ValueError(f"{prefix}.commission_type must be percentage or fixed")
        if commission_type == "percentage" and reward_type not in {"cps_one_time", "cps_recurring"}:
            raise ValueError(f"{prefix} percentage commissions are only valid for CPS programs")

        currency = item["currency"]
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Za-z]{3}", currency.strip()):
            raise ValueError(f"{prefix}.currency must be a three-letter currency code")
        currency = currency.strip().upper()
        if currency_seen is None:
            currency_seen = currency
        elif currency != currency_seen:
            raise ValueError("programs must use the same currency; mixed-currency comparisons are not ranked")

        commission_value = _commission_decimal(
            item["commission_value"], f"{prefix}.commission_value",
            maximum=Decimal("1000000000"),
        )
        if commission_type == "percentage":
            if "average_order_value" not in item:
                raise ValueError(f"{prefix}.average_order_value is required for percentage commissions")
            average_order_value = _commission_decimal(
                item["average_order_value"], f"{prefix}.average_order_value",
                maximum=Decimal("1000000000"),
            )
            if commission_value > Decimal("100"):
                raise ValueError(f"{prefix}.commission_value percentage cannot exceed 100")
            commission_per_conversion = average_order_value * commission_value / Decimal("100")
        else:
            if "average_order_value" in item:
                raise ValueError(f"{prefix}.average_order_value must be omitted for fixed commissions")
            average_order_value = None
            commission_per_conversion = commission_value

        recurring_months: int | None = None
        if reward_type == "cps_recurring":
            recurring_months = item.get("recurring_paid_months")
            if (
                isinstance(recurring_months, bool)
                or not isinstance(recurring_months, int)
                or not 1 <= recurring_months <= 120
            ):
                raise ValueError(f"{prefix}.recurring_paid_months must be an integer from 1 to 120")
        elif "recurring_paid_months" in item:
            raise ValueError(f"{prefix}.recurring_paid_months is only valid for recurring CPS programs")

        first_month = expected_conversions * commission_per_conversion
        if recurring_months is None:
            twelve_month_cohort_factor = 12
            basis = "one-time commission for each monthly conversion cohort"
        else:
            # Every monthly cohort is assumed to keep paying for the supplied duration;
            # churn/refunds are not inferred, so this is explicitly a pre-churn projection.
            twelve_month_cohort_factor = sum(min(recurring_months, 12 - month_index) for month_index in range(12))
            basis = "recurring cohort projection capped at supplied duration; assumes no churn or refunds"
        twelve_month_total = expected_conversions * commission_per_conversion * Decimal(twelve_month_cohort_factor)

        results.append({
            "name": name.strip(),
            "reward_type": reward_type,
            "currency": currency,
            "commission_per_conversion_amount": _commission_amount_string(commission_per_conversion),
            "expected_monthly_clicks": _commission_amount_string(expected_clicks),
            "expected_monthly_conversions": _commission_amount_string(expected_conversions),
            "estimated_first_month_commission": _commission_amount_string(first_month),
            "estimated_12_month_commission": _commission_amount_string(twelve_month_total),
            "recurring_paid_months": recurring_months,
            "projection_basis": basis,
        })

    results.sort(key=lambda result: (-Decimal(result["estimated_12_month_commission"]), result["name"].casefold()))
    return {
        "programs": results,
        "measurement_basis": {
            "monthly_visitors": visitors,
            "click_through_rate_pct_assumption": _commission_amount_string(ctr),
            "affiliate_conversion_rate_pct_assumption": _commission_amount_string(conversion_rate),
        },
        "currency_comparison": currency_seen,
        "input_provenance": "caller_supplied_assumptions",
        "provider_metrics_verified": False,
        "earnings_guaranteed": False,
        "external_provider_calls_made": False,
        "money_transferred": False,
        "requires_human_review": True,
        "notes": [
            "Clicks, conversions and commissions are expected-value estimates, not observed counts or earnings.",
            "The projection assumes constant monthly visitors and rates, with no refunds, cancellations, fraud or attribution loss.",
            "Recurring projections assume each cohort continues paying for the supplied duration; churn is not modeled.",
            "No market benchmarks or provider metrics were fetched or inferred.",
        ],
    }


def _validated_offer_term_record(value: Any, field: str) -> dict[str, Any]:
    """Validate bounded term fields before passing them to the shared comparator."""
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    extra = sorted(set(value) - set(TERM_FIELDS))
    if extra:
        raise ValueError(f"{field} contains unsupported fields: " + ", ".join(extra[:8]))
    for name, max_length in (("terms_version", 200), ("commission_type", 100), ("commission_currency", 12)):
        candidate = value.get(name)
        if candidate is not None and (
            not isinstance(candidate, str) or len(candidate) > max_length
        ):
            raise ValueError(f"{field}.{name} must be a string of at most {max_length} characters")
    for name in ("allowed_regions", "restricted_traffic_sources"):
        candidate = value.get(name)
        if candidate is None:
            continue
        if not isinstance(candidate, list) or len(candidate) > 200:
            raise ValueError(f"{field}.{name} must be a list with at most 200 entries")
        if any(
            not isinstance(item, str) or not item.strip() or len(item) > 80
            for item in candidate
        ):
            raise ValueError(f"{field}.{name} entries must be non-empty strings of at most 80 characters")
    return dict(value)


def _offer_term_change_review(payload: dict[str, Any]) -> dict[str, Any]:
    """Compare terms supplied by the caller without upgrading them to verified evidence."""
    allowed = {"previous_terms", "current_terms", "has_previous_snapshot"}
    unexpected = sorted(set(payload) - allowed)
    if unexpected:
        raise ValueError("unsupported offer-term-review input fields: " + ", ".join(unexpected[:8]))
    missing = sorted({"current_terms", "has_previous_snapshot"} - set(payload))
    if missing:
        raise ValueError("offer-term review is missing fields: " + ", ".join(missing))
    has_previous = payload["has_previous_snapshot"]
    if not isinstance(has_previous, bool):
        raise ValueError("has_previous_snapshot must be a boolean")

    current = _validated_offer_term_record(payload["current_terms"], "current_terms")
    if has_previous:
        if "previous_terms" not in payload:
            raise ValueError("previous_terms is required when has_previous_snapshot is true")
        previous = _validated_offer_term_record(payload["previous_terms"], "previous_terms")
    else:
        if "previous_terms" in payload:
            raise ValueError("previous_terms must be omitted when no previous snapshot exists")
        # The first observation creates a baseline; it is not a change from invented history.
        previous = current

    result = compare_offer_terms(previous, current, has_previous_snapshot=has_previous)
    review_reasons = ["source_authenticity_not_independently_verified"]
    if result["requires_revalidation"]:
        review_reasons.append("material_offer_terms_changed")
    result.update({
        "source_attestation_verified": False,
        "provider_approval_verified": False,
        "automatic_activation_permitted": False,
        "requires_human_review": True,
        "review_reasons": review_reasons,
        "note": (
            "This handler compares supplied term snapshots only. It does not authenticate the "
            "merchant/network, prove current eligibility, or permit offer activation."
        ),
    })
    return result


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
    scenario_observations = []
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
        # Skill inputs are operator-controlled JSON, not authenticated provider
        # evidence. Retain the declared label only as caller input; never pass it
        # into the authoritative evaluator as proof of provider verification.
        observed_at = _guardrail_timestamp(item["observed_at"], f"observations[{index}].observed_at")
        normalized = {
            "platform": item["platform"].strip().lower(),
            "creative_id": item["creative_id"].strip(),
            "observed_at": observed_at,
            "spend_usd": _guardrail_decimal(item["spend_usd"], f"observations[{index}].spend_usd"),
            "commission_usd": _guardrail_decimal(item["commission_usd"], f"observations[{index}].commission_usd"),
            "impressions": _guardrail_count(item["impressions"], f"observations[{index}].impressions"),
            "clicks": _guardrail_count(item["clicks"], f"observations[{index}].clicks"),
            "conversions": _guardrail_count(item["conversions"], f"observations[{index}].conversions"),
        }
        normalized_observations.append(SimpleNamespace(
            **normalized,
            evidence_status="operator_supplied_unverified",
        ))
        scenario_observations.append(SimpleNamespace(
            **normalized,
            evidence_status="provider_verified",
        ))

    plan_budget = None
    if "plan_daily_budget_usd" in payload:
        plan_budget = _guardrail_decimal(payload["plan_daily_budget_usd"], "plan_daily_budget_usd")
    policy_object = SimpleNamespace(**normalized_policy)
    # The authoritative decision always fails closed because this pure runtime
    # cannot independently authenticate the source of caller-supplied metrics.
    result = evaluate_ad_budget_guardrail(
        policy=policy_object,
        observations=normalized_observations,
        now=now,
        plan_daily_budget_usd=plan_budget,
    )
    # Optional scenario calculations are explicitly hypothetical, so an input
    # label of "provider_verified" can never become a trusted decision or action.
    scenario = evaluate_ad_budget_guardrail(
        policy=policy_object,
        observations=scenario_observations,
        now=now,
        plan_daily_budget_usd=plan_budget,
    )
    result["input_provenance"] = "caller_supplied_unattested"
    result["source_attestation_verified"] = False
    result["operational_action_permitted"] = False
    result["hypothetical_review"] = {
        "basis": "scenario_only_if_inputs_are_independently_attested",
        "status_if_independently_attested": scenario["status"],
        "potential_breaches_if_independently_attested": scenario["breaches"],
        "sample_gate_if_independently_attested": scenario["sample_gate"],
        "freshness_gate_if_independently_attested": scenario["freshness_gate"],
        "spend_metrics_if_independently_attested": {
            "daily_spend_usd": scenario["verified_spend_today_usd"],
            "campaign_spend_usd": scenario["verified_campaign_spend_usd"],
            "roas": scenario["verified_roas"],
            "cpa_usd": scenario["verified_cpa_usd"],
        },
        "is_provider_attested": False,
        "provider_action_executed": False,
    }
    result["note"] = (
        "Authoritative status is calculated only from caller-supplied, unattested input and therefore "
        "fails closed. The nested scenario is hypothetical if these values are independently verified; "
        "it is not provider evidence and cannot authorize a live spend, pause or kill-switch action."
    )
    return result


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
    if handler_key == "research.commission_calculator":
        return _commission_calculator(payload)
    if handler_key == "research.offer_term_change_review":
        return _offer_term_change_review(payload)
    if handler_key == "ads.guardrail_review":
        return _ad_guardrail_review(payload)
    if handler_key == "analytics.roas_calculator":
        return _roas_calculator(payload)
    raise ValueError("Unsupported runtime handler")
