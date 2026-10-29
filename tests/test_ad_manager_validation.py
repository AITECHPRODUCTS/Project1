from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.services.ad_manager import evaluate_roas


def test_evaluate_roas_returns_review_only_recommendation_for_valid_values():
    decision = evaluate_roas(" campaign-1 ", spend=10, commission=5, threshold=1.2)

    assert decision.campaign_id == "campaign-1"
    assert decision.roas == 0.5
    assert decision.pause_recommended is True
    assert decision.executed is False


def test_evaluate_roas_zero_spend_has_unknown_roas_and_no_pause_recommendation():
    decision = evaluate_roas("campaign-1", spend=0, commission=100, threshold=1.2)

    assert decision.roas is None
    assert decision.pause_recommended is False
    assert decision.executed is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("spend", -0.01),
        ("spend", float("nan")),
        ("spend", float("inf")),
        ("commission", -1),
        ("commission", float("-inf")),
        ("threshold", -0.01),
        ("threshold", float("nan")),
        ("spend", True),
    ],
)
def test_evaluate_roas_rejects_negative_nonfinite_and_boolean_inputs(field, value):
    values = {"spend": 10.0, "commission": 20.0, "threshold": 1.2}
    values[field] = value

    with pytest.raises(ValueError, match="finite, non-negative"):
        evaluate_roas("campaign-1", **values)


def test_evaluate_roas_rejects_ratio_overflow():
    with pytest.raises(ValueError, match="supported numeric range"):
        evaluate_roas("campaign-1", spend=1e-308, commission=1e308)


def test_evaluate_roas_rejects_blank_or_oversized_campaign_id():
    with pytest.raises(ValueError, match="campaign_id"):
        evaluate_roas("   ", spend=1, commission=1)
    with pytest.raises(ValueError, match="campaign_id"):
        evaluate_roas("x" * 256, spend=1, commission=1)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("spend", -1),
        ("commission", "NaN"),
        ("threshold", "Infinity"),
        ("spend", "-Infinity"),
    ],
)
def test_ads_evaluate_endpoint_returns_422_for_invalid_numeric_inputs(monkeypatch, field, value):
    async def allow_authenticated_workspace():
        return {
            "email": "ad-reviewer@example.invalid",
            "user_id": "ad-reviewer",
            "workspace_id": "ad-workspace",
            "workspace_role": "owner",
        }

    monkeypatch.setitem(
        main.app.dependency_overrides, main.require_auth, allow_authenticated_workspace
    )
    payload = {"campaign_id": "campaign-1", "spend": 10, "commission": 20, "threshold": 1.2}
    payload[field] = value

    with TestClient(main.app) as client:
        response = client.post("/api/ads/evaluate", json=payload)

    assert response.status_code == 422
    assert "finite non-negative numbers" in response.json()["detail"]


def test_ads_evaluate_endpoint_returns_422_for_missing_or_blank_campaign_id(monkeypatch):
    async def allow_authenticated_workspace():
        return {
            "email": "ad-reviewer@example.invalid",
            "user_id": "ad-reviewer",
            "workspace_id": "ad-workspace",
            "workspace_role": "owner",
        }

    monkeypatch.setitem(
        main.app.dependency_overrides, main.require_auth, allow_authenticated_workspace
    )
    with TestClient(main.app) as client:
        missing = client.post(
            "/api/ads/evaluate", json={"spend": 10, "commission": 20}
        )
        blank = client.post(
            "/api/ads/evaluate",
            json={"campaign_id": "   ", "spend": 10, "commission": 20},
        )

    assert missing.status_code == 422
    assert blank.status_code == 422
