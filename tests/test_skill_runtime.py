from __future__ import annotations

import pytest

from backend.services.offer_term_snapshots import compare_offer_terms
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
    assert validate_skill_value(0, schema) == []
    assert validate_skill_value(True, schema) == ["input: expected number, received bool"]
    assert validate_skill_value(float("nan"), schema) == ["input: number must be finite"]
    assert validate_skill_value(float("inf"), schema) == ["input: number must be finite"]
    assert validate_skill_value(float("-inf"), schema) == ["input: number must be finite"]


def test_runtime_schema_validation_checks_array_items_after_the_legacy_scan_limit():
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
        "minItems": 1,
        "maxItems": 150,
    }
    value = [{"ok": True} for _ in range(100)]
    value.append({"ok": True, "unexpected": "must be rejected"})
    errors = validate_skill_value(value, schema)
    assert "input[100].unexpected: additional property is not allowed" in errors


def test_runtime_schema_validation_checks_object_properties_after_the_legacy_scan_limit():
    declared = {f"field_{index:03d}": {"type": "integer"} for index in range(100)}
    schema = {"type": "object", "properties": declared, "additionalProperties": False}
    value = {key: index for index, key in enumerate(declared)}
    value["unexpected_after_100"] = "must be rejected"
    errors = validate_skill_value(value, schema)
    assert "input.unexpected_after_100: additional property is not allowed" in errors


