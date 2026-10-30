from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.schemas import (
    JurisdictionComplianceAssessmentCreateRequest,
    JurisdictionComplianceAssessmentReviewRequest,
    JurisdictionComplianceRuleEvidence,
)


def _evidence(**overrides):
    value = {
        "jurisdiction_code": "us",
        "category": "affiliate_disclosure",
        "source_title": "Official affiliate disclosure guidance",
        "source_url": "https://authority.example/rules/affiliate",
        "rule_summary": "Reviewed the source and recorded how the rule applies to the stated activity.",
        "effective_date": None,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewer_attestation": True,
    }
    value.update(overrides)
    return value


def test_assessment_schema_normalizes_scope_and_retains_unverified_draft_state():
    request = JurisdictionComplianceAssessmentCreateRequest(
        activity="content_publish",
        channels=["WordPress", "reddit", "wordpress"],
        jurisdictions=["us", "GB", "US"],
        rule_evidence=[_evidence()],
        operator_notes=" Scope reviewed by operator ",
    )
    assert request.channels == ["wordpress", "reddit"]
    assert request.jurisdictions == ["US", "GB"]
    assert request.rule_evidence[0].jurisdiction_code == "US"
    assert request.operator_notes == "Scope reviewed by operator"


def test_assessment_allows_empty_evidence_for_draft_but_not_approval_by_default():
    request = JurisdictionComplianceAssessmentCreateRequest(
        activity="lead_capture",
        channels=["web"],
        jurisdictions=["IN"],
        rule_evidence=[],
    )
    assert request.rule_evidence == []
    review = JurisdictionComplianceAssessmentReviewRequest(decision="approve")
    assert review.confirm_scope_reviewed is False


@pytest.mark.parametrize(
    "source_url",
    [
        "http://authority.example/rules",
        "https://user:password@authority.example/rules",
        "https://127.0.0.1/private",
        "https://localhost/private",
    ],
)
def test_evidence_source_must_be_public_https_without_credentials(source_url):
    with pytest.raises(ValidationError):
        JurisdictionComplianceRuleEvidence(**_evidence(source_url=source_url))


def test_evidence_review_timestamp_must_include_timezone():
    with pytest.raises(ValidationError):
        JurisdictionComplianceRuleEvidence(**_evidence(reviewed_at="2026-10-27T09:30:00"))


def test_assessment_rejects_unsupported_activity_and_invalid_jurisdiction():
    with pytest.raises(ValidationError):
        JurisdictionComplianceAssessmentCreateRequest(
            activity="guess_the_law",
            channels=["wordpress"],
            jurisdictions=["US"],
        )
    with pytest.raises(ValidationError):
        JurisdictionComplianceAssessmentCreateRequest(
            activity="content_publish",
            channels=["wordpress"],
            jurisdictions=["Not-A-Country"],
        )
