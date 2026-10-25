from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from backend.main import app
from backend.schemas import AdPerformanceObservationRequest


def test_observation_request_rejects_negative_money_and_unsafe_source_urls():
    with pytest.raises(ValidationError):
        AdPerformanceObservationRequest(
            platform="meta",
            creative_id="meta-01",
            spend_usd="-0.01",
            commission_usd="0.00",
        )
    with pytest.raises(ValidationError):
        AdPerformanceObservationRequest(
            platform="meta",
            creative_id="meta-01",
            source_reference_url="javascript:alert(1)",
        )


def test_reported_ad_metrics_are_persisted_but_not_treated_as_verified():
    payload = {
        "platform": "meta",
        "creative_id": "test-creative-reported-metrics",
        "source_type": "provider_export",
        "source_reference_url": "https://reports.example/campaigns/123",
        "impressions": 1000,
        "clicks": 42,
        "conversions": 3,
        "spend_usd": "10.00",
        "commission_usd": "25.00",
        "currency": "usd",
        "note": "Imported report for QA",
    }

    with TestClient(app) as client:
        created = client.post("/api/ads/observations", json=payload)
        assert created.status_code == 201, created.text
        row = created.json()
        assert row["evidence_status"] == "operator_supplied_unverified"
        assert row["currency"] == "USD"
        assert row["spend_usd"] == "10.00"
        assert row["external_actions_executed"] is False
        assert row["optimization_eligible"] is False

        listing = client.get("/api/ads/observations?limit=50")
        assert listing.status_code == 200, listing.text
        assert any(item["id"] == row["id"] for item in listing.json()["data"])

        performance = client.get("/api/ads/performance?limit=50")
        assert performance.status_code == 200, performance.text
        summary = next(
            item for item in performance.json()["items"]
            if item["creative_id"] == "test-creative-reported-metrics"
        )
        assert summary["reported_metrics_unverified"]["impressions"] == 1000
        assert summary["reported_metrics_unverified"]["clicks"] == 42
        assert summary["reported_metrics_unverified"]["spend_usd"] == "10.00"
        assert summary["reported_metrics_unverified"]["commission_to_spend_ratio"] == 2.5
        assert summary["verified_metrics"] is None
        assert summary["optimization"]["eligible"] is False
        assert summary["optimization"]["automatic_action_executed"] is False


def test_ad_observation_links_must_reference_a_plan_in_the_active_workspace():
    payload = {
        "campaign_plan_id": "missing-plan",
        "platform": "meta",
        "creative_id": "meta-01",
        "spend_usd": "0.00",
        "commission_usd": "0.00",
    }
    with TestClient(app) as client:
        response = client.post("/api/ads/observations", json=payload)
        assert response.status_code == 404


from datetime import datetime, timezone
from types import SimpleNamespace

from backend.services.ad_performance import summarize_ad_performance


def observation(*, day, impressions, clicks, conversions, spend, commission, evidence_status="provider_verified", plan_id="verified-plan", platform="meta", creative_id="verified-creative"):
    return SimpleNamespace(
        campaign_plan_id=plan_id,
        platform=platform,
        creative_id=creative_id,
        impressions=impressions,
        clicks=clicks,
        conversions=conversions,
        spend_usd=spend,
        commission_usd=commission,
        evidence_status=evidence_status,
        observed_at=datetime(2026, 10, day, tzinfo=timezone.utc),
    )


def test_verified_ad_optimization_has_sample_gates_and_never_executes_remote_actions():
    small = summarize_ad_performance([
        observation(day=20, impressions=250, clicks=8, conversions=1, spend="25.00", commission="0.00")
    ])[0]
    assert small["optimization"]["status"] == "blocked_insufficient_verified_sample"
    assert small["optimization"]["pause_recommended"] is False
    assert small["optimization"]["scale_review_recommended"] is False
    assert small["optimization"]["automatic_action_executed"] is False

    losing = summarize_ad_performance([
        observation(day=20, impressions=2500, clicks=100, conversions=0, spend="150.00", commission="0.00")
    ])[0]
    assert losing["optimization"]["status"] == "stop_loss_review_recommended"
    assert losing["optimization"]["pause_recommended"] is True
    assert losing["optimization"]["requires_human_approval"] is True
    assert losing["optimization"]["sample_gate"]["passed"] is True
    assert losing["optimization"]["automatic_action_executed"] is False


def test_scale_review_requires_verified_roas_cushion_and_conversion_sample():
    result = summarize_ad_performance([
        observation(day=20, impressions=8000, clicks=400, conversions=12, spend="100.00", commission="200.00")
    ])[0]
    assert result["optimization"]["status"] == "scale_review_recommended"
    assert result["optimization"]["scale_review_recommended"] is True
    assert result["optimization"]["automatic_action_executed"] is False
    assert result["optimization"]["requires_human_approval"] is True


def test_creative_fatigue_signal_uses_verified_time_series_and_review_only_output():
    rows = [
        observation(day=1, impressions=1000, clicks=100, conversions=5, spend="10.00", commission="15.00"),
        observation(day=2, impressions=1000, clicks=100, conversions=5, spend="10.00", commission="15.00"),
        observation(day=3, impressions=1000, clicks=50, conversions=2, spend="10.00", commission="10.00"),
        observation(day=4, impressions=1000, clicks=50, conversions=2, spend="10.00", commission="10.00"),
    ]
    result = summarize_ad_performance(rows)[0]
    fatigue = result["creative_fatigue"]
    assert fatigue["status"] == "review_signal_detected"
    assert fatigue["review_recommended"] is True
    assert fatigue["decline_percentage"] == 50.0
    assert fatigue["automatic_action_executed"] is False


def test_creative_fatigue_and_optimization_stay_blocked_for_unverified_reports():
    rows = [
        observation(day=1, impressions=1000, clicks=100, conversions=4, spend="10.00", commission="15.00", evidence_status="operator_supplied_unverified"),
        observation(day=2, impressions=1000, clicks=90, conversions=4, spend="10.00", commission="15.00", evidence_status="operator_supplied_unverified"),
        observation(day=3, impressions=1000, clicks=40, conversions=1, spend="10.00", commission="0.00", evidence_status="operator_supplied_unverified"),
        observation(day=4, impressions=1000, clicks=40, conversions=1, spend="10.00", commission="0.00", evidence_status="operator_supplied_unverified"),
    ]
    result = summarize_ad_performance(rows)[0]
    assert result["optimization"]["eligible"] is False
    assert result["optimization"]["pause_recommended"] is False
    assert result["optimization"]["scale_review_recommended"] is False
    assert result["creative_fatigue"]["status"] == "blocked_unverified_or_mixed_evidence"
    assert result["creative_fatigue"]["review_recommended"] is False

