from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main
from backend.adapters.ad_performance_webhook import AdPerformanceWebhookAdapter
from backend.config import Settings
from backend.main import app
from backend.schemas import SignedAdPerformanceWebhookPayload


def signed_body(secret: str, payload: dict) -> tuple[bytes, str]:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return raw, signature


def test_collector_hmac_verifies_exact_raw_body_and_rejects_mutation():
    secret = "test-workspace-platform-secret-" + ("x" * 16)
    adapter = AdPerformanceWebhookAdapter(secret)
    raw = b'{"event":"normalized report","value":1}'
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    assert adapter.verify(raw, signature) is True
    assert adapter.verify(raw + b" ", signature) is False
    assert adapter.verify(raw, "00" * 32) is False
    assert adapter.verify(raw, "") is False


def test_workspace_platform_secret_keys_are_normalized_and_validated():
    workspace_id = str(uuid4()).upper()
    configured = Settings(
        app_env="development",
        _env_file=None,
        ad_performance_webhook_secrets={f"{workspace_id}:META": "x" * 40},
    )
    assert f"{workspace_id.lower()}:meta" in configured.ad_performance_webhook_secrets
    with pytest.raises(ValidationError):
        Settings(
            app_env="development",
            _env_file=None,
            ad_performance_webhook_secrets={"not-a-uuid:meta": "x" * 40},
        )
    with pytest.raises(ValidationError):
        Settings(
            app_env="development",
            _env_file=None,
            ad_performance_webhook_secrets={f"{workspace_id.lower()}:meta": "short"},
        )


def test_signed_observation_is_verified_idempotent_and_triggers_guardrail(monkeypatch):
    secret = "test-signed-ad-performance-secret-" + ("z" * 16)
    with TestClient(app) as client:
        plan_response = client.post("/api/ads/plan", json={
            "campaign_name": "Trusted collector integration test",
            "niche": "creator tools",
            "audience": "independent content creators",
            "region": "US",
            "objective": "sales",
            "platforms": ["meta"],
            "variants_per_platform": 1,
            "daily_budget_usd": "40.00",
            "affiliate_disclosure": "Affiliate disclosure: I may earn a commission.",
        })
        assert plan_response.status_code == 201, plan_response.text
        plan_id = plan_response.json()["plan_id"]
        whoami = client.get("/api/auth/me")
        assert whoami.status_code == 200, whoami.text
        workspace_id = whoami.json()["user"]["workspace_id"]
        assert workspace_id

        monkeypatch.setattr(main.settings, "ad_performance_webhook_secrets", {f"{workspace_id}:meta": secret})
        policy_response = client.post(f"/api/ads/plans/{plan_id}/guardrails", json={
            "daily_spend_cap_usd": "35.00",
            "campaign_spend_cap_usd": "500.00",
            "minimum_roas": "1.20",
            "maximum_cpa_usd": "100.00",
            "minimum_verified_impressions": 100,
            "minimum_verified_clicks": 10,
            "minimum_verified_conversions": 3,
        })
        assert policy_response.status_code == 201, policy_response.text
        guardrail_id = policy_response.json()["id"]

        payload = {
            "provider_event_id": "collector-event-" + uuid4().hex,
            "campaign_plan_id": plan_id,
            "platform": "meta",
            "creative_id": "meta-creative-signed-01",
            "source_reference_url": "https://reports.example.com/exports/daily",
            "impressions": 1000,
            "clicks": 50,
            "conversions": 4,
            "spend_usd": "40.00",
            "commission_usd": "0.00",
            "currency": "USD",
            "observed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "note": "Trusted collector test record.",
        }
        invalid = dict(payload)
        invalid["observed_at"] = "2026-10-27T12:00:00"
        with pytest.raises(ValidationError):
            SignedAdPerformanceWebhookPayload.model_validate(invalid)

        raw, signature = signed_body(secret, payload)
        path = f"/api/webhooks/ad-performance/{workspace_id}/meta"
        bad_signature = client.post(path, content=raw, headers={"X-Ad-Performance-Signature": "00" * 32})
        assert bad_signature.status_code == 401, bad_signature.text

        accepted = client.post(path, content=raw, headers={"X-Ad-Performance-Signature": signature})
        assert accepted.status_code == 201, accepted.text
        event = accepted.json()
        assert event["status"] == "recorded"
        assert event["evidence_status"] == "provider_verified"
        assert event["collector_signature_verified"] is True
        assert event["native_provider_signature_checked_by_project1"] is False
        assert event["provider_action_executed"] is False

        duplicate = client.post(path, content=raw, headers={"X-Ad-Performance-Signature": signature})
        assert duplicate.status_code == 200, duplicate.text
        assert duplicate.json()["status"] == "duplicate_ignored"

        # A reused provider event ID is idempotent only when its business payload matches.
        conflicting_payload = dict(payload)
        conflicting_payload["spend_usd"] = "41.00"
        conflicting_raw, conflicting_signature = signed_body(secret, conflicting_payload)
        conflicting = client.post(
            path,
            content=conflicting_raw,
            headers={"X-Ad-Performance-Signature": conflicting_signature},
        )
        assert conflicting.status_code == 409, conflicting.text
        assert "different observation data" in conflicting.json()["detail"]

        evaluated = client.post(f"/api/ads/guardrails/{guardrail_id}/evaluate")
        assert evaluated.status_code == 200, evaluated.text
        result = evaluated.json()
        assert result["evaluation"]["status"] == "triggered_stop"
        assert result["kill_switch_engaged"] is True
        assert result["stop_latched"] is True
        assert result["evaluation"]["provider_action_executed"] is False


def test_signed_collector_requires_workspace_platform_secret_and_rejects_wrong_payload_platform(monkeypatch):
    secret = "another-workspace-secret-" + ("m" * 24)
    with TestClient(app) as client:
        plan_response = client.post("/api/ads/plan", json={
            "campaign_name": "Missing collector secret test",
            "niche": "creator tools",
            "audience": "independent content creators",
            "region": "US",
            "objective": "sales",
            "platforms": ["meta"],
            "variants_per_platform": 1,
            "daily_budget_usd": "20.00",
            "affiliate_disclosure": "Affiliate disclosure: I may earn a commission.",
        })
        assert plan_response.status_code == 201, plan_response.text
        workspace_id = client.get("/api/auth/me").json()["user"]["workspace_id"]
        payload = {
            "provider_event_id": "collector-event-" + uuid4().hex,
            "campaign_plan_id": plan_response.json()["plan_id"],
            "platform": "google_search",
            "creative_id": "google-creative-01",
            "impressions": 10,
            "clicks": 1,
            "conversions": 0,
            "spend_usd": "1.00",
            "commission_usd": "0.00",
            "currency": "USD",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        path = f"/api/webhooks/ad-performance/{workspace_id}/meta"
        absent = client.post(path, content=raw, headers={"X-Ad-Performance-Signature": signature})
        assert absent.status_code == 503, absent.text

        monkeypatch.setattr(main.settings, "ad_performance_webhook_secrets", {f"{workspace_id}:meta": secret})
        wrong_platform = client.post(path, content=raw, headers={"X-Ad-Performance-Signature": signature})
        assert wrong_platform.status_code == 422, wrong_platform.text
