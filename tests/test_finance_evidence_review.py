from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from backend import main
from backend.database import get_session


def _override(session):
    async def override_get_session():
        yield session
    return override_get_session


def _evidence():
    return SimpleNamespace(
        id="mail-1", workspace_id="workspace-1", network="Acme Network",
        commission=12.5, currency="USD", status="pending_verification",
        evidence_json={"message_id": "message-1"},
    )


def _conversion(*, commission=12.5, status="approved", workspace_id="workspace-1"):
    return SimpleNamespace(
        id="conversion-1", workspace_id=workspace_id, network="acme-network",
        commission=commission, currency="USD", status=status,
    )


def _setup(session, user=None):
    main.app.dependency_overrides[get_session] = _override(session)
    main.app.dependency_overrides[main.require_auth] = lambda: user or {
        "user_id": "user-1", "workspace_id": "workspace-1",
        "email": "operator@example.test", "workspace_role": "owner",
    }


def _teardown():
    main.app.dependency_overrides.pop(get_session, None)
    main.app.dependency_overrides.pop(main.require_auth, None)


def test_finance_review_accepts_matching_conversion_without_confirming_payout():
    evidence = _evidence()
    conversion = _conversion()
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[evidence, conversion]),
        add=Mock(),
        commit=AsyncMock(),
    )
    _setup(session)
    try:
        with TestClient(main.app) as client:
            response = client.patch(
                "/api/finance/mail-commissions/mail-1/review",
                json={
                    "decision": "matched_to_conversion",
                    "candidate_conversion_id": "conversion-1",
                    "note": "Provider network and amount reviewed",
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "matched_to_conversion"
        assert payload["payout_confirmed"] is False
        assert payload["transfers_initiated"] is False
        assert evidence.status == "matched_to_conversion"
        assert evidence.evidence_json["operator_review"]["candidate_conversion_id"] == "conversion-1"
        session.add.assert_called_once()
        audit = session.add.call_args.args[0]
        assert audit.workspace_id == "workspace-1"
        assert audit.action == "finance.commission_evidence.reviewed"
        session.commit.assert_awaited_once()
    finally:
        _teardown()


def test_finance_review_rejects_nonmatching_conversion_without_mutation():
    evidence = _evidence()
    conversion = _conversion(commission=99.0)
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[evidence, conversion]),
        add=Mock(),
        commit=AsyncMock(),
    )
    _setup(session)
    try:
        with TestClient(main.app) as client:
            response = client.patch(
                "/api/finance/mail-commissions/mail-1/review",
                json={
                    "decision": "matched_to_conversion",
                    "candidate_conversion_id": "conversion-1",
                },
            )

        assert response.status_code == 422
        assert evidence.status == "pending_verification"
        session.add.assert_not_called()
        session.commit.assert_not_awaited()
    finally:
        _teardown()


def test_finance_review_rejects_cross_workspace_candidate():
    evidence = _evidence()
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[evidence, None]),
        add=Mock(),
        commit=AsyncMock(),
    )
    _setup(session)
    try:
        with TestClient(main.app) as client:
            response = client.patch(
                "/api/finance/mail-commissions/mail-1/review",
                json={
                    "decision": "matched_to_conversion",
                    "candidate_conversion_id": "conversion-from-other-workspace",
                },
            )

        assert response.status_code == 404
        session.add.assert_not_called()
        session.commit.assert_not_awaited()
    finally:
        _teardown()


def test_finance_review_requires_workspace_before_database_access():
    session = SimpleNamespace(scalar=AsyncMock(), add=Mock(), commit=AsyncMock())
    _setup(session, {"user_id": "user-1", "workspace_id": None, "email": "operator@example.test", "workspace_role": "owner"})
    try:
        with TestClient(main.app) as client:
            response = client.patch(
                "/api/finance/mail-commissions/mail-1/review",
                json={"decision": "not_a_match"},
            )

        assert response.status_code == 403
        session.scalar.assert_not_awaited()
        session.commit.assert_not_awaited()
    finally:
        _teardown()
