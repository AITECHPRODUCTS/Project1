from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import main


_AD_PLAN = {
    "niche": "creator video editing",
    "audience": "independent creators",
    "region": "US",
    "objective": "leads",
    "platforms": ["meta"],
    "daily_budget_usd": "1.00",
    "affiliate_disclosure": "Disclosure: I may earn a commission from qualifying purchases.",
}
_OBSERVATION = {
    "platform": "meta",
    "creative_id": "auth-regression-creative",
    "spend_usd": "0.00",
    "commission_usd": "0.00",
}
_EVALUATION = {"campaign_id": "auth-regression-plan", "spend": 10.0, "commission": 20.0}


def _requests(client: TestClient):
    return [
        client.get("/api/ads/plans"),
        client.get("/api/ads/plans/not-a-real-plan"),
        client.post("/api/ads/plan", json=_AD_PLAN),
        client.post("/api/ads/observations", json=_OBSERVATION),
        client.get("/api/ads/observations"),
        client.get("/api/ads/performance"),
        client.post("/api/ads/evaluate", json=_EVALUATION),
    ]


def test_ad_routes_require_authentication(monkeypatch):
    async def deny_auth():
        raise HTTPException(status_code=401, detail="Authentication required")

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, deny_auth)
    with TestClient(main.app) as client:
        responses = _requests(client)
    assert [response.status_code for response in responses] == [401] * len(responses)


def test_ad_routes_refuse_authenticated_users_without_an_active_workspace(monkeypatch):
    async def no_workspace():
        return {
            "email": "member@example.invalid",
            "user_id": "test-member",
            "workspace_id": None,
            "workspace_role": "member",
        }

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, no_workspace)
    with TestClient(main.app) as client:
        responses = _requests(client)
    assert [response.status_code for response in responses] == [403] * len(responses)
