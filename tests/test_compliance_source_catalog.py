from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.services.compliance_source_catalog import get_compliance_source_catalog


@pytest.mark.parametrize("jurisdiction", ["US", "GB", "IN", "CA", "AU", "EU"])
def test_catalog_has_jurisdiction_scoped_starters_for_supported_coverage(jurisdiction):
    result = get_compliance_source_catalog(jurisdiction=jurisdiction, activity="content_publish")
    assert result["filters"]["jurisdiction"] == jurisdiction
    assert result["count"] > 0
    assert any(source["scope_match"] == "exact" for source in result["data"])
    assert all(source["legal_approval_granted"] is False for source in result["data"])
    assert all(source["review_required"] is True for source in result["data"])
    assert all(source["jurisdiction_code"] in {jurisdiction, "GLOBAL"} for source in result["data"])


def test_global_platform_policy_is_supplemental_and_never_relabelled_as_national_evidence():
    result = get_compliance_source_catalog(
        jurisdiction="US", category="platform_terms", activity="paid_media"
    )
    global_sources = [source for source in result["data"] if source["jurisdiction_code"] == "GLOBAL"]
    assert global_sources
    assert all(source["scope_match"] == "supplemental_global" for source in global_sources)
    assert any(source["source_id"] == "global-meta-ad-standards" for source in global_sources)
    assert all(source["legal_approval_granted"] is False for source in global_sources)


def test_catalog_channel_filter_is_applied_to_platform_policy_entries():
    result = get_compliance_source_catalog(
        jurisdiction="US", category="platform_terms", activity="paid_media", channel="google_ads"
    )
    assert result["data"]
    assert any(item["source_id"] == "global-google-misrepresentation" for item in result["data"])
    assert not any(item["source_id"] == "global-meta-ad-standards" for item in result["data"])


def test_catalog_does_not_let_an_unrelated_category_be_used_for_an_activity():
    with pytest.raises(ValueError, match="not required"):
        get_compliance_source_catalog(
            jurisdiction="US", category="cookie_tracking", activity="content_publish"
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"jurisdiction": "not a country"},
        {"jurisdiction": "US", "activity": "unknown_activity"},
        {"jurisdiction": "US", "category": "invented_category"},
        {"jurisdiction": "US", "activity": "content_publish", "category": "affiliate_disclosure", "channel": "bad channel"},
    ],
)
def test_catalog_rejects_invalid_filters(kwargs):
    with pytest.raises(ValueError):
        get_compliance_source_catalog(**kwargs)


def test_catalog_api_requires_admin_and_returns_clear_nonapproval_notice(monkeypatch):
    async def admin():
        return {
            "email": "catalog-reviewer@example.invalid",
            "user_id": "catalog-reviewer",
            "workspace_id": "catalog-workspace",
            "workspace_role": "owner",
            "is_admin": True,
        }

    monkeypatch.setitem(main.app.dependency_overrides, main.require_admin, admin)
    try:
        with TestClient(main.app) as client:
            response = client.get(
                "/api/compliance/source-catalog",
                params={"jurisdiction": "GB", "activity": "content_publish", "category": "affiliate_disclosure"},
            )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["count"] > 0
        assert any(item["source_id"] == "gb-cap-section-2" for item in payload["data"])
        assert all(item["legal_approval_granted"] is False for item in payload["data"])
        assert "does not create evidence" in payload["notice"]
    finally:
        main.app.dependency_overrides.pop(main.require_admin, None)


def test_catalog_api_rejects_category_that_is_not_required_for_activity(monkeypatch):
    async def admin():
        return {"email": "reviewer@example.invalid", "workspace_id": "catalog-workspace", "is_admin": True}

    monkeypatch.setitem(main.app.dependency_overrides, main.require_admin, admin)
    try:
        with TestClient(main.app) as client:
            response = client.get(
                "/api/compliance/source-catalog",
                params={"jurisdiction": "GB", "activity": "content_publish", "category": "cookie_tracking"},
            )
        assert response.status_code == 422
    finally:
        main.app.dependency_overrides.pop(main.require_admin, None)
