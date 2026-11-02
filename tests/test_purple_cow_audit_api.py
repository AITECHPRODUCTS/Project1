from __future__ import annotations
from fastapi.testclient import TestClient
from backend import main


def test_purple_cow_audit_endpoint_returns_review_only_result(monkeypatch):
    def fake_audit(**kwargs):
        assert kwargs["offer_name"] == "Creator editor"
        assert len(kwargs["alternatives"]) == 1
        return {"score":72,"score_components":{"lexical_distinctiveness_vs_supplied_alternatives":80},"alternative_comparisons":[{"name":"Alternative A","lexical_overlap_score":20}],"market_research_performed":False,"publishing_started":False,"requires_review":True}
    monkeypatch.setattr(main,"audit_purple_cow_positioning_service",fake_audit)
    with TestClient(main.app) as client:
        response=client.post("/api/research/purple-cow-audit",json={"offer_name":"Creator editor","target_audience":"independent video creators","positioning_statement":"A source-linked editing workflow for creators","alternatives":[{"name":"Alternative A","positioning_statement":"A general editor for all creators","evidence_note":""}]})
    assert response.status_code==200,response.text
    result=response.json()
    assert result["market_research_performed"] is False
    assert result["publishing_started"] is False
    assert result["requires_review"] is True
    assert result["score"]==72


def test_purple_cow_audit_request_requires_comparison_input():
    with TestClient(main.app) as client:
        response=client.post("/api/research/purple-cow-audit",json={"offer_name":"Creator editor","target_audience":"independent video creators","positioning_statement":"A source-linked editing workflow for creators","alternatives":[]})
    assert response.status_code==422
