from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main
from backend.schemas import ContentDecayRequest
from backend.services.content_decay_detector import build_content_decay_report


def test_prioritizes_independently_supported_decay_signals_and_actions():
    report = build_content_decay_report(
        site_url="https://example.com",
        timeframe="90d",
        today=date(2026, 10, 25),
        pages=[{
            "url": "https://example.com/best-tools",
            "title": "Best tools",
            "previous_clicks": 1000,
            "current_clicks": 650,
            "previous_impressions": 12000,
            "current_impressions": 9000,
            "previous_avg_position": 4.0,
            "current_avg_position": 13.0,
            "revenue_impact": "high",
            "contains_affiliate_links": True,
            "outdated_elements": ["2024 pricing needs verification"],
            "competitor_refresh_observed": True,
            "serp_displacement_observed": True,
            "refresh_effort_hours": 1,
        }],
    )
    page = report["decaying_pages"][0]
    assert page["priority"] == "P0-critical"
    assert page["priority_score"] == 100.0
    assert page["metrics"]["clicks_decline_pct"] == 35.0
    assert page["metrics"]["impressions_decline_pct"] == 25.0
    assert page["metrics"]["position_worsening"] == 9.0
    assert "outdated_information_reported" in page["decay_signals"]
    assert any("authoritative sources" in action for action in page["refresh_actions"])
    assert report["pages_decaying"] == 1
    assert report["total_refresh_effort_hours"] == 1.0
    assert report["traffic_recovery_estimate_supported"] is False
    assert report["search_console_connected"] is False
    assert report["competitor_data_checked"] is False
    assert report["publishing_started"] is False


def test_stable_matched_metrics_are_not_suggested_for_refresh():
    report = build_content_decay_report(
        site_url="https://example.com",
        timeframe="30d",
        today=date(2026, 10, 25),
        pages=[{
            "url": "https://example.com/stable",
            "previous_clicks": 500,
            "current_clicks": 520,
            "previous_impressions": 4000,
            "current_impressions": 4100,
            "previous_avg_position": 5.0,
            "current_avg_position": 4.0,
        }],
    )
    assert report["healthy_pages"] == ["https://example.com/stable"]
    assert report["decaying_pages"] == []
    assert report["pages_needing_more_data"] == []


def test_age_alone_is_not_misreported_as_performance_decay():
    report = build_content_decay_report(
        site_url="https://example.com",
        timeframe="1y",
        today=date(2026, 10, 25),
        pages=[{
            "url": "https://example.com/old-guide",
            "publish_date": date(2024, 1, 1),
            "last_updated": date(2024, 2, 1),
        }],
    )
    assert report["decaying_pages"] == []
    assert report["healthy_pages"] == []
    assert len(report["pages_needing_more_data"]) == 1
    assert "content_not_updated_for_365_days_or_more" in report["pages_needing_more_data"][0]["preliminary_signals"]
    assert any("age alone" in item for item in report["pages_needing_more_data"][0]["missing_data"])


def test_zero_previous_clicks_does_not_divide_by_zero_or_infer_a_decline():
    report = build_content_decay_report(
        site_url="https://example.com",
        timeframe="90d",
        pages=[{
            "url": "https://example.com/new-page",
            "previous_clicks": 0,
            "current_clicks": 20,
        }],
    )
    assert report["decaying_pages"] == []
    assert report["pages_needing_more_data"][0]["url"] == "https://example.com/new-page"


def test_page_priority_uses_reported_revenue_band_and_effort():
    report = build_content_decay_report(
        site_url="https://example.com",
        timeframe="90d",
        pages=[
            {
                "url": "https://example.com/low",
                "previous_clicks": 100,
                "current_clicks": 60,
                "revenue_impact": "low",
                "refresh_effort_hours": 3,
                "competitor_refresh_observed": False,
            },
            {
                "url": "https://example.com/high",
                "previous_clicks": 100,
                "current_clicks": 60,
                "revenue_impact": "high",
                "refresh_effort_hours": 1,
                "competitor_refresh_observed": True,
            },
        ],
    )
    assert report["decaying_pages"][0]["url"] == "https://example.com/high"


