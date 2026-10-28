from __future__ import annotations

import pytest

from backend.services.skill_packager import build_skill_package, validate_skill_value
from backend.services.skill_runtime import SUPPORTED_RUNTIME_HANDLERS, execute_skill_handler


def test_extractive_summary_is_deterministic_and_bounded():
    text = "Alpha helps teams. Beta improves workflows. Gamma supports analysis."
    expected = {
        "summary": "Alpha helps teams. Beta improves workflows.",
        "sentence_count": 2,
        "source_character_count": len(text),
    }
    payload = {"text": text, "max_sentences": 2}
    assert execute_skill_handler("content.extractive_summary", payload) == expected
    assert execute_skill_handler("content.extractive_summary", payload) == expected


def test_keyword_extract_is_repeatable_and_does_not_claim_search_volume():
    result = execute_skill_handler(
        "research.keyword_extract",
        {"text": "Affiliate marketing guide guide builds conversion", "limit": 3},
    )
    assert result == {
        "keywords": ["guide", "affiliate", "builds"],
        "keyword_count": 3,
        "source_token_count": 6,
    }


def test_roas_handler_is_decimal_safe_and_only_returns_a_review_signal():
    result = execute_skill_handler(
        "analytics.roas_calculator",
        {"spend_usd": 50, "commission_usd": 75, "minimum_roas": 1.2},
    )
    assert result["roas_available"] is True
    assert result["roas"] == 1.5
    assert result["pause_recommended"] is False
    assert result["requires_human_review"] is True
    assert "no remote campaign action was taken" in result["reason"]

    no_spend = execute_skill_handler(
        "analytics.roas_calculator",
        {"spend_usd": 0, "commission_usd": 75, "minimum_roas": 1.2},
    )
    assert no_spend["roas_available"] is False
    assert "roas" not in no_spend
    assert no_spend["pause_recommended"] is False


@pytest.mark.parametrize("handler", ["__import__", "python.exec", "http.request", "none"])
def test_unknown_or_non_executable_handler_fails_closed(handler):
    with pytest.raises(ValueError):
        execute_skill_handler(handler, {"text": "Do not run arbitrary instructions"})


def test_skill_contract_fixtures_execute_allowlisted_handler_and_compare_real_outputs():
    text = "Alpha helps teams. Beta improves workflows. Gamma supports analysis."
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "minLength": 1, "maxLength": 20000},
            "max_sentences": {"type": "integer", "minimum": 1, "maximum": 10},
        },
        "required": ["text", "max_sentences"],
        "additionalProperties": False,
    }
    output_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "maxLength": 20000},
            "sentence_count": {"type": "integer", "minimum": 0, "maximum": 10},
            "source_character_count": {"type": "integer", "minimum": 0, "maximum": 20000},
        },
        "required": ["summary", "sentence_count", "source_character_count"],
        "additionalProperties": False,
    }
    expected = {
        "summary": "Alpha helps teams. Beta improves workflows.",
        "sentence_count": 2,
        "source_character_count": len(text),
    }
    payload = {
        "skill_id": "content/extractive-summary",
        "display_name": "Extractive summary",
        "version": "1.0.0",
        "description": "Summarize supplied text by returning its leading sentences.",
        "stage": "S2",
        "runtime_handler": "content.extractive_summary",
        "capabilities": ["content.draft"],
        "input_schema": input_schema,
        "output_schema": output_schema,
        "instructions_markdown": "# Declarative guidance\nInstructions are not executed.",
        "test_cases": [{"name": "two sentence summary", "input": {"text": text, "max_sentences": 2}, "expected_output": expected}],
    }
    built = build_skill_package(payload)
    report = built["validation_report"]
    assert report["all_fixtures_passed"] is True
    assert report["runtime_handler_allowlisted"] is True
    assert report["runtime_execution_tested"] is True
    assert report["runtime_fixtures_executed"] == 1
    assert report["skill_instructions_executed"] is False
    assert report["external_actions_executed"] is False
    assert report["cases"][0]["runtime_output_matches_expected"] is True
    assert built["manifest"]["runtime_handler"] == "content.extractive_summary"


