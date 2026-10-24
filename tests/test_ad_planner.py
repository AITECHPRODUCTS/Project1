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
