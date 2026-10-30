from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from backend import main
from backend.database import get_session


def _result(rows):
    return SimpleNamespace(all=Mock(return_value=rows))


def _session_override(session):
    async def override_get_session():
        yield session
    return override_get_session


def test_finance_reconciliation_is_workspace_scoped_and_read_only():
    mail = SimpleNamespace(
        id="mail-1", network="Acme Network", commission=12.5, currency="USD",
        status="pending_verification",
    )
    conversion = SimpleNamespace(
        id="conversion-1", network="acme-network", commission=12.5, currency="USD",
        status="approved",
    )
    session = SimpleNamespace(
        scalars=AsyncMock(side_effect=[_result([mail]), _result([conversion])]),
    )
    user = {"user_id": "user-1", "workspace_id": "workspace-1", "email": "user@example.test"}
    main.app.dependency_overrides[get_session] = _session_override(session)
    main.app.dependency_overrides[main.require_auth] = lambda: user
    try:
        with TestClient(main.app) as client:
            response = client.get("/api/finance/reconciliation")

        assert response.status_code == 200
        payload = response.json()
        assert payload["workspace_id"] == "workspace-1"
        assert payload["data"][0]["reconciliation_status"] == "possible_match"
        assert payload["data"][0]["verified"] is False
        assert payload["data"][0]["payout_confirmed"] is False
        assert session.scalars.await_count == 2

        statements = [call.args[0] for call in session.scalars.await_args_list]
        for statement in statements:
            compiled = statement.compile()
            assert "workspace_id" in str(statement)
            assert "workspace-1" in compiled.params.values()
    finally:
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)


def test_finance_reconciliation_refuses_missing_workspace_without_querying_financial_data():
    session = SimpleNamespace(scalars=AsyncMock())
    main.app.dependency_overrides[get_session] = _session_override(session)
    main.app.dependency_overrides[main.require_auth] = lambda: {
        "user_id": "user-1", "workspace_id": None, "email": "user@example.test"
    }
    try:
        with TestClient(main.app) as client:
            response = client.get("/api/finance/reconciliation")

        assert response.status_code == 403
        assert session.scalars.await_count == 0
    finally:
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)
