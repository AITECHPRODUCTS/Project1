from __future__ import annotations

import pytest

from backend.services.content_angle_ranker import rank_content_angles


def test_ranks_topic_and_audience_relevant_angles_ahead_of_generic_angles():
    result = rank_content_angles(
        topic="beginner sourdough baking",
        audience="first-time home bakers",
        candidates=[
            {
                "angle": "Sourdough starter troubleshooting for beginner home bakers",
                "description": "Practical feeding and temperature checks for sourdough baking.",
                "evidence_facts": [
                    "Sourdough starters need regular feeding.",
                    "Temperature changes starter activity.",
                ],
            },
            {
                "angle": "General growth tips for software founders",
                "description": "Broad business advice and productivity.",
                "evidence_facts": [],
            },
        ],
    )

    assert result["results"][0]["rank"] == 1
    assert "sourdough" in result["results"][0]["angle"].lower()
    assert result["results"][0]["score"] > result["results"][1]["score"]
    assert result["results"][0]["score_components"]["topic_relevance"] >= 60
    assert result["forecast"] == {
        "estimated_ctr": None,
        "estimated_conversion_rate": None,
        "estimated_revenue": None,
        "estimated_profit": None,
    }
    assert result["publishing_started"] is False
    assert result["requires_review"] is True


def test_operator_evidence_notes_affect_score_but_remain_unverified():
    base = {
        "angle": "Sourdough starter feeding for beginner bakers",
        "description": "A checklist for everyday starter care.",
    }
    without_notes = rank_content_angles(
        topic="sourdough starter feeding",
        audience="beginner bakers",
        candidates=[base],
    )["results"][0]
    with_notes = rank_content_angles(
        topic="sourdough starter feeding",
        audience="beginner bakers",
        candidates=[{**base, "evidence_facts": ["Feed the starter on a regular schedule."]}],
    )["results"][0]

    assert with_notes["score_components"]["evidence_support"] > 0
    assert with_notes["score"] > without_notes["score"]
    assert with_notes["evidence_status"] == "operator_supplied_not_independently_verified"
    assert "operator_evidence_notes_present_unverified" in with_notes["reasons"]


def test_flags_risky_claim_language_and_deducts_from_heuristic_score():
    risky = rank_content_angles(
        topic="beginner sourdough baking",
        audience="home bakers",
        candidates=[
            {"angle": "Sourdough starter care for home bakers", "description": "Step-by-step guide."},
            {
                "angle": "Sourdough starter care guarantees to earn $5000 overnight with no risk",
                "description": "For home bakers.",
            },
        ],
    )["results"]
    by_angle = {item["angle"]: item for item in risky}
    clean = by_angle["Sourdough starter care for home bakers"]
    risky_item = by_angle["Sourdough starter care guarantees to earn $5000 overnight with no risk"]

    assert "guarantee_or_risk_free_language" in risky_item["risk_flags"]
    assert "specific_earnings_claim" in risky_item["risk_flags"]
    assert "potentially_high_risk_claim_language" in risky_item["reasons"]
    assert risky_item["score_components"]["risk_penalty"] >= 24
    assert risky_item["score"] < clean["score"]


def test_missing_audience_is_reported_instead_of_fabricating_fit():
    result = rank_content_angles(
        topic="home gardening",
        audience="",
        candidates=[{"angle": "Container gardening for small apartments"}],
    )

    assert result["results"][0]["score_components"]["audience_alignment"] is None
    assert "audience_not_provided" in result["results"][0]["reasons"]


def test_rejects_empty_candidates_and_topic_without_meaningful_terms():
    with pytest.raises(ValueError, match="At least one candidate"):
        rank_content_angles(topic="home gardening", audience="", candidates=[])
    with pytest.raises(ValueError, match="meaningful keyword"):
        rank_content_angles(topic="the and is", audience="", candidates=[{"angle": "Gardening tips"}])
    with pytest.raises(ValueError, match="five non-whitespace"):
        rank_content_angles(topic="home gardening", audience="", candidates=[{"angle": "ok"}])