def test_runtime_catalog_is_explicit_and_contains_no_user_supplied_code_execution():
    assert set(SUPPORTED_RUNTIME_HANDLERS) == {
        "none", "content.extractive_summary", "research.keyword_extract", "research.offer_metrics",
        "research.commission_calculator", "research.offer_term_change_review", "ads.guardrail_review", "analytics.roas_calculator"
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



def _term_payload(**overrides):
    values = {
        "terms_version": "terms-v1",
        "commission_type": "percentage",
        "commission_value": "10.0000",
        "commission_currency": "usd",
        "cookie_days": 30,
        "attribution_window_days": 30,
        "allowed_regions": ["US", "GB"],
        "restricted_traffic_sources": ["paid_search"],
    }
    values.update(overrides)
    return values


def test_offer_term_change_review_detects_material_changes_without_claiming_verification():
    result = execute_skill_handler(
        "research.offer_term_change_review",
        {
            "previous_terms": _term_payload(),
            "current_terms": _term_payload(commission_value="12", commission_currency="USD", allowed_regions=["US"]),
            "has_previous_snapshot": True,
        },
    )
    assert result["change_status"] == "changes_detected"
    assert result["changed_fields"] == ["commission_value", "allowed_regions"]
    assert result["changes"] == [
        {"field": "commission_value", "previous": "10.0000", "current": "12.0000"},
        {"field": "allowed_regions", "previous": ["GB", "US"], "current": ["US"]},
    ]
    assert result["requires_revalidation"] is True
    assert result["source_attestation_verified"] is False
    assert result["provider_approval_verified"] is False
    assert result["automatic_activation_permitted"] is False
    assert result["requires_human_review"] is True
    assert "material_offer_terms_changed" in result["review_reasons"]
    assert len(result["terms_sha256"]) == 64


def test_offer_term_change_review_normalizes_values_and_does_not_flag_equivalent_terms():
    result = execute_skill_handler(
        "research.offer_term_change_review",
        {
            "previous_terms": _term_payload(commission_value="10", commission_currency="usd", allowed_regions=["US", "GB"]),
            "current_terms": _term_payload(commission_value="10.0000", commission_currency="USD", allowed_regions=["GB", "US"]),
            "has_previous_snapshot": True,
        },
    )
    assert result["change_status"] == "unchanged"
    assert result["changed_fields"] == []
    assert result["requires_revalidation"] is False
    assert result["source_attestation_verified"] is False
    assert result["automatic_activation_permitted"] is False
    assert result["requires_human_review"] is True


def test_offer_term_change_review_records_first_snapshot_as_baseline():
    result = execute_skill_handler(
        "research.offer_term_change_review",
        {
            "current_terms": _term_payload(),
            "has_previous_snapshot": False,
        },
    )
    assert result["change_status"] == "baseline_recorded"
    assert result["changed_fields"] == []
    assert result["requires_revalidation"] is False
    assert result["requires_human_review"] is True


@pytest.mark.parametrize(
    "payload",
    [
        {"current_terms": _term_payload(), "has_previous_snapshot": "false"},
        {"current_terms": _term_payload(), "has_previous_snapshot": True},
        {"current_terms": _term_payload(), "has_previous_snapshot": False, "previous_terms": _term_payload()},
        {"current_terms": _term_payload(extra_field="pretend_verified"), "has_previous_snapshot": False},
        {"current_terms": _term_payload(allowed_regions="US"), "has_previous_snapshot": False},
        {"current_terms": _term_payload(allowed_regions=[1]), "has_previous_snapshot": False},
        {"current_terms": _term_payload(commission_value="NaN"), "has_previous_snapshot": False},
        {"current_terms": _term_payload(), "has_previous_snapshot": False, "provider_approval_verified": True},
    ],
)
def test_offer_term_change_review_rejects_ambiguous_or_untrusted_shapes(payload):
    with pytest.raises(ValueError):
        execute_skill_handler("research.offer_term_change_review", payload)


def test_offer_term_change_review_executes_as_a_governed_skill_package_fixture():
    previous = _term_payload()
    current = _term_payload(commission_value="12", allowed_regions=["US"])
    input_value = {
        "previous_terms": previous,
        "current_terms": current,
        "has_previous_snapshot": True,
    }
    expected = compare_offer_terms(previous, current, has_previous_snapshot=True)
    expected.update({
        "source_attestation_verified": False,
        "provider_approval_verified": False,
        "automatic_activation_permitted": False,
        "requires_human_review": True,
        "review_reasons": ["source_authenticity_not_independently_verified", "material_offer_terms_changed"],
        "note": (
            "This handler compares supplied term snapshots only. It does not authenticate the "
            "merchant/network, prove current eligibility, or permit offer activation."
        ),
    })
    term_object = {"type": "object", "additionalProperties": True}
    input_schema = {
        "type": "object",
        "properties": {
            "previous_terms": term_object,
            "current_terms": term_object,
            "has_previous_snapshot": {"type": "boolean"},
        },
        "required": ["previous_terms", "current_terms", "has_previous_snapshot"],
        "additionalProperties": False,
    }
    output_schema = {
        "type": "object",
        "properties": {
            "current_terms": term_object,
            "terms_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "change_status": {"type": "string", "enum": ["baseline_recorded", "unchanged", "changes_detected"]},
            "changed_fields": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
            "changes": {"type": "array", "items": {"type": "object", "additionalProperties": True}, "maxItems": 8},
            "requires_revalidation": {"type": "boolean"},
            "source_attestation_verified": {"type": "boolean"},
            "provider_approval_verified": {"type": "boolean"},
            "automatic_activation_permitted": {"type": "boolean"},
            "requires_human_review": {"type": "boolean"},
            "review_reasons": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
            "note": {"type": "string"},
        },
        "required": [
            "current_terms", "terms_sha256", "change_status", "changed_fields", "changes",
            "requires_revalidation", "source_attestation_verified", "provider_approval_verified",
            "automatic_activation_permitted", "requires_human_review", "review_reasons", "note",
        ],
        "additionalProperties": False,
    }
    package = build_skill_package({
        "skill_id": "research/offer-term-change-review",
        "display_name": "Offer term change review",
        "version": "1.0.0",
        "description": "Compare supplied affiliate-offer snapshots and request review after material changes.",
        "stage": "S1",
        "runtime_handler": "research.offer_term_change_review",
        "capabilities": ["research.read"],
        "input_schema": input_schema,
        "output_schema": output_schema,
        "instructions_markdown": "# Declarative guidance\nNever treat a term comparison as provider authentication or approval.",
        "test_cases": [{
            "name": "commission and region change",
            "input": input_value,
            "expected_output": expected,
        }],
    })
    report = package["validation_report"]
    assert report["all_fixtures_passed"] is True
    assert report["runtime_handler_allowlisted"] is True
    assert report["runtime_execution_tested"] is True
    assert report["cases"][0]["runtime_output_matches_expected"] is True



def _commission_program(name, **overrides):
    value = {
        "name": name,
        "reward_type": "cps_one_time",
        "commission_type": "percentage",
        "commission_value": "20",
        "currency": "USD",
        "average_order_value": "50",
    }
    value.update(overrides)
    if overrides.get("commission_type") == "fixed" and "average_order_value" not in overrides:
        value.pop("average_order_value", None)
    return value


def _commission_payload(**overrides):
    value = {
        "monthly_visitors": 100,
        "click_through_rate_pct": "10",
        "affiliate_conversion_rate_pct": "10",
        "programs": [
            _commission_program("One-time Example"),
            _commission_program(
                "Recurring Example",
                reward_type="cps_recurring",
                commission_type="fixed",
                commission_value="15",
                currency="usd",
                recurring_paid_months=3,
            ),
        ],
    }
    value.update(overrides)
    return value


def test_commission_calculator_uses_explicit_assumptions_and_ranks_same_currency_programs():
    result = execute_skill_handler("research.commission_calculator", _commission_payload())
    assert [row["name"] for row in result["programs"]] == ["Recurring Example", "One-time Example"]
    recurring, one_time = result["programs"]
    assert recurring == {
        "name": "Recurring Example",
        "reward_type": "cps_recurring",
        "currency": "USD",
        "commission_per_conversion_amount": "15.000000",
        "expected_monthly_clicks": "10.000000",
        "expected_monthly_conversions": "1.000000",
        "estimated_first_month_commission": "15.000000",
        "estimated_12_month_commission": "495.000000",
        "recurring_paid_months": 3,
        "projection_basis": "recurring cohort projection capped at supplied duration; assumes no churn or refunds",
    }
    assert one_time["commission_per_conversion_amount"] == "10.000000"
    assert one_time["expected_monthly_clicks"] == "10.000000"
    assert one_time["expected_monthly_conversions"] == "1.000000"
    assert one_time["estimated_first_month_commission"] == "10.000000"
    assert one_time["estimated_12_month_commission"] == "120.000000"
    assert result["measurement_basis"] == {
        "monthly_visitors": 100,
        "click_through_rate_pct_assumption": "10.000000",
        "affiliate_conversion_rate_pct_assumption": "10.000000",
    }
    assert result["input_provenance"] == "caller_supplied_assumptions"
    assert result["provider_metrics_verified"] is False
    assert result["earnings_guaranteed"] is False
    assert result["external_provider_calls_made"] is False
    assert result["money_transferred"] is False
    assert result["requires_human_review"] is True


@pytest.mark.parametrize(
    "payload",
    [
        _commission_payload(monthly_visitors=True),
        _commission_payload(monthly_visitors=-1),
        _commission_payload(click_through_rate_pct=float("nan")),
        _commission_payload(affiliate_conversion_rate_pct=101),
        _commission_payload(programs=[]),
        _commission_payload(programs=[_commission_program("USD"), _commission_program("GBP", currency="GBP")]),
        _commission_payload(programs=[_commission_program("Lead", reward_type="cpl")]),
        _commission_payload(programs=[_commission_program("No price", average_order_value=None)]),
        _commission_payload(programs=[_commission_program("Too much", commission_value=101)]),
        _commission_payload(programs=[_commission_program("Recurring without duration", reward_type="cps_recurring")]),
        _commission_payload(programs=[_commission_program("One-time with duration", recurring_paid_months=3)]),
        _commission_payload(programs=[_commission_program("Fixed with price", commission_type="fixed", average_order_value="50")]),
        _commission_payload(programs=[_commission_program("Unhashable reward type", reward_type=[])]),
        _commission_payload(programs=[_commission_program("Unhashable commission type", commission_type={})]),
        _commission_payload(extra_field="untrusted"),
    ],
)
def test_commission_calculator_rejects_ambiguous_or_invalid_assumptions(payload):
    with pytest.raises(ValueError):
        execute_skill_handler("research.commission_calculator", payload)


def test_commission_calculator_is_executable_through_a_governed_skill_fixture():
    input_value = {
        "monthly_visitors": 100,
        "click_through_rate_pct": 10,
        "affiliate_conversion_rate_pct": 10,
        "programs": [_commission_program("One-time Example")],
    }
    expected = {
        "programs": [{
            "name": "One-time Example",
            "reward_type": "cps_one_time",
            "currency": "USD",
            "commission_per_conversion_amount": "10.000000",
            "expected_monthly_clicks": "10.000000",
            "expected_monthly_conversions": "1.000000",
            "estimated_first_month_commission": "10.000000",
            "estimated_12_month_commission": "120.000000",
            "recurring_paid_months": None,
            "projection_basis": "one-time commission for each monthly conversion cohort",
        }],
        "measurement_basis": {
            "monthly_visitors": 100,
            "click_through_rate_pct_assumption": "10.000000",
            "affiliate_conversion_rate_pct_assumption": "10.000000",
        },
        "currency_comparison": "USD",
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
    input_schema = {
        "type": "object",
        "properties": {
            "monthly_visitors": {"type": "integer", "minimum": 0, "maximum": 1000000000},
            "click_through_rate_pct": {"type": "number", "minimum": 0, "maximum": 100},
            "affiliate_conversion_rate_pct": {"type": "number", "minimum": 0, "maximum": 100},
            "programs": {"type": "array", "minItems": 1, "maxItems": 10, "items": {"type": "object", "additionalProperties": True}},
        },
        "required": ["monthly_visitors", "click_through_rate_pct", "affiliate_conversion_rate_pct", "programs"],
        "additionalProperties": False,
    }
    package = build_skill_package({
        "skill_id": "research/commission-calculator",
        "display_name": "Commission calculator",
        "version": "1.0.0",
        "description": "Estimate affiliate earnings using explicit traffic, conversion and payout assumptions.",
        "stage": "S1",
        "runtime_handler": "research.commission_calculator",
        "capabilities": ["research.read"],
        "input_schema": input_schema,
        "output_schema": {"type": "object", "additionalProperties": True},
        "instructions_markdown": "# Declarative guidance\nTreat projections as assumptions, not actual earnings or guarantees.",
        "test_cases": [{"name": "explicit single-program estimate", "input": input_value, "expected_output": expected}],
    })
    report = package["validation_report"]
    assert report["all_fixtures_passed"] is True
    assert report["runtime_handler_allowlisted"] is True
    assert report["runtime_execution_tested"] is True
    assert report["cases"][0]["runtime_output_matches_expected"] is True


def test_ad_guardrail_review_package_executes_a_real_fixture_and_fails_closed_without_evidence():
    input_value = {
        "policy": {
            "id": "policy-guardrail-1",
            "campaign_plan_id": "plan-1",
            "daily_spend_cap_usd": 30,
            "campaign_spend_cap_usd": 500,
            "minimum_roas": 1.2,
            "maximum_cpa_usd": 35,
            "minimum_verified_impressions": 1000,
            "minimum_verified_clicks": 30,
            "minimum_verified_conversions": 3,
        },
        "observations": [],
        "now": "2026-10-28T18:00:00+00:00",
    }
    expected_output = {
        "policy_id": "policy-guardrail-1",
        "campaign_plan_id": "plan-1",
        "evaluated_at": "2026-10-28T18:00:00+00:00",
        "timezone": "UTC",
        "status": "blocked_pending_provider_verification",
        "reported_observation_count": 0,
        "verified_observation_count": 0,
        "snapshot_observation_count": 0,
        "snapshot_conflicts": [],
        "unverified_observation_count": 0,
        "configured_daily_spend_cap_usd": "30.00",
        "plan_daily_budget_usd": "0.00",
        "effective_daily_spend_cap_usd": "30.00",
        "campaign_spend_cap_usd": "500.00",
        "verified_spend_today_usd": "0.00",
        "verified_campaign_spend_usd": "0.00",
        "minimum_roas": "1.2000",
        "verified_roas": None,
        "maximum_cpa_usd": "35.00",
        "verified_cpa_usd": None,
        "sample_gate": {
            "minimum_verified_impressions": 1000,
            "minimum_verified_clicks": 30,
            "minimum_verified_conversions": 3,
            "actual_verified_impressions": 0,
            "actual_verified_clicks": 0,
            "actual_verified_conversions": 0,
            "passed": False,
        },
        "freshness_gate": {
            "max_age_hours": 24,
            "max_future_skew_minutes": 5,
            "latest_creative_count": 0,
            "stale_creatives": [],
            "future_dated_creatives": [],
            "passed": True,
        },
        "breaches": [],
        "stop_recommended": False,
        "kill_switch_should_engage": False,
        "live_spend_authorized": False,
        "provider_action_executed": False,
        "input_provenance": "caller_supplied_unattested",
        "source_attestation_verified": False,
        "operational_action_permitted": False,
        "hypothetical_review": {
            "basis": "scenario_only_if_inputs_are_independently_attested",
            "status_if_independently_attested": "blocked_pending_provider_verification",
            "potential_breaches_if_independently_attested": [],
            "sample_gate_if_independently_attested": {
                "minimum_verified_impressions": 1000,
                "minimum_verified_clicks": 30,
                "minimum_verified_conversions": 3,
                "actual_verified_impressions": 0,
                "actual_verified_clicks": 0,
                "actual_verified_conversions": 0,
                "passed": False,
            },
            "freshness_gate_if_independently_attested": {
                "max_age_hours": 24,
                "max_future_skew_minutes": 5,
                "latest_creative_count": 0,
                "stale_creatives": [],
                "future_dated_creatives": [],
                "passed": True,
            },
            "spend_metrics_if_independently_attested": {
                "daily_spend_usd": "0.00",
                "campaign_spend_usd": "0.00",
                "roas": None,
                "cpa_usd": None,
            },
            "is_provider_attested": False,
            "provider_action_executed": False,
        },
        "note": (
            "Authoritative status is calculated only from caller-supplied, unattested input and therefore "
            "fails closed. The nested scenario is hypothetical if these values are independently verified; "
            "it is not provider evidence and cannot authorize a live spend, pause or kill-switch action."
        ),
    }
    input_schema = {
        "type": "object",
        "properties": {
            "policy": {"type": "object", "additionalProperties": True},
            "observations": {"type": "array", "items": {"type": "object", "additionalProperties": True}, "maxItems": 1000},
            "now": {"type": "string", "minLength": 20, "maxLength": 64},
        },
        "required": ["policy", "observations", "now"],
        "additionalProperties": False,
    }
    output_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "source_attestation_verified": {"type": "boolean"},
            "operational_action_permitted": {"type": "boolean"},
            "live_spend_authorized": {"type": "boolean"},
            "provider_action_executed": {"type": "boolean"},
            "stop_recommended": {"type": "boolean"},
            "kill_switch_should_engage": {"type": "boolean"},
        },
        "required": [
            "status", "source_attestation_verified", "operational_action_permitted",
            "live_spend_authorized", "provider_action_executed", "stop_recommended",
            "kill_switch_should_engage",
        ],
        "additionalProperties": True,
    }
    package = build_skill_package({
        "skill_id": "ads/guardrail-review",
        "display_name": "Ad budget guardrail review",
        "version": "1.0.0",
        "description": "Fails closed for caller-supplied ad metrics and never mutates an ad account.",
        "stage": "S7",
        "runtime_handler": "ads.guardrail_review",
        "capabilities": ["ads.review"],
        "input_schema": input_schema,
        "output_schema": output_schema,
        "instructions_markdown": "# Review only\nNever convert caller-supplied ad observations into provider-attested evidence.",
        "test_cases": [{
            "name": "empty evidence fails closed",
            "input": input_value,
            "expected_output": expected_output,
        }],
    })
    report = package["validation_report"]
    assert report["all_fixtures_passed"] is True
    assert report["runtime_handler"] == "ads.guardrail_review"
    assert report["runtime_execution_tested"] is True
    assert report["cases"][0]["runtime_output_matches_expected"] is True
    result = execute_skill_handler("ads.guardrail_review", input_value)
    assert result["live_spend_authorized"] is False
    assert result["provider_action_executed"] is False
    assert result["source_attestation_verified"] is False
    assert result["operational_action_permitted"] is False
