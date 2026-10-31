from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main
from backend.schemas import InfographicRequest
from backend.services.infographic_generator import build_infographic


def test_builder_returns_safe_self_contained_svg_from_supplied_points():
    result=build_infographic(
        title="<script>alert(1)</script> Helpful Guide",
        subtitle="Three steps with facts from the operator",
        audience="Independent creators",
        key_points=["Compare options using the same criteria","Check current product terms before deciding","Verify claims against primary source material"],
        source_urls=["https://example.com/source"],
    )
    assert result["format"]=="image/svg+xml"
    assert result["width"]==1080 and result["height"]==1350
    assert len(result["cards"])==3
    assert result["requires_review"] is True
    assert result["publishing_started"] is False
    assert "<svg" in result["svg"]
    assert "&lt;script&gt;" in result["svg"]
    assert "<script>alert(1)</script>" not in result["svg"]
    assert "example.com" not in result["svg"].lower()
    assert all(1<=len(card["lines"])<=5 for card in result["cards"])


def test_builder_caps_point_lines_and_uses_no_external_resources():
    result=build_infographic(
        title="Source-backed visual checklist",
        key_points=[
            "A very long sentence with many details " * 4,
            "Second actionable point for the reader",
            "Third evidence review point",
            "Fourth point about current conditions",
            "Fifth practical checklist point",
            "Sixth and final point",
        ],
        source_urls=["https://example.com/ref"],
    )
    assert len(result["cards"])==6
    assert all(len(card["lines"])<=5 for card in result["cards"])
    assert "href=" not in result["svg"]
    assert "<image" not in result["svg"]
    assert "<script" not in result["svg"].lower()


def test_infographic_request_rejects_private_sources_and_duplicate_points():
    with pytest.raises(ValidationError):
        InfographicRequest(title="Source-backed infographic",key_points=["First fact","Second fact","Third fact"],source_urls=["http://127.0.0.1/secret"])
    with pytest.raises(ValidationError):
        InfographicRequest(title="Source-backed infographic",key_points=["Same point","Same point","Third distinct fact"])


def test_infographic_api_persists_svg_as_reviewable_workspace_asset(monkeypatch):
    def fake_builder(**kwargs):
        assert kwargs["title"]=="Source-backed visual"
        assert len(kwargs["key_points"])==3
        return {
            "title":kwargs["title"],"subtitle":"Three points","audience":None,
            "key_points":kwargs["key_points"],"cards":[{"number":1},{"number":2},{"number":3}],
            "width":1080,"height":1350,"format":"image/svg+xml",
            "svg":"<svg xmlns='http://www.w3.org/2000/svg'><text>review</text></svg>",
            "source_urls":kwargs["source_urls"],"requires_review":True,
            "publishing_started":False,"external_image_provider_used":False,"note":"Draft only",
        }
    monkeypatch.setattr(main,"build_infographic_service",fake_builder)
    with TestClient(main.app) as client:
        response=client.post("/api/content/infographic",json={
            "title":"Source-backed visual","subtitle":"A concise review list","audience":"Creators",
            "key_points":["Point one about a workflow","Point two about evidence","Point three about terms"],
            "source_urls":["https://example.com/reference"],
        })
    assert response.status_code==201,response.text
    result=response.json()
    assert result["asset_id"]
    assert result["format"]=="image/svg+xml"
    assert result["requires_review"] is True
    assert result["publishing_started"] is False
    assert result["svg"].startswith("<svg")


def test_infographic_api_requires_three_points():
    with TestClient(main.app) as client:
        response=client.post("/api/content/infographic",json={"title":"Too few facts","key_points":["Only one point"]})
    assert response.status_code==422
