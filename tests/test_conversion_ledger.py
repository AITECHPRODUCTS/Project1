from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, get_session
from backend.models import Conversion, ConversionLedgerEntry, Workspace
from backend.tenancy import workspace_scope


def _result(rows):
    return SimpleNamespace(all=Mock(return_value=rows))


def _override_session(session):
    async def override_get_session():
        yield session
    return override_get_session


def test_conversion_ledger_endpoint_preserves_currency_and_evidence_separation():
    observed = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
    rows = [
        SimpleNamespace(
            id="ledger-1",
            network="Acme",
            external_event_id="evt-1",
            click_id="click-1",
            entry_type="conversion",
            original_event_id=None,
            commission_amount=Decimal("1.230000"),
            revenue_amount=Decimal("10.120000"),
            currency="USD",
            status="approved",
            evidence_status="signed_webhook_verified",
            observed_at=observed,
            created_at=observed,
        )
    ]
    grouped = [
        ("USD", "legacy_unverified", 3, Decimal("9.100000"), Decimal("31.000000")),
        ("USD", "signed_webhook_verified", 1, Decimal("1.230000"), Decimal("10.120000")),
        ("EUR", "signed_webhook_verified", 2, Decimal("2.500000"), Decimal("20.000000")),
    ]
    session = SimpleNamespace(
        scalars=AsyncMock(return_value=_result(rows)),
        execute=AsyncMock(return_value=_result(grouped)),
    )
    main.app.dependency_overrides[get_session] = _override_session(session)
    main.app.dependency_overrides[main.require_auth] = lambda: {
        "user_id": "user-1", "workspace_id": "workspace-1", "email": "user@example.test"
    }
    try:
        with TestClient(main.app) as client:
            response = client.get("/api/finance/conversion-ledger")

        assert response.status_code == 200
        payload = response.json()
        assert payload["returned_count"] == 1
        assert payload["total_entry_count"] == 6
        assert payload["read_only"] is True
        assert payload["totals_by_currency_and_evidence"] == [
            {
                "currency": "USD",
                "evidence_status": "legacy_unverified",
                "entry_count": 3,
                "commission_total": "9.100000",
                "revenue_total": "31.000000",
            },
            {
                "currency": "USD",
                "evidence_status": "signed_webhook_verified",
                "entry_count": 1,
                "commission_total": "1.230000",
                "revenue_total": "10.120000",
            },
            {
                "currency": "EUR",
                "evidence_status": "signed_webhook_verified",
                "entry_count": 2,
                "commission_total": "2.500000",
                "revenue_total": "20.000000",
            },
        ]
        assert payload["data"][0]["commission_amount"] == "1.230000"
        assert payload["data"][0]["evidence_status"] == "signed_webhook_verified"
        statements = [session.scalars.await_args.args[0], session.execute.await_args.args[0]]
        for statement in statements:
            compiled = statement.compile()
            assert "workspace_id" in str(statement)
            assert "workspace-1" in compiled.params.values()
    finally:
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)


def test_conversion_ledger_endpoint_refuses_missing_workspace_without_querying():
    session = SimpleNamespace(scalars=AsyncMock(), execute=AsyncMock())
    main.app.dependency_overrides[get_session] = _override_session(session)
    main.app.dependency_overrides[main.require_auth] = lambda: {
        "user_id": "user-1", "workspace_id": None, "email": "user@example.test"
    }
    try:
        with TestClient(main.app) as client:
            response = client.get("/api/finance/conversion-ledger")
        assert response.status_code == 403
        session.scalars.assert_not_awaited()
        session.execute.assert_not_awaited()
    finally:
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)


def test_conversion_create_api_records_decimal_but_unverified_evidence(monkeypatch):
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=None),
        add=Mock(),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    main.app.dependency_overrides[get_session] = _override_session(session)
    body = {
        "network": "operator-import",
        "external_event_id": "imported-event-1",
        "commission": "0.100000",
        "revenue": "1.230000",
        "currency": "USD",
        "status": "pending",
    }
    try:
        with TestClient(main.app) as client:
            response = client.post("/api/analytics/conversions", json=body)
        assert response.status_code == 200
        assert response.json()["status"] == "recorded"
        assert session.add.call_count == 2
        added = [call.args[0] for call in session.add.call_args_list]
        conversion = next(value for value in added if isinstance(value, Conversion))
        ledger_entry = next(value for value in added if isinstance(value, ConversionLedgerEntry))
        assert conversion.commission == pytest.approx(0.1)
        assert ledger_entry.commission_amount == Decimal("0.100000")
        assert ledger_entry.revenue_amount == Decimal("1.230000")
        assert ledger_entry.evidence_status == "api_submitted_unverified"
    finally:
        main.app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_conversion_ledger_rows_cannot_be_mutated_or_deleted_through_orm():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            workspace = Workspace(name="Ledger workspace", slug="ledger-workspace-test")
            db.add(workspace)
            await db.commit()
            workspace_id = workspace.id

        with workspace_scope(workspace_id):
            async with sessions() as db:
                entry = ConversionLedgerEntry(
                    workspace_id=workspace_id,
                    network="test-network",
                    external_event_id="ledger-event-1",
                    entry_type="conversion",
                    commission_amount=Decimal("1.250000"),
                    revenue_amount=Decimal("9.500000"),
                    currency="USD",
                    status="approved",
                    evidence_status="signed_webhook_verified",
                    source_event_json={"test_fixture": True},
                )
                db.add(entry)
                await db.commit()
                entry_id = entry.id

                entry.status = "tampered"
                with pytest.raises(ValueError, match="append-only"):
                    await db.commit()
                await db.rollback()
                await db.refresh(entry)

                with pytest.raises(ValueError, match="append-only"):
                    await db.delete(entry)
                    await db.commit()
                await db.rollback()

                persisted = await db.get(ConversionLedgerEntry, entry_id)
                assert persisted is not None
                assert persisted.status == "approved"
                assert persisted.commission_amount == Decimal("1.250000")
    finally:
        await engine.dispose()