def test_runtime_fixture_that_only_matches_schema_but_not_handler_output_fails():
    payload = {
        "skill_id": "research/keyword-extract",
        "display_name": "Keyword extract",
        "version": "1.0.0",
        "description": "Extract frequent terms from a supplied text sample.",
        "stage": "S3",
        "runtime_handler": "research.keyword_extract",
        "capabilities": ["research.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "minLength": 1},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["text", "limit"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "keywords": {"type": "array", "items": {"type": "string", "minLength": 3, "maxLength": 50}, "maxItems": 20},
                "keyword_count": {"type": "integer", "minimum": 0, "maximum": 20},
                "source_token_count": {"type": "integer", "minimum": 0, "maximum": 5000},
            },
            "required": ["keywords", "keyword_count", "source_token_count"],
            "additionalProperties": False,
        },
        "instructions_markdown": "# Declarative guidance\nNever invent search-volume metrics.",
        "test_cases": [{
            "name": "incorrect expected terms",
            "input": {"text": "Affiliate marketing guide guide builds conversion", "limit": 3},
            "expected_output": {"keywords": ["marketing", "affiliate", "guide"], "keyword_count": 3, "source_token_count": 6},
        }],
    }
    built = build_skill_package(payload)
    assert built["validation_report"]["all_fixtures_passed"] is False
    assert built["validation_report"]["cases"][0]["runtime_output_matches_expected"] is False
    assert built["validation_report"]["cases"][0]["runtime_errors"]


def test_runtime_schema_validation_rejects_boolean_as_number_and_non_finite_values():
    schema = {"type": "number", "minimum": 0}
    assert validate_skill_value(True, schema)
    assert validate_skill_value(float("nan"), schema)
    assert validate_skill_value(float("inf"), schema)


def test_runtime_catalog_is_explicit_and_contains_no_user_supplied_code_execution():
    assert set(SUPPORTED_RUNTIME_HANDLERS) == {
        "none", "content.extractive_summary", "research.keyword_extract", "research.offer_metrics", "ads.guardrail_review", "analytics.roas_calculator"
    }



@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("spend_usd", "1000000000000.00"),
        ("spend_usd", "0.0000001"),
        ("commission_usd", "12.1234567"),
        ("minimum_roas", "1000000.1"),
    ],
)
def test_roas_handler_rejects_out_of_range_or_unrepresentable_values(field, value):
    payload = {"spend_usd": 50, "commission_usd": 60, "minimum_roas": 1.2}
    payload[field] = value
    with pytest.raises(ValueError):
        execute_skill_handler("analytics.roas_calculator", payload)


def test_roas_handler_rejects_ratio_that_exceeds_its_supported_output_range():
    with pytest.raises(ValueError, match="ROAS exceeds the supported output range"):
        execute_skill_handler(
            "analytics.roas_calculator",
            {
                "spend_usd": "0.000001",
                "commission_usd": "999999999999.999999",
                "minimum_roas": 1,
            },
        )



def test_offer_metrics_handler_calculates_only_from_supplied_measured_values():
    result = execute_skill_handler(
        "research.offer_metrics",
        {
            "offer": {"reward_type": "one-time", "gravity_score": 4.5},
            "clicks": 20,
            "conversions": 2,
            "total_revenue": 50,
            "gravity_weight": 2,
        },
    )
    assert result == {
        "gravity_score": 4.5,
        "normalized_gravity": 9.0,
        "epc": 2.5,
        "conversion_rate": 0.1,
        "recurring_commission": False,
        "recurring_commission_value": None,
        "measurement_basis": {
            "clicks": 20,
            "conversions": 2,
            "total_revenue": 50.0,
            "gravity_weight": 2.0,
        },
    }

    unknown = execute_skill_handler("research.offer_metrics", {"offer": {"reward_type": "one-time"}})
    assert unknown["epc"] is None
    assert unknown["conversion_rate"] is None
    assert unknown["gravity_score"] is None
    assert unknown["measurement_basis"]["clicks"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"offer": "not-an-object"},
        {"offer": {}, "untrusted_extra": True},
        {"offer": {}, "clicks": 1.5},
        {"offer": {}, "clicks": 2, "conversions": 3},
        {"offer": {}, "total_revenue": float("inf")},
        {"offer": {}, "gravity_weight": float("nan")},
    ],
)
def test_offer_metrics_handler_rejects_invalid_or_ambiguous_inputs(payload):
    with pytest.raises(ValueError):
        execute_skill_handler("research.offer_metrics", payload)


