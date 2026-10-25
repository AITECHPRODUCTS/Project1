from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main
from backend.schemas import CategoryDesignRequest
from backend.services.category_designer import design_category_taxonomy


def test_design_creates_safe_slugs_and_transparent_taxonomy_from_supplied_topics():
    result=design_category_taxonomy(
        niche="Creator video editing",
        target_audience="independent creators",
        topic_candidates=["Beginner video editing","Video editing workflows","Editing software comparisons"],
        existing_categories=["Video editing","Audio tips"],
    )
    assert result["category_count"]==3
    assert result["root_category"]=="Creator video editing"
    assert all(category["parent_category"]=="Creator video editing" for category in result["categories"])
    assert all(category["slug"] for category in result["categories"])
    assert len({category["slug"] for category in result["categories"]})==3
    assert result["search_volume_validated"] is False
    assert result["taxonomy_evaluated"] is False
    assert result["publishing_started"] is False
    assert result["requires_review"] is True


def test_design_flags_existing_category_overlap_without_claiming_duplicate_content():
    result=design_category_taxonomy(
        niche="Gardening",
        target_audience="home gardeners",
        topic_candidates=["Container gardening basics","Indoor herb gardening","Seasonal soil preparation"],
        existing_categories=["Container gardening","Garden product reviews"],
    )
    first=result["categories"][0]
    assert first["overlap_score_vs_existing"] >= 60
    assert first["matched_existing_category"]=="Container gardening"
    assert "possible_duplicate_or_near_duplicate" in first["flags"]
    assert "Search volume" in result["recommendations"][1]


def test_request_rejects_too_few_distinct_topic_candidates():
    with pytest.raises(ValidationError):
        CategoryDesignRequest(niche="Creator tools",target_audience="small teams",topic_candidates=["Same label","Same label","same label"])


def test_category_design_api_persists_review_only_workspace_draft(monkeypatch):
    def fake_designer(**kwargs):
        assert kwargs["niche"]=="Creator tools"
        return {
            "root_category":"Creator tools","target_audience":"small teams",
            "categories":[{"name":"Starter guides","slug":"starter-guides","parent_category":"Creator tools","description":"Draft description","overlap_score_vs_existing":None,"matched_existing_category":None,"flags":[],"origin":"operator_supplied_topic_candidate"}],
            "category_count":1,"existing_category_count":0,"categories_flagged_for_review":0,
            "taxonomy_method":"operator_supplied_topics_with_deterministic_slug_and_lexical_overlap_checks",
            "search_volume_validated":False,"taxonomy_evaluated":False,"publishing_started":False,"requires_review":True,
            "recommendations":["Validate before use"],"note":"Inventory only.",
        }
    monkeypatch.setattr(main,"design_category_taxonomy_service",fake_designer)
    with TestClient(main.app) as client:
        response=client.post("/api/research/category-design",json={
            "niche":"Creator tools","target_audience":"small teams",
            "topic_candidates":["Starter guides","Software comparisons","Editing workflows"],
            "existing_categories":[],
        })
    assert response.status_code==201,response.text
    result=response.json()
    assert result["asset_id"]
    assert result["search_volume_validated"] is False
    assert result["publishing_started"] is False
    assert result["requires_review"] is True


def test_category_design_api_rejects_too_few_topics():
    with TestClient(main.app) as client:
        response=client.post("/api/research/category-design",json={
            "niche":"Creator tools","target_audience":"small teams",
            "topic_candidates":["Starter guides"],
        })
    assert response.status_code==422
