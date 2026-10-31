from __future__ import annotations

from fastapi.testclient import TestClient

from backend import main


def test_skill_finder_api_forwards_search_filters(monkeypatch):
    def fake_find_skills(**kwargs):
        assert kwargs == {"query":"purple cow","stage":"S2","status":"partial","limit":5}
        return {"skill_count":53,"matched_count":1,"results":[{"skill_id":"research/purple-cow-audit","stage":"S2","status":"partial","gap":"Buyer validation remains"}],"read_only":True}
    monkeypatch.setattr(main, "find_skills_service", fake_find_skills)
    with TestClient(main.app) as client:
        response=client.get("/api/skills/find?q=purple%20cow&stage=S2&status=partial&limit=5")
    assert response.status_code==200,response.text
    assert response.json()["results"][0]["skill_id"]=="research/purple-cow-audit"
    assert response.json()["read_only"] is True


def test_skill_finder_api_rejects_short_query():
    with TestClient(main.app) as client:
        response=client.get("/api/skills/find?q=x")
    assert response.status_code==422