def test_offer_metrics_skill_fixture_executes_the_real_allowlisted_handler():
    input_value = {
        "offer": {"reward_type": "one-time", "gravity_score": 4.5},
        "clicks": 20,
        "conversions": 2,
        "total_revenue": 50,
        "gravity_weight": 2,
    }
    expected = {
        "gravity_score": 4.5,
        "normalized_gravity": 9.0,
        "epc": 2.5,
        "conversion_rate": 0.1,
        "recurring_commission": False,
        "recurring_commission_value": None,
        "measurement_basis": {
            "clicks": 20,
            "conversions": 2,
            "total_revenue": 50.0,
            "gravity_weight": 2.0,
        },
    }
    payload = {
        "skill_id": "research/offer-metrics",
        "display_name": "Measured offer metrics",
        "version": "1.0.0",
        "description": "Calculate evidence-dependent offer metrics from measured values supplied by the operator.",
        "stage": "S1",
        "runtime_handler": "research.offer_metrics",
        "capabilities": ["research.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "offer": {
                    "type": "object",
                    "properties": {
                        "reward_type": {"type": "string"},
                        "gravity_score": {"type": "number", "minimum": 0},
                    },
                    "required": ["reward_type", "gravity_score"],
                    "additionalProperties": False,
                },
                "clicks": {"type": "integer", "minimum": 0},
                "conversions": {"type": "integer", "minimum": 0},
                "total_revenue": {"type": "number", "minimum": 0},
                "gravity_weight": {"type": "number", "minimum": 0, "maximum": 10},
            },
            "required": ["offer", "clicks", "conversions", "total_revenue", "gravity_weight"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "gravity_score": {"type": "number", "minimum": 0},
                "normalized_gravity": {"type": "number", "minimum": 0},
                "epc": {"type": "number", "minimum": 0},
                "conversion_rate": {"type": "number", "minimum": 0, "maximum": 1},
                "recurring_commission": {"type": "boolean"},
                "recurring_commission_value": {"type": "null"},
                "measurement_basis": {
                    "type": "object",
                    "properties": {
                        "clicks": {"type": "integer", "minimum": 0},
                        "conversions": {"type": "integer", "minimum": 0},
                        "total_revenue": {"type": "number", "minimum": 0},
                        "gravity_weight": {"type": "number", "minimum": 0, "maximum": 10},
                    },
                    "required": ["clicks", "conversions", "total_revenue", "gravity_weight"],
                    "additionalProperties": False,
                },
            },
            "required": [
                "gravity_score", "normalized_gravity", "epc", "conversion_rate",
                "recurring_commission", "recurring_commission_value", "measurement_basis",
            ],
            "additionalProperties": False,
        },
        "instructions_markdown": "# Declarative guidance\nUse measured evidence only; do not infer provider approval or search volume.",
        "test_cases": [{"name": "measured one-time offer", "input": input_value, "expected_output": expected}],
    }
    built = build_skill_package(payload)
    report = built["validation_report"]
    assert report["all_fixtures_passed"] is True
    assert report["runtime_execution_tested"] is True
    assert report["cases"][0]["runtime_output_matches_expected"] is True
    assert built["manifest"]["runtime_handler"] == "research.offer_metrics"



def _guardrail_policy_payload(**overrides):
    policy = {
        "id": "policy-guardrail-1",
        "campaign_plan_id": "plan-1",
        "daily_spend_cap_usd": "30.00",
        "campaign_spend_cap_usd": "500.00",
        "minimum_roas": "1.20",
        "maximum_cpa_usd": "35.00",
        "minimum_verified_impressions": 1000,
        "minimum_verified_clicks": 30,
        "minimum_verified_conversions": 3,
    }
    policy.update(overrides)
    return policy


