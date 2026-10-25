from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main
from backend.schemas import ContentMoatRequest
from backend.services.content_moat_calculator import analyze_content_moat


def _competitor(domain: str, pages: int, **extra):
    return {"domain": domain, "pages_on_topic": pages, **extra}


def test_calculates_average_target_gap_and_timeline_from_supplied_competitors():
    report = analyze_content_moat(
        niche="AI video tools",
        hub_keyword="best AI video tools",
        your_current_pages=20,
        publishing_capacity="2/week",
        competitors=[
            _competitor("alpha.example.com", 35, content_quality="average", freshness="recent"),
            _competitor("beta.example.com", 15, content_quality="thin", freshness="stale"),
            _competitor("gamma.example.com", 50, content_quality="deep", freshness="actively_updated"),
        ],
    )
    assert report["average_competitor_pages"] == 33.3
    assert report["moat_target"] == 50
    assert report["content_gap"] == 30
    assert report["weeks_to_moat"] == 15
    assert report["feasibility"] == "yellow"
    assert sum(phase["pages"] for phase in report["phase_roadmap"]) == 30
    assert report["competitor_data_verified"] is False
    assert report["live_search_performed"] is False
    assert report["search_volume_validated"] is False
    assert report["ranking_outcome_guaranteed"] is False
    assert report["publishing_started"] is False


def test_existing_content_at_or_above_target_has_no_negative_gap():
    report = analyze_content_moat(
        niche="Narrow gardening",
        your_current_pages=100,
        publishing_capacity="3/week",
        competitors=[_competitor("garden.example.com", 20)],
    )
    assert report["moat_target"] == 30
    assert report["content_gap"] == 0
    assert report["weeks_to_moat"] == 0
    assert "benchmark is met" in report["assessment"]


@pytest.mark.parametrize(
    ("competitor_pages", "expected_band"),
    [(12, "green"), (20, "yellow"), (40, "orange"), (101, "red")],
)
def test_feasibility_bands_are_transparent(competitor_pages, expected_band):
    report = analyze_content_moat(
        niche="Test niche",
        your_current_pages=0,
        publishing_capacity="1/week",
        competitors=[_competitor("example.com", competitor_pages)],
    )
    assert report["feasibility"] == expected_band


def test_schema_rejects_duplicate_domains_invalid_domain_and_invalid_capacity():
    with pytest.raises(ValidationError):
        ContentMoatRequest(
            niche="Video editors",
            publishing_capacity="4/week",
            competitors=[_competitor("example.com", 5)],
        )
    with pytest.raises(ValidationError):
        ContentMoatRequest(
            niche="Video editors",
            competitors=[_competitor("example.com/path", 5)],
        )
    with pytest.raises(ValidationError):
        ContentMoatRequest(
            niche="Video editors",
            competitors=[_competitor("example.com", 5), _competitor("https://example.com/", 7)],
        )
    with pytest.raises(ValidationError):
        ContentMoatRequest(
            niche="Video editors",
            your_current_pages=-1,
            competitors=[_competitor("example.com", 5)],
        )


def test_content_moat_api_persists_review_only_report(monkeypatch):
    def fake_analyzer(**kwargs):
        assert kwargs["niche"] == "AI video tools"
        assert kwargs["hub_keyword"] == "best AI video"
        assert kwargs["your_current_pages"] == 10
        assert kwargs["publishing_capacity"] == "2/week"
        assert kwargs["competitors"][0]["domain"] == "example.com"
        return {
            "niche": "AI video tools", "hub_keyword": "best AI video",
            "competitors_analyzed": 1,
            "competitors": [{"domain": "example.com", "pages_on_topic": 30, "content_quality": "average", "freshness": "recent", "evidence_note": "", "data_source": "operator_supplied_unverified"}],
            "average_competitor_pages": 30.0, "moat_multiplier": 1.5, "moat_target": 45,
            "your_current_pages": 10, "content_gap": 35, "publishing_capacity": "2/week",
            "publishing_capacity_pages_per_week": 2, "weeks_to_moat": 18, "feasibility": "yellow",
            "assessment": "Planning model only.", "recommendation": "Validate first.",
            "phase_roadmap": [{"phase": "Foundation", "content": "Hub and spokes", "pages": 5, "weeks": 3}],
            "authority_gaps": [], "competitive_advantages": [],
            "competitor_data_verified": False, "live_search_performed": False, "search_volume_validated": False,
            "ranking_outcome_guaranteed": False, "data_provenance": "operator_supplied_unverified",
            "requires_review": True, "publishing_started": False,
            "chain_metadata": {"skill_slug": "content-moat-calculator", "stage": "blog", "timestamp": "2026-10-25T00:00:00+00:00", "suggested_next": ["affiliate-blog-builder"]},
            "note": "Operator-supplied data only.",
        }
    monkeypatch.setattr(main, "analyze_content_moat_service", fake_analyzer)
    with TestClient(main.app) as client:
        response = client.post("/api/research/content-moat", json={
            "niche": "AI video tools",
            "hub_keyword": "best AI video",
            "your_current_pages": 10,
            "publishing_capacity": "2/week",
            "competitors": [{"domain": "example.com", "pages_on_topic": 30}],
        })
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["asset_id"]
    assert result["competitor_data_verified"] is False
    assert result["publishing_started"] is False


def test_service_rejects_duplicate_and_invalid_competitor_inputs():
    with pytest.raises(ValueError):
        analyze_content_moat(
            niche="Video tools", your_current_pages=0, publishing_capacity="2/week",
            competitors=[_competitor("example.com", 5), _competitor("example.com", 7)],
        )
    with pytest.raises(ValueError):
        analyze_content_moat(
            niche="Video tools", your_current_pages=0, publishing_capacity="4/week",
            competitors=[_competitor("example.com", 5)],
        )
