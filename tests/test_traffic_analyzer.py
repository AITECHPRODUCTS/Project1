from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main
from backend.schemas import TrafficAnalysisRequest
from backend.services.traffic_analyzer import analyze_traffic_domains


def _domain(domain: str, **values):
    return {"domain": domain, **values}


def test_scores_complete_metrics_and_orders_domains_for_comparison():
    result = analyze_traffic_domains(
        focus="affiliate",
        domains=[
            _domain(
                "strong.example.com",
                global_rank=8000,
                country_rank=100,
                country="US",
                monthly_visits=1_500_000,
                visits_trend="growing",
                pages_per_visit=4.5,
                avg_duration_seconds=240,
                bounce_rate=32,
                traffic_sources={"direct": 35, "search": 32, "social": 10, "referral": 13, "paid": 10},
            ),
            _domain(
                "small.example.com",
                global_rank=15_000_000,
                monthly_visits=30_000,
                visits_trend="declining",
                pages_per_visit=1.5,
                avg_duration_seconds=30,
                bounce_rate=75,
                traffic_sources={"direct": 5, "search": 5, "social": 30, "referral": 10, "paid": 50},
            ),
        ],
    )
    by_domain = {item["domain"]: item for item in result["domains_analyzed"]}
    assert by_domain["strong.example.com"]["traffic_score"] >= 80
    assert by_domain["strong.example.com"]["verdict"] == "excellent"
    assert by_domain["small.example.com"]["verdict"] in {"weak", "red_flag"}
    assert "operator_reported_traffic_decline" in by_domain["small.example.com"]["risk_flags"]
    assert result["comparison"]["winner"] == "strong.example.com"
    assert result["provider_connected"] is False
    assert result["external_search_performed"] is False
    assert result["traffic_data_verified"] is False


def test_insufficient_data_is_not_falsely_scored_as_red_flag():
    result = analyze_traffic_domains(
        focus="advertiser",
        domains=[_domain("new.example.com")],
    )
    row = result["domains_analyzed"][0]
    assert row["traffic_score"] is None
    assert row["verdict"] == "insufficient_data"
    assert row["missing_metrics"]


def test_missing_metric_groups_are_weight_normalized_instead_of_zero_filled():
    result = analyze_traffic_domains(
        focus="competitor",
        domains=[_domain("known.example.com", monthly_visits=120_000)],
    )
    row = result["domains_analyzed"][0]
    assert row["traffic_score"] == 75.0
    assert row["component_scores"]["rank"] is None
    assert row["component_scores"]["volume"] == 75.0


def test_traffic_schema_rejects_bad_domain_duplicate_and_impossible_source_shares():
    with pytest.raises(ValidationError):
        TrafficAnalysisRequest(domains=[_domain("localhost", monthly_visits=1)])
    with pytest.raises(ValidationError):
        TrafficAnalysisRequest(domains=[_domain("example.com", monthly_visits=1), _domain("https://example.com/", monthly_visits=2)])
    with pytest.raises(ValidationError):
        TrafficAnalysisRequest(domains=[_domain("example.com", traffic_sources={"direct": 80, "search": 80, "social": 0, "referral": 0, "paid": 0})])
    with pytest.raises(ValidationError):
        TrafficAnalysisRequest(domains=[_domain("example.com", monthly_visits=-1)])


def test_traffic_api_persists_review_only_analysis(monkeypatch):
    def fake_analyzer(**kwargs):
        assert kwargs["focus"] == "affiliate"
        assert len(kwargs["domains"]) == 1
        assert kwargs["domains"][0]["domain"] == "example.com"
        return {
            "focus": "affiliate",
            "domains_analyzed": [{"domain": "example.com", "data_source": "operator_supplied_unverified", "metrics": {"global_rank": None, "country_rank": None, "country": "", "monthly_visits": 1000, "monthly_visits_formatted": "1.0K", "visits_trend": "unknown", "pages_per_visit": None, "avg_duration_seconds": None, "bounce_rate": None}, "traffic_sources": {"direct": None, "search": None, "social": None, "referral": None, "paid": None}, "component_scores": {"rank": None, "volume": 20, "engagement": None, "diversity": None, "brand": None}, "traffic_score": 20, "verdict": "weak", "risk_flags": [], "missing_metrics": ["global_rank"], "interpretation": "Operator data only."}],
            "comparison": None, "recommendation": "Verify affiliate terms.",
            "recommended_next_skill": "affiliate-program-search",
            "scoring_weights": {"rank": 20, "volume": 25, "engagement": 25, "diversity": 15, "brand": 15},
            "provider_connected": False, "external_search_performed": False, "traffic_data_verified": False,
            "requires_review": True, "publishing_started": False, "note": "No provider data used.",
        }
    monkeypatch.setattr(main, "analyze_traffic_domains_service", fake_analyzer)
    with TestClient(main.app) as client:
        response = client.post("/api/research/traffic-analyzer", json={
            "focus": "affiliate",
            "domains": [{"domain": "example.com", "monthly_visits": 1000}],
        })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["asset_id"]
    assert body["traffic_data_verified"] is False
    assert body["provider_connected"] is False
    assert body["publishing_started"] is False


def test_service_rejects_empty_or_duplicate_domain_list():
    with pytest.raises(ValueError):
        analyze_traffic_domains(focus="affiliate", domains=[])
    with pytest.raises(ValueError):
        analyze_traffic_domains(focus="affiliate", domains=[_domain("example.com"), _domain("example.com")])
