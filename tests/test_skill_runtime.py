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
        "none", "content.extractive_summary", "research.keyword_extract", "analytics.roas_calculator"
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
