from __future__ import annotations

from fastapi.testclient import TestClient

from backend import main
from backend.database import get_session


class _FakeReadinessSession:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        if self.error is not None:
            raise self.error
        return object()


def _override_session(monkeypatch, fake_session: _FakeReadinessSession) -> None:
    async def provide_session():
        yield fake_session

    monkeypatch.setitem(main.app.dependency_overrides, get_session, provide_session)


def test_readiness_returns_ready_when_database_query_succeeds(monkeypatch):
    session = _FakeReadinessSession()
    _override_session(monkeypatch, session)
    client = TestClient(main.app)
    try:
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ready",
            "service": "affiliate-os-api",
            "dependencies": {"database": "ok"},
        }
        assert session.statement is not None
    finally:
        client.close()


def test_readiness_fails_closed_without_leaking_database_error(monkeypatch):
    session = _FakeReadinessSession(RuntimeError("postgres://operator:private-password@db.internal"))
    _override_session(monkeypatch, session)
    client = TestClient(main.app)
    try:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"detail": "service_not_ready"}
        assert "private-password" not in response.text
        assert "db.internal" not in response.text
    finally:
        client.close()
