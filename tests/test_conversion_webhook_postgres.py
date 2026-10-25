from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import uuid

import pytest
from decimal import Decimal
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError

from backend import main
from backend.database import SessionLocal, engine
from backend.models import Campaign, ClickEvent, Conversion, ConversionLedgerEntry, Workspace
from backend.tenancy import workspace_scope


SECRET = "postgres-conversion-test-secret-with-at-least-32-bytes"
NETWORK = "postgres-race-network"
ORIGINAL_EVENT_ID = "postgres-original-conversion"


def _signed_headers(body: bytes) -> dict[str, str]:
    digest = hmac.new(SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return {"X-Affiliate-Signature": f"sha256={digest}", "Content-Type": "application/json"}


@pytest.mark.asyncio
async def test_postgres_serializes_concurrent_full_conversion_reversals(monkeypatch):
    if not engine.url.drivername.startswith("postgresql"):
        pytest.skip("requires the dedicated PostgreSQL integration CI job")

    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", SECRET)
    workspace_id: str | None = None
    try:
        async with SessionLocal() as db:
            workspace = Workspace(
                name="Webhook race test",
                slug=f"webhook-race-{uuid.uuid4().hex}",
            )
            db.add(workspace)
            await db.commit()
            workspace_id = workspace.id

        click_id = uuid.uuid4().hex
        with workspace_scope(workspace_id):
            async with SessionLocal() as db:
                campaign = Campaign(
                    name="Webhook race test campaign",
                    niche="test",
                    primary_destination="https://example.com/offer",
                )
                db.add(campaign)
                await db.flush()
                click = ClickEvent(
                    click_id=click_id,
                    campaign_id=campaign.id,
                    destination_url="https://example.com/offer",
                    chosen_destination="primary",
                )
                db.add(click)
                db.add(
                    Conversion(
                        workspace_id=workspace_id,
                        network=NETWORK,
                        external_event_id=ORIGINAL_EVENT_ID,
                        click_id=click_id,
                        commission=1.25,
                        revenue=9.50,
                        currency="USD",
                        status="approved",
                    )
                )
                db.add(
                    ConversionLedgerEntry(
                        workspace_id=workspace_id,
                        network=NETWORK,
                        external_event_id=ORIGINAL_EVENT_ID,
                        click_id=click_id,
                        entry_type="conversion",
                        commission_amount=Decimal("1.250000"),
                        revenue_amount=Decimal("9.500000"),
                        currency="USD",
                        status="approved",
                        evidence_status="signed_webhook_verified",
                        source_event_json={"test_fixture": True},
                    )
                )
                await db.commit()

        payloads = [
            {
                "event_id": f"postgres-refund-{suffix}",
                "click_id": click_id,
                "status": "refunded",
                "original_event_id": ORIGINAL_EVENT_ID,
            }
            for suffix in ("a", "b")
        ]
        bodies = [json.dumps(p, separators=(",", ":")).encode("utf-8") for p in payloads]
        async with AsyncClient(
            transport=ASGITransport(app=main.app),
            base_url="http://test",
        ) as client:
            responses = await asyncio.gather(
                *(
                    client.post(
                        f"/api/webhooks/conversions/{NETWORK}",
                        content=body,
                        headers=_signed_headers(body),
                    )
                    for body in bodies
                )
            )

        assert all(response.status_code == 200 for response in responses)
        outcomes = [response.json()["status"] for response in responses]
        assert outcomes.count("recorded") == 1
        assert outcomes.count("duplicate_reversal_ignored") == 1

        with workspace_scope(workspace_id):
            async with SessionLocal() as db:
                rows = list((await db.scalars(select(Conversion))).all())
                assert len(rows) == 2
                original = next(row for row in rows if row.external_event_id == ORIGINAL_EVENT_ID)
                reversal = next(row for row in rows if row.external_event_id != ORIGINAL_EVENT_ID)
                assert original.status == "reversed"
                assert reversal.status == "reversed"
                assert reversal.commission == pytest.approx(-1.25)
                assert reversal.revenue == pytest.approx(-9.50)
                assert sum(row.commission for row in rows) == pytest.approx(0.0)
                ledger_rows = list((await db.scalars(select(ConversionLedgerEntry))).all())
                assert len(ledger_rows) == 2
                assert sum((entry.commission_amount for entry in ledger_rows), Decimal("0")) == Decimal("0.000000")
                reversal_entry = next(entry for entry in ledger_rows if entry.external_event_id != ORIGINAL_EVENT_ID)
                assert reversal_entry.entry_type == "reversal"
                assert reversal_entry.evidence_status == "signed_webhook_verified"
    finally:
        if workspace_id:
            async with engine.begin() as connection:
                await connection.execute(
                    delete(ConversionLedgerEntry).where(ConversionLedgerEntry.workspace_id == workspace_id)
                )
                await connection.execute(
                    delete(Conversion).where(Conversion.workspace_id == workspace_id)
                )
                await connection.execute(
                    delete(ClickEvent).where(ClickEvent.workspace_id == workspace_id)
                )
                await connection.execute(
                    delete(Campaign).where(Campaign.workspace_id == workspace_id)
                )
                await connection.execute(delete(Workspace).where(Workspace.id == workspace_id))


@pytest.mark.asyncio
async def test_postgres_conversion_ledger_rejects_direct_update_and_delete(monkeypatch):
    if not engine.url.drivername.startswith("postgresql"):
        pytest.skip("requires the dedicated PostgreSQL integration CI job")

    workspace_id: str | None = None
    entry_id: str | None = None
    try:
        async with SessionLocal() as db:
            workspace = Workspace(
                name="Ledger immutability test",
                slug=f"ledger-immutable-{uuid.uuid4().hex}",
            )
            db.add(workspace)
            await db.commit()
            workspace_id = workspace.id

        with workspace_scope(workspace_id):
            async with SessionLocal() as db:
                entry = ConversionLedgerEntry(
                    workspace_id=workspace_id,
                    network="ledger-immutability-network",
                    external_event_id=uuid.uuid4().hex,
                    entry_type="conversion",
                    commission_amount=Decimal("2.340000"),
                    revenue_amount=Decimal("10.000000"),
                    currency="USD",
                    status="approved",
                    evidence_status="signed_webhook_verified",
                    source_event_json={"test_fixture": True},
                )
                db.add(entry)
                await db.commit()
                entry_id = entry.id

        with pytest.raises(DBAPIError):
            async with engine.begin() as connection:
                await connection.execute(
                    update(ConversionLedgerEntry)
                    .where(ConversionLedgerEntry.id == entry_id)
                    .values(status="tampered")
                )

        with pytest.raises(DBAPIError):
            async with engine.begin() as connection:
                await connection.execute(
                    delete(ConversionLedgerEntry).where(ConversionLedgerEntry.id == entry_id)
                )

        async with SessionLocal() as db:
            persisted = await db.get(ConversionLedgerEntry, entry_id)
            assert persisted is not None
            assert persisted.status == "approved"
            assert persisted.commission_amount == Decimal("2.340000")
    finally:
        if workspace_id:
            async with engine.begin() as connection:
                await connection.execute(
                    delete(ConversionLedgerEntry).where(ConversionLedgerEntry.workspace_id == workspace_id)
                )
                await connection.execute(delete(Workspace).where(Workspace.id == workspace_id))
