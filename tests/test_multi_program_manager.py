from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main
from backend.schemas import MultiProgramManagerRequest
from backend.services.multi_program_manager import manage_program_portfolio


def _program(name, **values):
    return {"name": name, **values}


def test_epc_shares_concentration_stability_and_cautious_actions():
    report = manage_program_portfolio(
        goal="maximize_revenue", budget_hours=10,
        programs=[
            _program("Recurring Leader", niche="Creator SaaS", reward_type="cps_recurring", reward_value="30% recurring", monthly_revenue=800, monthly_clicks=1000),
            _program("Low EPC Program", niche="Creator SaaS", reward_type="cps_one_time", monthly_revenue=100, monthly_clicks=500),
            _program("New Video Partner", niche="Video", status="considering"),
        ],
    )
    rows = {item["name"]: item for item in report["programs"]}
    assert rows["Recurring Leader"]["epc"] == 0.8
    assert rows["Recurring Leader"]["revenue_share"] == 88.89
    assert rows["Recurring Leader"]["action"] == "double_down"
    assert rows["Low EPC Program"]["action"] == "phase_out"
    assert "candidate" in rows["Low EPC Program"]["reason"]
    assert rows["New Video Partner"]["action"] == "optimize"
    assert report["portfolio"]["concentration_risk"] == "high"
    assert report["portfolio"]["niche_diversification"] == "overlapping"
    assert report["portfolio"]["revenue_stability"] == "stable"
    assert not report["provider_connected"] and not report["payouts_verified"] and not report["program_mutations_started"]


@pytest.mark.parametrize("budget", [1, 7.25, 10, 13.5])
def test_weekly_plan_sums_to_exact_budget(budget):
    report = manage_program_portfolio(goal="diversify", budget_hours=budget, programs=[
        _program("One", monthly_revenue=100, monthly_clicks=100, niche="A", reward_type="cps_recurring"),
        _program("Two", monthly_revenue=80, monthly_clicks=100, niche="B", reward_type="cps_one_time"),
    ])
    assert round(sum(row["hours"] for row in report["weekly_plan"]["allocation"]), 2) == round(budget, 2)
    assert report["weekly_plan"]["total_hours"] == round(budget, 2)


def test_missing_metrics_are_unknown_not_zero_performance():
    report = manage_program_portfolio(programs=[_program("One"), _program("Two", status="new")], budget_hours=3)
    assert report["portfolio"]["total_monthly_revenue"] is None
    assert report["portfolio"]["concentration_risk"] == "unknown"
    assert report["portfolio"]["revenue_stability"] == "unknown"
    assert all(item["epc"] is None and item["revenue_share"] is None for item in report["programs"])
    assert not any(item["action"] == "phase_out" for item in report["programs"])


def test_zero_clicks_does_not_create_infinite_epc():
    report = manage_program_portfolio(programs=[_program("No clicks", monthly_revenue=12, monthly_clicks=0)])
    assert report["programs"][0]["epc"] is None
    assert report["programs"][0]["revenue_share"] == 100
    assert report["programs"][0]["action"] == "maintain"


def test_diversify_goal_identifies_niche_gap():
    report = manage_program_portfolio(goal="diversify", programs=[
        _program("One", niche="One niche", monthly_revenue=100, monthly_clicks=100),
        _program("Two", niche="One niche", monthly_revenue=50, monthly_clicks=100),
    ])
    assert any(rec["action"] == "identify_niche_gaps" for rec in report["recommendations"])


def test_schema_rejects_duplicate_names_private_urls_and_invalid_metrics():
    with pytest.raises(ValidationError):
        MultiProgramManagerRequest(programs=[_program("Example Program"), _program(" example program ")])
    with pytest.raises(ValidationError):
        MultiProgramManagerRequest(programs=[_program("Program One", affiliate_url="http://127.0.0.1/private")])
    with pytest.raises(ValidationError):
        MultiProgramManagerRequest(programs=[_program("Program One", monthly_revenue=-1)])
    with pytest.raises(ValidationError):
        MultiProgramManagerRequest(programs=[_program("Program One", monthly_clicks=1.5)])


def test_api_persists_review_only_portfolio_report(monkeypatch):
    def fake_manager(**kwargs):
        assert kwargs["goal"] == "reduce_risk" and kwargs["budget_hours"] == 8
        assert len(kwargs["programs"]) == 1 and kwargs["programs"][0]["name"] == "A program"
        return {
            "portfolio": {"total_programs": 1, "active_programs": 1, "paused_programs": 0,
                "total_monthly_revenue": 100.0, "total_monthly_clicks": 50, "revenue_share_complete": True,
                "click_metrics_complete": True, "data_completeness_pct": 100, "top_program_revenue_share": 100,
                "top_two_program_revenue_share": 100, "recurring_revenue_share": 100, "concentration_risk": "high",
                "niche_diversification": "single_niche", "revenue_stability": "stable", "goal": "reduce_risk",
                "goal_note": "Reduce concentration."},
            "programs": [{"name": "A program", "affiliate_url": None, "niche": "test", "reward_type": "cps_recurring",
                "reward_value": "30%", "status": "active", "monthly_revenue": 100.0, "monthly_clicks": 50, "epc": 2.0,
                "revenue_share": 100.0, "commission_quality_score": 5, "relative_score": 100, "action": "double_down",
                "reason": "Reported EPC is high.", "data_provenance": "operator_supplied_unverified"}],
            "recommendations": [], "weekly_plan": {"total_hours": 8.0, "allocation": [
                {"program": "A program", "hours": 7.2, "tasks": ["Review"]},
                {"program": "Portfolio research", "hours": 0.8, "tasks": ["Research"]}], "category_targets": []},
            "metrics_source": "operator_supplied_unverified", "provider_connected": False, "external_search_performed": False,
            "payouts_verified": False, "program_mutations_started": False, "requires_review": True,
            "chain_metadata": {"skill_slug": "multi-program-manager", "stage": "automation", "suggested_next": ["traffic-analyzer"]},
            "note": "Manual data only.",
        }
    monkeypatch.setattr(main, "manage_program_portfolio_service", fake_manager)
    with TestClient(main.app) as client:
        response = client.post("/api/automation/multi-program-manager", json={
            "goal": "reduce_risk", "budget_hours": 8,
            "programs": [{"name": "A program", "monthly_revenue": 100, "monthly_clicks": 50, "reward_type": "cps_recurring"}],
        })
    assert response.status_code == 201, response.text
    assert response.json()["asset_id"]
    assert response.json()["provider_connected"] is False
    assert response.json()["program_mutations_started"] is False


def test_service_rejects_duplicate_programs_and_invalid_budget():
    with pytest.raises(ValueError):
        manage_program_portfolio(programs=[_program("Duplicate"), _program(" duplicate ")])
    with pytest.raises(ValueError):
        manage_program_portfolio(programs=[_program("Single")], budget_hours=100)
