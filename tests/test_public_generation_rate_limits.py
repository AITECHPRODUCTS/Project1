from __future__ import annotations

from starlette.requests import Request
from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from backend import main
from backend.tenancy import get_workspace_id


def _request(ip: str = "203.0.113.82") -> Request:
    return Request({
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/api/public/leads/capture",
        "raw_path": b"/api/public/leads/capture",
        "query_string": b"",
        "headers": [],
        "client": (ip, 12345),
        "server": ("testserver", 443),
    })


class _FakeRedis:
    def __init__(self):
        self.counts: dict[str, int] = {}
        self.calls: list[tuple[str, int, str, int]] = []

    async def eval(self, script, numkeys, key, window_seconds):
        self.calls.append((script, numkeys, key, int(window_seconds)))
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]


class _BrokenRedis:
    async def eval(self, script, numkeys, key, window_seconds):
        raise ConnectionError("redis is unavailable")


async def _fake_rate_limit(*args, **kwargs):
    return None


def _payloads():
    return [
        ("/api/content/social", {"topic": "A safe marketing guide", "hooks": [{"hook": "Useful tip"}], "platform": "linkedin"}),
        ("/api/content/tiktok-script", {"topic": "A safe marketing guide", "hooks": [{"hook": "Useful tip"}]}),
        ("/api/content/video", {"script": "A short script with enough words to render safely.", "broll_query": "desk workspace"}),
        ("/api/landing/offer", {"product": {"name": "Example"}, "audience": "new creators", "main_problem": "limited time"}),
        ("/api/landing/value-ladder", {"audience": "new creators", "product": {"name": "Example"}, "deliverable_assets": []}),
        ("/api/content/keywords", {"keywords": [f"keyword {i} for affiliate marketing" for i in range(50)]}),
    ]


def test_expensive_generation_and_render_routes_require_authentication(monkeypatch):
    async def deny_auth():
        raise HTTPException(401, "Authentication required")

    calls: list[str] = []
    async def fake(*args, **kwargs):
        calls.append("called")
        return {"status": "test"}

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, deny_auth)
    for name in ("viral_post_writer", "tiktok_script_writer", "render_vertical_video",
                 "grand_slam_offer_generator", "value_ladder_architect", "keyword_cluster_architect"):
        monkeypatch.setattr(main, name, fake)
    with TestClient(main.app) as client:
        responses = [client.post(path, json=payload) for path, payload in _payloads()]

    assert [r.status_code for r in responses] == [401] * len(responses)
    assert calls == []


def test_expensive_generation_routes_require_selected_workspace(monkeypatch):
    async def no_workspace():
        return {
            "email": "generation@example.invalid",
            "user_id": "generation-user",
            "workspace_id": None,
            "workspace_role": "member",
            "is_admin": False,
        }

    rate_calls: list[str] = []
    async def rate_limit(request, workspace_id, *, video=False):
        rate_calls.append(workspace_id)

    calls: list[str] = []
    async def fake(*args, **kwargs):
        calls.append("called")
        return {"status": "test"}

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, no_workspace)
    monkeypatch.setattr(main, "workspace_generation_rate_limit", rate_limit)
    for name in ("viral_post_writer", "tiktok_script_writer", "render_vertical_video",
                 "grand_slam_offer_generator", "value_ladder_architect", "keyword_cluster_architect"):
        monkeypatch.setattr(main, name, fake)
    with TestClient(main.app) as client:
        responses = [client.post(path, json=payload) for path, payload in _payloads()]

    assert [r.status_code for r in responses] == [403] * len(responses)
    assert rate_calls == []
    assert calls == []


def test_generation_calls_are_workspace_scoped_and_rate_limited(monkeypatch):
    workspace_id = "generation-workspace-test"
    captured = []

    async def workspace_user():
        return {
            "email": "generation@example.invalid",
            "user_id": "generation-user",
            "workspace_id": workspace_id,
            "workspace_role": "owner",
            "is_admin": False,
        }

    async def capture_writer(topic, hooks, platform):
        captured.append((get_workspace_id(), topic, platform))
        return {"content": "draft", "provider": "test", "requires_review": True}

    rate_calls = []
    async def rate_limit(request, selected_workspace, *, video=False):
        rate_calls.append((selected_workspace, video))

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, workspace_user)
    monkeypatch.setattr(main, "workspace_generation_rate_limit", rate_limit)
    monkeypatch.setattr(main, "viral_post_writer", capture_writer)
    with TestClient(main.app) as client:
        response = client.post("/api/content/social", json={
            "topic": "A safe marketing guide",
            "hooks": [{"hook": "Useful tip"}],
            "platform": "linkedin",
        })

    assert response.status_code == 200, response.text
    assert captured == [(workspace_id, "A safe marketing guide", "linkedin")]
    assert rate_calls and rate_calls[0] == (workspace_id, False)


