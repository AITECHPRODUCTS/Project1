from __future__ import annotations

import json

import pytest
from starlette.websockets import WebSocketDisconnect

from backend import main
from backend.core.events import EventHub
from backend.core.state_machine import WorkflowRunner


class _FakeSocket:
    def __init__(self, session: dict | None = None):
        self.scope = {"session": session or {}}
        self.accepted = False
        self.closed: dict | None = None
        self.messages: list[dict] = []

    async def accept(self):
        self.accepted = True

    async def close(self, code: int, reason: str):
        self.closed = {"code": code, "reason": reason}

    async def send_text(self, message: str):
        self.messages.append(json.loads(message))

    async def receive_text(self):
        raise WebSocketDisconnect(code=1000)


class _FakeDatabase:
    def __init__(self, result=None):
        self.result = result

    async def scalar(self, statement):
        return self.result


class _FakeDatabaseContext:
    def __init__(self, result=None):
        self.db = _FakeDatabase(result)

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_event_hub_delivers_workspace_events_only_to_matching_connections():
    hub = EventHub()
    tenant_a = _FakeSocket()
    tenant_b = _FakeSocket()
    unscoped = _FakeSocket()
    await hub.connect(tenant_a, "workspace-a")
    await hub.connect(tenant_b, "workspace-b")
    await hub.connect(unscoped, None)

    await hub.publish({
        "event": "HITL_ALERT",
        "workspace_id": "workspace-a",
        "session_id": "workflow-1",
        "message": "verification required",
    })

    assert tenant_a.accepted is True
    assert tenant_b.accepted is True
    assert len(tenant_a.messages) == 1
    assert tenant_a.messages[0]["workspace_id"] == "workspace-a"
    assert tenant_b.messages == []
    assert unscoped.messages == []


@pytest.mark.asyncio
async def test_event_hub_drops_legacy_events_without_workspace_scope():
    hub = EventHub()
    tenant_a = _FakeSocket()
    await hub.connect(tenant_a, "workspace-a")

    await hub.publish({"event": "WORKFLOW_STATUS", "session_id": "legacy-workflow"})

    assert tenant_a.messages == []


@pytest.mark.asyncio
async def test_workflow_event_emitter_adds_scope_and_drops_unscoped_event(monkeypatch):
    emitted: list[dict] = []

    async def capture(payload):
        emitted.append(payload)

    monkeypatch.setattr("backend.core.state_machine.hub.publish", capture)
    runner = WorkflowRunner()

    await runner._emit(
        {"metadata": {"workspace_id": "workspace-a"}},
        {"event": "WORKFLOW_STATUS", "session_id": "workflow-a"},
    )
    await runner._emit(
        {"metadata": {}},
        {"event": "WORKFLOW_STATUS", "session_id": "unscoped-workflow"},
    )

    assert len(emitted) == 1
    assert emitted[0]["workspace_id"] == "workspace-a"


@pytest.mark.asyncio
async def test_websocket_rejects_revoked_workspace_membership(monkeypatch):
    monkeypatch.setattr(main.settings, "app_env", "production")
    monkeypatch.setattr(main, "SessionLocal", lambda: _FakeDatabaseContext(None))
    socket = _FakeSocket({
        "user": {
            "user_id": "revoked-user",
            "workspace_id": "revoked-workspace",
            "is_admin": False,
        }
    })

    await main.websocket(socket)

    assert socket.closed == {
        "code": 1008,
        "reason": "Workspace membership is no longer active",
    }
    assert socket.accepted is False
