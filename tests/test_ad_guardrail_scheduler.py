from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from backend import main
from backend.main import app


def _sign(secret: str, payload: dict) -> tuple[bytes, str]:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return raw, hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def test_scheduled_guardrail_monitor_latches_verified_breach(monkeypatch):
    secret = "scheduled-guardrail-test-secret-" + ("s" * 16)
    with TestClient(app) as client:
        plan = client.post("/api/ads/plan", json={
            "campaign_name": "Scheduled guardrail integration",
            "niche": "creator tools",
            "audience": "independent content creators",
            "region": "US",
            "objective": "sales",
            "platforms": ["meta"],
            "variants_per_platform": 1,
            "daily_budget_usd": "40.00",
            "affiliate_disclosure": "Affiliate disclosure: I may earn a commission.",
        })
        assert plan.status_code == 201, plan.text
        plan_id = plan.json()["plan_id"]
        workspace_id = client.get("/api/auth/me").json()["user"]["workspace_id"]
        monkeypatch.setattr(main.settings, "ad_performance_webhook_secrets", {f"{workspace_id}:meta": secret})

        guardrail = client.post(f"/api/ads/plans/{plan_id}/guardrails", json={
            "daily_spend_cap_usd": "35.00",
            "campaign_spend_cap_usd": "500.00",
            "minimum_roas": "1.20",
            "maximum_cpa_usd": "100.00",
            "minimum_verified_impressions": 100,
            "minimum_verified_clicks": 10,
            "minimum_verified_conversions": 3,
        })
        assert guardrail.status_code == 201, guardrail.text
        guardrail_id = guardrail.json()["id"]

        payload = {
            "provider_event_id": "scheduled-" + uuid4().hex,
            "campaign_plan_id": plan_id,
            "platform": "meta",
            "creative_id": "scheduled-creative",
            "impressions": 1000,
            "clicks": 50,
            "conversions": 4,
            "spend_usd": "40.00",
            "commission_usd": "0.00",
            "currency": "USD",
            "observed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        raw, signature = _sign(secret, payload)
        response = client.post(
            f"/api/webhooks/ad-performance/{workspace_id}/meta",
            content=raw,
            headers={"X-Ad-Performance-Signature": signature},
        )
        assert response.status_code == 201, response.text
        assert response.json()["evidence_status"] == "provider_verified"

    # The monitor uses the same durable database/session factory used by the API,
    # but executes outside the TestClient event loop to exercise the real scheduler job.
    summary = asyncio.run(main.ad_guardrail_monitor_job())
    assert summary["guardrails_evaluated"] >= 1
    assert summary["guardrails_latched"] >= 1

    with TestClient(app) as client:
        response = client.get("/api/ads/guardrails?limit=300")
        assert response.status_code == 200, response.text
        row = next(item for item in response.json()["data"] if item["id"] == guardrail_id)
        assert row["kill_switch_engaged"] is True
        assert row["stop_latched"] is True
        assert row["last_evaluation"]["status"] == "triggered_stop"


def test_scheduled_guardrail_monitor_handles_no_workspaces(monkeypatch):
    async def no_workspaces():
        return []

    monkeypatch.setattr(main, "_background_workspace_ids", no_workspaces)
    result = asyncio.run(main.ad_guardrail_monitor_job())
    assert result == {
        "workspaces_processed": 0,
        "guardrails_evaluated": 0,
        "guardrails_latched": 0,
        "guardrails_failed": 0,
    }