def _guardrail_observation_payload(**overrides):
    observation = {
        "platform": "meta",
        "creative_id": "creative-1",
        "observed_at": "2026-10-28T17:00:00+00:00",
        "spend_usd": "30.00",
        "commission_usd": "60.00",
        "impressions": 1000,
        "clicks": 50,
        "conversions": 4,
        "evidence_status": "provider_verified",
    }
    observation.update(overrides)
    return observation


def _guardrail_payload(observations=None, **overrides):
    payload = {
        "policy": _guardrail_policy_payload(),
        "observations": [_guardrail_observation_payload()] if observations is None else observations,
        "now": "2026-10-28T18:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def test_ad_guardrail_handler_fails_closed_for_unverified_evidence():
    result = execute_skill_handler(
        "ads.guardrail_review",
        _guardrail_payload(observations=[_guardrail_observation_payload(evidence_status="operator_supplied_unverified")]),
    )
    assert result["status"] == "blocked_pending_provider_verification"
    assert result["stop_recommended"] is False
    assert result["kill_switch_should_engage"] is False
    assert result["live_spend_authorized"] is False
    assert result["provider_action_executed"] is False
    assert result["input_provenance"] == "caller_supplied_unattested"
    assert result["source_attestation_verified"] is False
    assert result["operational_action_permitted"] is False
    assert result["status"] == "blocked_pending_provider_verification"
    assert result["hypothetical_review"]["status_if_independently_attested"] == "triggered_stop"
    assert result["hypothetical_review"]["is_provider_attested"] is False


def test_ad_guardrail_handler_does_not_trust_caller_claimed_provider_verified_evidence():
    result = execute_skill_handler("ads.guardrail_review", _guardrail_payload())
    # Even though the input declares provider_verified, this pure handler
    # cannot establish provenance and must not emit a real stop recommendation.
    assert result["status"] == "blocked_pending_provider_verification"
    assert result["stop_recommended"] is False
    assert result["kill_switch_should_engage"] is False
    assert result["live_spend_authorized"] is False
    assert result["provider_action_executed"] is False
    assert result["source_attestation_verified"] is False
    assert result["operational_action_permitted"] is False
    assert result["hypothetical_review"]["status_if_independently_attested"] == "triggered_stop"
    assert {item["code"] for item in result["hypothetical_review"]["potential_breaches_if_independently_attested"]} == {"daily_spend_cap_reached"}
    assert result["hypothetical_review"]["is_provider_attested"] is False
    assert "fails closed" in result["note"]


def test_ad_guardrail_handler_blocks_stale_input_and_reports_only_hypothetical_review():
    stale = _guardrail_observation_payload(observed_at="2026-10-25T18:00:00+00:00", spend_usd="60.00")
    result = execute_skill_handler("ads.guardrail_review", _guardrail_payload(observations=[stale]))
    assert result["status"] == "blocked_pending_provider_verification"
    assert result["breaches"] == []
    assert result["stop_recommended"] is False
    assert result["kill_switch_should_engage"] is False
    assert result["provider_action_executed"] is False
    assert result["hypothetical_review"]["status_if_independently_attested"] == "blocked_stale_provider_evidence"
    assert result["hypothetical_review"]["potential_breaches_if_independently_attested"] == []
    assert result["hypothetical_review"]["is_provider_attested"] is False


@pytest.mark.parametrize(
    "payload",
    [
        _guardrail_payload(now="2026-10-28T18:00:00"),
        _guardrail_payload(policy=_guardrail_policy_payload(unexpected="x")),
        _guardrail_payload(policy=_guardrail_policy_payload(daily_spend_cap_usd="NaN")),
        _guardrail_payload(policy=_guardrail_policy_payload(daily_spend_cap_usd="10", campaign_spend_cap_usd="5")),
        _guardrail_payload(observations=[_guardrail_observation_payload(clicks=True)]),
        _guardrail_payload(observations=[_guardrail_observation_payload(spend_usd="Infinity")]),
        _guardrail_payload(observations=[_guardrail_observation_payload(extra_field="value")]),
    ],
)
def test_ad_guardrail_handler_rejects_ambiguous_or_invalid_inputs(payload):
    with pytest.raises(ValueError):
        execute_skill_handler("ads.guardrail_review", payload)
