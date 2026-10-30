from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.schemas import AdCampaignPlanRequest
from backend.services.ad_planner import build_ad_campaign_plan


def request(**overrides):
    data = {
        "niche": "creator video editing",
        "audience": "independent creators",
        "region": "US",
        "objective": "leads",
        "platforms": ["meta", "google_search", "tiktok"],
        "daily_budget_usd": Decimal("10.00"),
        "affiliate_disclosure": "Disclosure: I may earn a commission from qualifying purchases.",
        "evidence_urls": ["https://vendor.example/features"],
        "landing_page_url": "https://publisher.example/guide",
    }
    data.update(overrides)
    return AdCampaignPlanRequest(**data)


def test_ad_plan_creates_platform_specific_draft_variants_without_external_actions():
    plan = build_ad_campaign_plan(request(variants_per_platform=3))

    assert len(plan["platform_plans"]) == 3
    assert all(len(platform["creatives"]) == 3 for platform in plan["platform_plans"])
    assert {x["platform"] for x in plan["platform_plans"]} == {"meta", "google_search", "tiktok"}
    assert all(x["provider_write_access_verified"] is False for x in plan["platform_plans"])
    assert all(x["external_actions_executed"] is False for x in plan["platform_plans"])
    for platform in plan["platform_plans"]:
        for creative in platform["creatives"]:
            assert creative["publish_authorized"] is False
            assert creative["disclosure_included"] is True
            assert "commission" in creative["primary_text"].lower() or "affiliate" in creative["primary_text"].lower()
    assert plan["publishing_authorized"] is False
    assert plan["spend_authorized"] is False
    assert plan["external_actions_executed"] is False


def test_ad_plan_budget_split_preserves_cents_without_claiming_optimization():
    plan = build_ad_campaign_plan(
        request(platforms=["meta", "google_search", "tiktok"], daily_budget_usd=Decimal("10.00"))
    )
    allocations = plan["budget_plan"]["platform_allocations"]
    assert [x["daily_budget_usd"] for x in allocations] == ["3.34", "3.33", "3.33"]
    assert sum(Decimal(x["daily_budget_usd"]) for x in allocations) == Decimal("10.00")
    assert plan["budget_plan"]["allocation_method"] == "equal_exploratory_split_no_performance_data"
    assert plan["budget_plan"]["spend_authorized"] is False


def test_ad_plan_does_not_fabricate_kpi_forecasts():
    plan = build_ad_campaign_plan(request())
    forecast = plan["performance_forecast"]

    assert forecast["status"] == "unavailable_without_verified_campaign_data"
    assert all(forecast[key] is None for key in ("ctr", "cpc_usd", "cpm_usd", "conversion_rate", "cpa_usd", "roas"))


def test_operator_product_facts_remain_unverified_until_reviewed():
    plan = build_ad_campaign_plan(
        request(
            product_name="Creator Toolkit",
            product_summary="A short user-supplied product description",
            product_facts_for_review=["Saves time in video editing"],
        )
    )

    assert plan["product_facts_for_review"] == [
        {"text": "Saves time in video editing", "status": "operator_supplied_unverified"}
    ]
    assert plan["compliance"]["product_facts_verified"] is False
    assert plan["landing_page"]["coherence_check_passed"] is False


def test_ad_plan_has_no_sensitive_attribute_targeting():
    plan = build_ad_campaign_plan(request())
    assert all(segment["sensitive_attribute_targeting"] is False for segment in plan["audience_segments"])


def test_ad_request_rejects_unsupported_platform_and_invalid_urls():
    with pytest.raises(ValidationError):
        request(platforms=["unknown_social_network"])
    with pytest.raises(ValidationError):
        request(evidence_urls=["file:///etc/passwd"])
    with pytest.raises(ValidationError):
        request(landing_page_url="javascript:alert(1)")


def test_ad_request_requires_affiliate_disclosure():
    with pytest.raises(ValidationError):
        request(affiliate_disclosure="Buy today")

def test_ad_plan_adds_platform_specific_targeting_hypotheses_and_guardrails():
    plan = build_ad_campaign_plan(request(
        platforms=["google_search", "meta", "linkedin", "reddit"],
        daily_budget_usd=Decimal("12.01"),
    ))
    by_platform = {item["platform"]: item for item in plan["platform_plans"]}
    assert set(by_platform) == {"google_search", "meta", "linkedin", "reddit"}
    assert "query intent" in by_platform["google_search"]["targeting_plan"]["strategy"].lower()
    assert "community" in by_platform["reddit"]["targeting_plan"]["strategy"].lower()
    assert "professional" in by_platform["linkedin"]["targeting_plan"]["strategy"].lower()
    for item in by_platform.values():
        target = item["targeting_plan"]
        assert target["framework"] == "platform_targeting_hypotheses_v1"
        assert target["platform_feature_availability"] == "not_checked"
        assert len(target["recommended_signals"]) >= 3
        assert len(target["audience_tests"]) == 3
        assert target["requires_policy_review"] is True
        assert target["requires_measurement_review"] is True
        assert target["external_actions_executed"] is False
        assert target["optimization"]["auto_pause_enabled"] is False
        assert target["optimization"]["auto_scale_enabled"] is False
        assert all(row["spend_authorized"] is False for row in target["audience_tests"])
        assert all(row["primary_measurement_event_hypothesis"] == "qualified_lead" for row in target["audience_tests"])
        assert all(row["availability_status"] == "not_checked" for row in target["recommended_signals"])
        assert any("sensitive personal traits" in item for item in target["guardrails"])
    for item in plan["platform_plans"]:
        target_tests = item["targeting_plan"]["audience_tests"]
        platform_budget = Decimal(next(row["daily_budget_usd"] for row in plan["budget_plan"]["platform_allocations"] if row["platform"] == item["platform"]))
        assert sum(Decimal(row["suggested_daily_budget_usd"]) for row in target_tests) == platform_budget


def test_ad_targeting_budget_is_not_fabricated_when_budget_is_unset():
    plan = build_ad_campaign_plan(request(daily_budget_usd=Decimal("0.00")))
    for item in plan["platform_plans"]:
        tests = item["targeting_plan"]["audience_tests"]
        assert all(row["suggested_daily_budget_usd"] is None for row in tests)
        assert all(row["budget_status"] == "budget_not_set" for row in tests)
        assert all(row["spend_authorized"] is False for row in tests)

