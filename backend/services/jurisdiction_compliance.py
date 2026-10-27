from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from backend.models import JurisdictionComplianceAssessment


REQUIRED_RULE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "affiliate_promotion": ("affiliate_disclosure", "advertising_claims", "platform_terms"),
    "content_publish": ("affiliate_disclosure", "advertising_claims", "platform_terms", "privacy_data_protection"),
    "paid_media": ("affiliate_disclosure", "advertising_claims", "paid_media_rules", "privacy_data_protection", "platform_terms"),
    "email_marketing": ("affiliate_disclosure", "email_marketing", "privacy_data_protection", "consent_and_marketing"),
    "lead_capture": ("privacy_data_protection", "consent_and_marketing", "data_retention"),
    "tracking_analytics": ("privacy_data_protection", "cookie_tracking", "data_retention"),
    "merchant_marketplace": ("affiliate_disclosure", "advertising_claims", "platform_terms", "consumer_protection"),
}
FAST_CHANGING_ACTIVITIES = {"paid_media", "email_marketing", "tracking_analytics", "lead_capture"}
DEFAULT_EVIDENCE_MAX_AGE_DAYS = 365
FAST_EVIDENCE_MAX_AGE_DAYS = 180
ASSESSMENT_VALIDITY_DAYS = 180


def normalize_jurisdictions(values: list[str]) -> list[str]:
    normalized = list(dict.fromkeys(str(value).strip().upper() for value in values if str(value).strip()))
    if not normalized or any(not re.fullmatch(r"(?:[A-Z]{2}(?:-[A-Z0-9]{1,6})?|EU|EEA|GLOBAL)", value) for value in normalized):
        raise ValueError("Target jurisdictions must use ISO-style country/subdivision codes or EU, EEA, GLOBAL")
    return normalized


def required_categories(activity: str) -> list[str]:
    if activity not in REQUIRED_RULE_CATEGORIES:
        raise ValueError("Unsupported compliance activity")
    return list(REQUIRED_RULE_CATEGORIES[activity])


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        candidate = value
    elif isinstance(value, str):
        try:
            candidate = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if candidate.tzinfo is None or candidate.utcoffset() is None:
        candidate = candidate.replace(tzinfo=timezone.utc)
    return candidate.astimezone(timezone.utc)


def evidence_coverage(
    activity: str,
    jurisdictions: list[str],
    evidence: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    required = required_categories(activity)
    max_age = FAST_EVIDENCE_MAX_AGE_DAYS if activity in FAST_CHANGING_ACTIVITIES else DEFAULT_EVIDENCE_MAX_AGE_DAYS
    cutoff = current - timedelta(days=max_age)
    normalized_evidence: list[dict[str, Any]] = [row for row in evidence if isinstance(row, dict)]
    missing: list[dict[str, str]] = []
    covered_count = 0
    required_count = len(jurisdictions) * len(required)

    for jurisdiction in jurisdictions:
        for category in required:
            matching = [
                item for item in normalized_evidence
                if str(item.get("jurisdiction_code") or "").strip().upper() == jurisdiction
                and str(item.get("category") or "").strip() == category
                and item.get("reviewer_attestation") is True
                and str(item.get("source_url") or "").strip().startswith("https://")
                and len(str(item.get("rule_summary") or "").strip()) >= 20
                and len(str(item.get("source_title") or "").strip()) >= 3
            ]
            valid = False
            saw_stale = False
            for item in matching:
                reviewed_at = _as_datetime(item.get("reviewed_at"))
                if reviewed_at is None or reviewed_at > current:
                    continue
                if reviewed_at < cutoff:
                    saw_stale = True
                    continue
                valid = True
                break
            if valid:
                covered_count += 1
            else:
                missing.append({
                    "jurisdiction_code": jurisdiction,
                    "category": category,
                    "reason": "stale_evidence" if saw_stale else "missing_or_unattested_evidence",
                })

    return {
        "activity": activity,
        "jurisdictions": jurisdictions,
        "required_categories": required,
        "required_evidence_items": required_count,
        "covered_evidence_items": covered_count,
        "coverage_complete": not missing,
        "missing_evidence": missing,
        "evidence_max_age_days": max_age,
    }


def assessment_is_current(
    assessment: JurisdictionComplianceAssessment,
    *,
    activity: str,
    jurisdictions: list[str],
    channel: str,
    now: datetime | None = None,
) -> tuple[bool, dict[str, Any]]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    scope_jurisdictions = set(str(item).upper() for item in (assessment.jurisdictions_json or []))
    scope_channels = set(str(item).lower() for item in (assessment.channels_json or []))
    valid_until = _as_datetime(assessment.valid_until)
    reviewed_at = _as_datetime(assessment.reviewed_at)
    reason = None
    if assessment.status != "approved":
        reason = "assessment_not_approved"
    elif assessment.activity != activity:
        reason = "activity_mismatch"
    elif not set(jurisdictions).issubset(scope_jurisdictions):
        reason = "jurisdiction_scope_mismatch"
    elif channel.lower() not in scope_channels:
        reason = "channel_scope_mismatch"
    elif valid_until is None or valid_until <= current:
        reason = "approval_expired"
    elif reviewed_at is None or reviewed_at > current:
        reason = "review_timestamp_invalid"

    coverage = evidence_coverage(
        activity,
        jurisdictions,
        list(assessment.rule_evidence_json or []),
        now=current,
    )
    if not coverage["coverage_complete"]:
        reason = "evidence_incomplete_or_stale"
    return reason is None, {**coverage, "reason": reason, "assessment_id": assessment.id}


async def find_current_assessment(
    db,
    *,
    workspace_id: str,
    activity: str,
    jurisdictions: list[str],
    channel: str,
    now: datetime | None = None,
) -> JurisdictionComplianceAssessment | None:
    normalized = normalize_jurisdictions(jurisdictions)
    rows = list((await db.scalars(
        select(JurisdictionComplianceAssessment)
        .where(
            JurisdictionComplianceAssessment.workspace_id == str(workspace_id),
            JurisdictionComplianceAssessment.activity == activity,
            JurisdictionComplianceAssessment.status == "approved",
        )
        .order_by(JurisdictionComplianceAssessment.reviewed_at.desc())
        .limit(100)
    )).all())
    for assessment in rows:
        approved, _ = assessment_is_current(
            assessment,
            activity=activity,
            jurisdictions=normalized,
            channel=channel,
            now=now,
        )
        if approved:
            return assessment
    return None
