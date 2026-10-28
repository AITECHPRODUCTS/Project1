from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.main import app
from backend.schemas import AdBudgetGuardrailCreateRequest
from backend.services.ad_guardrails import evaluate_ad_budget_guardrail


def policy(**overrides):
    base = {
        "id": "guardrail-1", "campaign_plan_id": "plan-1",
        "daily_spend_cap_usd": Decimal("50.00"), "campaign_spend_cap_usd": Decimal("500.00"),
        "minimum_roas": Decimal("1.20"), "maximum_cpa_usd": Decimal("35.00"),
        "minimum_verified_impressions": 1000, "minimum_verified_clicks": 30,
        "minimum_verified_conversions": 3, "kill_switch_engaged": False, "stop_latched": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def observation(*, day, creative="creative-1", platform="meta", spend="10.00", commission="20.00",
                impressions=1000, clicks=50, conversions=4, status="provider_verified", hour=12):
    return SimpleNamespace(
        observed_at=datetime(2026, 10, day, hour, tzinfo=timezone.utc), platform=platform, creative_id=creative,
        spend_usd=Decimal(spend), commission_usd=Decimal(commission), impressions=impressions, clicks=clicks,
        conversions=conversions, evidence_status=status,
    )


def test_guardrail_blocks_empty_and_mixed_unverified_observations():
    now = datetime(2026, 10, 27, 18, tzinfo=timezone.utc)
    empty = evaluate_ad_budget_guardrail(policy=policy(), observations=[], now=now, plan_daily_budget_usd=Decimal("40"))
    assert empty["status"] == "blocked_pending_provider_verification"
    assert empty["live_spend_authorized"] is False
    assert empty["provider_action_executed"] is False
    mixed = evaluate_ad_budget_guardrail(
        policy=policy(),
        observations=[observation(day=27), observation(day=27, creative="unverified", status="operator_supplied_unverified")],
        now=now,
    )
    assert mixed["status"] == "blocked_mixed_evidence"
    assert mixed["breaches"] == []
    assert mixed["kill_switch_should_engage"] is False


def test_guardrail_deduplicates_creative_day_snapshots_and_enforces_lower_daily_budget():
    now = datetime(2026, 10, 27, 18, tzinfo=timezone.utc)
    result = evaluate_ad_budget_guardrail(
        policy=policy(daily_spend_cap_usd=Decimal("80.00"), campaign_spend_cap_usd=Decimal("800.00"),
                      maximum_cpa_usd=None, minimum_roas=Decimal("0")),
        observations=[
            observation(day=27, spend="20.00", commission="0.00", hour=10),
            observation(day=27, spend="35.00", commission="0.00", hour=16),
        ],
        now=now, plan_daily_budget_usd=Decimal("30.00"),
    )
    assert result["snapshot_observation_count"] == 1
    assert result["verified_spend_today_usd"] == "35.00"
    assert result["effective_daily_spend_cap_usd"] == "30.00"
    assert result["status"] == "triggered_stop"
    assert result["breaches"][0]["code"] == "daily_spend_cap_reached"


def test_guardrail_blocks_stale_latest_provider_observation_but_keeps_history_for_fresh_creative():
    now = datetime(2026, 10, 28, 18, tzinfo=timezone.utc)
    stale = evaluate_ad_budget_guardrail(
        policy=policy(),
        observations=[observation(day=26, spend="25.00", commission="0.00")],
        now=now,
    )
    assert stale["status"] == "blocked_stale_provider_evidence"
    assert stale["freshness_gate"]["passed"] is False
    assert stale["freshness_gate"]["stale_creatives"][0]["creative_id"] == "creative-1"
    assert stale["breaches"] == []
    assert stale["kill_switch_should_engage"] is False
    assert stale["provider_action_executed"] is False

    # Older daily snapshots still feed campaign totals when the same creative
    # has a fresh latest observation; freshness applies to the latest point.
    fresh = evaluate_ad_budget_guardrail(
        policy=policy(minimum_roas=Decimal("0"), maximum_cpa_usd=None),
        observations=[
            observation(day=25, spend="10.00", commission="20.00"),
            observation(day=28, spend="12.00", commission="24.00", hour=17),
        ],
        now=now,
    )
    assert fresh["status"] == "monitoring"
    assert fresh["freshness_gate"]["passed"] is True
    assert fresh["verified_campaign_spend_usd"] == "22.00"


def test_guardrail_blocks_materially_future_dated_provider_observations():
    now = datetime(2026, 10, 27, 18, tzinfo=timezone.utc)
    future = observation(day=28, spend="30.00")
    result = evaluate_ad_budget_guardrail(policy=policy(), observations=[future], now=now)
    assert result["status"] == "blocked_future_provider_evidence"
    assert result["freshness_gate"]["passed"] is False
    assert result["freshness_gate"]["future_dated_creatives"][0]["creative_id"] == "creative-1"
    assert result["breaches"] == []
    assert result["kill_switch_should_engage"] is False


def test_guardrail_campaign_cap_roas_and_cpa_breaches_are_explicit():
    now = datetime(2026, 10, 27, 18, tzinfo=timezone.utc)
    result = evaluate_ad_budget_guardrail(
        policy=policy(campaign_spend_cap_usd=Decimal("20.00"), daily_spend_cap_usd=Decimal("100.00"),
                      minimum_roas=Decimal("1.5"), maximum_cpa_usd=Decimal("2.00")),
        observations=[observation(day=27, spend="25.00", commission="10.00", conversions=4)],
        now=now, plan_daily_budget_usd=Decimal("100.00"),
    )
    codes = {item["code"] for item in result["breaches"]}
    assert result["status"] == "triggered_stop"
    assert {"campaign_spend_cap_reached", "minimum_roas_breach", "maximum_cpa_breach"} <= codes
    assert result["kill_switch_should_engage"] is True
    assert result["provider_action_executed"] is False
    assert result["live_spend_authorized"] is False


def test_guardrail_request_validates_caps_and_sample_thresholds():
    with pytest.raises(ValidationError):
        AdBudgetGuardrailCreateRequest(daily_spend_cap_usd="0", campaign_spend_cap_usd="100")
    with pytest.raises(ValidationError):
        AdBudgetGuardrailCreateRequest(daily_spend_cap_usd="100", campaign_spend_cap_usd="99")


def test_guardrail_api_persists_policy_and_manual_kill_switch_latch():
    plan_payload = {
        "campaign_name": "Guardrail API test campaign", "niche": "creator tools",
        "audience": "independent content creators", "region": "US", "objective": "sales",
        "platforms": ["meta"], "variants_per_platform": 1, "daily_budget_usd": "40.00",
        "affiliate_disclosure": "Affiliate disclosure: I may earn a commission.",
    }
    with TestClient(app) as client:
        plan_response = client.post("/api/ads/plan", json=plan_payload)
        assert plan_response.status_code == 201, plan_response.text
        plan_id = plan_response.json()["plan_id"]
        policy_response = client.post(f"/api/ads/plans/{plan_id}/guardrails", json={
            "daily_spend_cap_usd": "35.00", "campaign_spend_cap_usd": "500.00",
            "minimum_roas": "1.20", "maximum_cpa_usd": "30.00",
        })
        assert policy_response.status_code == 201, policy_response.text
        guardrail = policy_response.json()
        assert guardrail["live_spend_authorized"] is False
        assert guardrail["kill_switch_engaged"] is False
        assert guardrail["campaign_plan_id"] == plan_id
        duplicate = client.post(f"/api/ads/plans/{plan_id}/guardrails", json={
            "daily_spend_cap_usd": "35.00", "campaign_spend_cap_usd": "500.00",
        })
        assert duplicate.status_code == 409, duplicate.text
        evaluated = client.post(f"/api/ads/guardrails/{guardrail['id']}/evaluate")
        assert evaluated.status_code == 200, evaluated.text
        assert evaluated.json()["evaluation"]["status"] == "blocked_pending_provider_verification"
        tripped = client.post(f"/api/ads/guardrails/{guardrail['id']}/kill-switch")
        assert tripped.status_code == 200, tripped.text
        assert tripped.json()["kill_switch_engaged"] is True
        assert tripped.json()["stop_latched"] is True
        assert tripped.json()["live_spend_authorized"] is False
        unsafe_reset = client.post(f"/api/ads/guardrails/{guardrail['id']}/reset", json={
            "confirm_reset": True, "reason": "Reset after looking at the latest unverified report.",
        })
        assert unsafe_reset.status_code == 409, unsafe_reset.text