def test_video_uses_stricter_workspace_and_ip_rate_limit(monkeypatch):
    workspace_id = "video-workspace-test"

    async def workspace_user():
        return {
            "email": "video@example.invalid",
            "user_id": "video-user",
            "workspace_id": workspace_id,
            "workspace_role": "owner",
            "is_admin": False,
        }

    rate_calls = []
    async def rate_limit(request, selected_workspace, *, video=False):
        rate_calls.append((selected_workspace, video))

    async def fake_render(*args, **kwargs):
        return {"status": "rendered", "requires_license_review": True}

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, workspace_user)
    monkeypatch.setattr(main, "workspace_generation_rate_limit", rate_limit)
    monkeypatch.setattr(main, "render_vertical_video", fake_render)
    with TestClient(main.app) as client:
        response = client.post("/api/content/video", json={
            "script": "A short script with enough words to render safely.",
            "broll_query": "desk workspace",
        })

    assert response.status_code == 200, response.text
    assert rate_calls == [(workspace_id, True)]


@pytest.mark.asyncio
async def test_production_public_rate_limit_uses_atomic_redis_and_never_stores_raw_ip(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(main.settings, "app_env", "production")
    monkeypatch.setattr(main, "_public_rate_limit_redis", fake)

    request = _request("203.0.113.82")
    for _ in range(20):
        await main.public_rate_limit(request)

    with pytest.raises(HTTPException) as error:
        await main.public_rate_limit(request)

    assert error.value.status_code == 429
    assert len(fake.calls) == 21
    assert all(call[1] == 1 and call[3] == 3600 for call in fake.calls)
    assert all("203.0.113.82" not in call[2] for call in fake.calls)
    assert "INCR" in fake.calls[0][0]
    assert "EXPIRE" in fake.calls[0][0]


@pytest.mark.asyncio
async def test_production_rate_limit_fails_closed_when_redis_is_unavailable(monkeypatch):
    monkeypatch.setattr(main.settings, "app_env", "production")
    monkeypatch.setattr(main, "_public_rate_limit_redis", _BrokenRedis())
    monkeypatch.setattr(main, "_public_hits", {})

    with pytest.raises(HTTPException) as error:
        await main.public_rate_limit(_request())

    assert error.value.status_code == 503
    assert "unavailable" in error.value.detail.lower()
    assert main._public_hits == {}


@pytest.mark.asyncio
async def test_development_public_rate_limit_keeps_local_fallback(monkeypatch):
    monkeypatch.setattr(main.settings, "app_env", "development")
    monkeypatch.setattr(main, "_public_hits", {})
    request = _request("198.51.100.66")
    for _ in range(20):
        await main.public_rate_limit(request)

    with pytest.raises(HTTPException) as error:
        await main.public_rate_limit(request)

    assert error.value.status_code == 429


def test_keyword_clustering_rejects_unbounded_inputs(monkeypatch):
    async def workspace_user():
        return {
            "email": "keywords@example.invalid",
            "user_id": "keywords-user",
            "workspace_id": "keyword-workspace-test",
            "workspace_role": "owner",
            "is_admin": False,
        }

    calls = []
    async def rate_limit(*args, **kwargs):
        calls.append("rate")

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, workspace_user)
    monkeypatch.setattr(main, "workspace_generation_rate_limit", rate_limit)
    monkeypatch.setattr(main, "keyword_cluster_architect", lambda items: {"count": len(items)})
    with TestClient(main.app) as client:
        too_many = client.post("/api/content/keywords", json={"keywords": [f"keyword {i}" for i in range(501)]})
        too_long = client.post("/api/content/keywords", json={"keywords": ["x" * 501 for _ in range(50)]})

    assert too_many.status_code == 422
    assert too_long.status_code == 422
    assert calls == []
