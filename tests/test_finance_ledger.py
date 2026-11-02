from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from backend import main
from backend.database import get_session


def _result(rows):
    return SimpleNamespace(all=Mock(return_value=rows))


def _override_session(session):
    async def override_get_session():
        yield session
    return override_get_session


def test_finance_ledger_aggregates_all_commissions_by_currency_in_workspace():
    rows = [
        SimpleNamespace(
            id="usd-1", network="Acme", external_event_id="event-1", commission=5.0,
            revenue=20.0, currency="USD", status="approved", utm_campaign=None, created_at=None,
        ),
        SimpleNamespace(
            id="eur-1", network="Acme", external_event_id="event-2", commission=10.0,
            revenue=30.0, currency="EUR", status="approved", utm_campaign=None, created_at=None,
        ),
    ]
    session = SimpleNamespace(
        scalars=AsyncMock(return_value=_result(rows)),
        execute=AsyncMock(return_value=_result([("USD", 105.0), ("EUR", 210.0)])),
    )
    main.app.dependency_overrides[get_session] = _override_session(session)
    main.app.dependency_overrides[main.require_auth] = lambda: {
        "user_id": "user-1", "workspace_id": "workspace-1", "email": "user@example.test"
    }
    try:
        with TestClient(main.app) as client:
            response = client.get("/api/finance/ledger")

        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] == 2
        assert payload["total_commission_recorded"] == 105.0
        assert payload["total_commission_recorded_currency"] == "USD"
        assert payload["totals_by_currency"] == {"USD": 105.0, "EUR": 210.0}
        assert len(payload["data"]) == 2

        statements = [
            session.scalars.await_args.args[0],
            session.execute.await_args.args[0],
        ]
        for statement in statements:
            compiled = statement.compile()
            assert "workspace_id" in str(statement)
            assert "workspace-1" in compiled.params.values()
    finally:
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)


def test_finance_ledger_refuses_missing_workspace_without_querying():
    session = SimpleNamespace(scalars=AsyncMock(), execute=AsyncMock())
    main.app.dependency_overrides[get_session] = _override_session(session)
    main.app.dependency_overrides[main.require_auth] = lambda: {
        "user_id": "user-1", "workspace_id": None, "email": "user@example.test"
    }
    try:
        with TestClient(main.app) as client:
            response = client.get("/api/finance/ledger")

        assert response.status_code == 403
        session.scalars.assert_not_awaited()
        session.execute.assert_not_awaited()
    finally:
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)