def test_schema_rejects_cross_origin_pages_negative_metrics_and_untrusted_urls():
    with pytest.raises(ValidationError):
        ContentDecayRequest(
            site_url="https://example.com",
            pages=[{"url": "https://another.example/article", "previous_clicks": 4, "current_clicks": -1}],
        )
    with pytest.raises(ValidationError):
        ContentDecayRequest(
            site_url="https://example.com",
            pages=[{"url": "http://127.0.0.1/private"}],
        )
    with pytest.raises(ValidationError):
        ContentDecayRequest(
            site_url="https://example.com",
            pages=[{
                "url": "https://example.com/article",
                "publish_date": "2026-05-01",
                "last_updated": "2026-04-01",
            }],
        )


def test_content_decay_api_persists_review_only_report(monkeypatch):
    def fake_report(**kwargs):
        assert kwargs["site_url"] == "https://example.com"
        assert kwargs["timeframe"] == "90d"
        assert len(kwargs["pages"]) == 1
        return {
            "site": "https://example.com",
            "timeframe": "90d",
            "timeframe_label": "90 days",
            "pages_analyzed": 1,
            "pages_decaying": 1,
            "total_refresh_effort_hours": 2.5,
            "decaying_pages": [{
                "url": "https://example.com/article", "title": "Example", "target_keyword": "example",
                "priority": "P1-high", "priority_score": 44.0,
                "decay_signals": ["clicks_declined_20_percent_or_more"], "preliminary_signals": [],
                "refresh_actions": ["Check supplied metrics"], "estimated_effort_hours": 2.5,
                "effort_source": "operator_supplied", "revenue_impact": "medium",
                "contains_affiliate_links": None, "evidence_confidence": "low",
                "data_provenance": "operator_supplied_unverified", "requires_review": True,
                "metrics": {"clicks_decline_pct": 30.0, "impressions_decline_pct": None, "position_worsening": None},
            }],
            "healthy_pages": [],
            "pages_needing_more_data": [],
            "priority_queues": {"P0-critical": [], "P1-high": ["https://example.com/article"], "P2-medium": [], "P3-low": []},
            "monthly_maintenance_schedule": {"week_1_p0": [], "week_2_p1": ["https://example.com/article"], "week_3_p2": [], "week_4_p3_and_recheck": []},
            "search_console_connected": False,
            "competitor_data_checked": False,
            "external_search_performed": False,
            "metrics_source": "operator_supplied_unverified",
            "traffic_recovery_estimate_supported": False,
            "requires_review": True,
            "publishing_started": False,
            "chain_metadata": {"skill_slug": "content-decay-detector", "stage": "blog", "timestamp": "2026-10-25T00:00:00+00:00", "suggested_next": ["affiliate-blog-builder", "seo-audit", "internal-linking-optimizer", "keyword-cluster-architect"]},
            "note": "Operator-supplied data only.",
        }
    monkeypatch.setattr(main, "build_content_decay_report_service", fake_report)
    with TestClient(main.app) as client:
        response = client.post("/api/research/content-decay", json={
            "site_url": "https://example.com",
            "timeframe": "90d",
            "pages": [{
                "url": "https://example.com/article",
                "previous_clicks": 100,
                "current_clicks": 70,
                "revenue_impact": "medium",
            }],
        })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["asset_id"]
    assert body["requires_review"] is True
    assert body["publishing_started"] is False
    assert body["search_console_connected"] is False
    assert body["traffic_recovery_estimate_supported"] is False


def test_content_decay_request_rejects_unpaired_metrics():
    with pytest.raises(ValidationError):
        ContentDecayRequest(
            site_url="https://example.com",
            pages=[{"url": "https://example.com/article", "previous_clicks": 100}],
        )


def test_one_stable_metric_pair_is_not_enough_to_mark_page_healthy():
    report = build_content_decay_report(
        site_url="https://example.com",
        timeframe="90d",
        today=date(2026, 10, 25),
        pages=[{
            "url": "https://example.com/partial-metrics",
            "previous_clicks": 500,
            "current_clicks": 510,
        }],
    )
    assert report["healthy_pages"] == []
    assert report["pages_needing_more_data"][0]["url"] == "https://example.com/partial-metrics"
