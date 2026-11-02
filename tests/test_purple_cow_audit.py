from __future__ import annotations
import pytest
from backend.services.purple_cow_audit import audit_purple_cow_positioning


def test_audit_compares_only_supplied_alternatives_and_exposes_components():
    result = audit_purple_cow_positioning(
        offer_name="Creator video workflow",
        target_audience="independent video creators",
        positioning_statement="A source-linked editing workflow for independent creators",
        alternatives=[
            {"name": "Generic editor", "positioning_statement": "An all-in-one video editor for every creator"},
            {"name": "Fast editor", "positioning_statement": "Edit short clips quickly with simple controls"},
        ],
        evidence_notes=["Product documentation describes source-linked clip references."],
    )
    assert 0 <= result["score"] <= 100
    assert len(result["alternative_comparisons"]) == 2
    assert all("lexical_overlap_score" in item for item in result["alternative_comparisons"])
    assert result["score_components"]["lexical_distinctiveness_vs_supplied_alternatives"] >= 0
    assert result["score_components"]["evidence_readiness"] == 25
    assert result["evidence_status"] == "operator_supplied_not_independently_verified"
    assert result["market_research_performed"] is False
    assert result["publishing_started"] is False
    assert result["requires_review"] is True


def test_audit_flags_unsupported_absolute_and_guarantee_claim_language():
    result = audit_purple_cow_positioning(
        offer_name="Creator editor",
        target_audience="independent creators",
        positioning_statement="The only best editor that guarantees success with no risk",
        alternatives=[{"name": "Other tool", "positioning_statement": "A simple video editing tool"}],
    )
    assert "absolute_superiority_or_exclusivity" in result["risk_flags"]
    assert "guarantee_or_risk_free_language" in result["risk_flags"]
    assert result["risk_penalty"] >= 24
    assert any("Review absolute" in item for item in result["recommendations"])


def test_missing_evidence_is_reported_without_fabricating_proof():
    result = audit_purple_cow_positioning(
        offer_name="Gardening guide", target_audience="beginner home gardeners",
        positioning_statement="A practical container gardening checklist for small homes",
        alternatives=[{"name": "Broad guide", "positioning_statement": "Gardening ideas for everyone"}],
    )
    assert result["score_components"]["evidence_readiness"] is None
    assert result["evidence_status"] == "not_supplied"
    assert any("Add primary-source proof" in item for item in result["recommendations"])


def test_audit_rejects_empty_alternatives_and_vacuous_positioning():
    with pytest.raises(ValueError, match="At least one supplied alternative"):
        audit_purple_cow_positioning(offer_name="An offer",target_audience="a real audience",positioning_statement="A distinctive practical statement",alternatives=[])
    with pytest.raises(ValueError, match="meaningful terms"):
        audit_purple_cow_positioning(offer_name="An offer",target_audience="a real audience",positioning_statement="the and of to",alternatives=[{"name":"Alternative","positioning_statement":"Other words about an offer"}])
