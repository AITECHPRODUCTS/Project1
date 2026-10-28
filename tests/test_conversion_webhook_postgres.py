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
from backend.config import get_settings
from backend.database import SessionLocal, engine
from backend.models import Campaign, ClickEvent, Conversion, ConversionLedgerEntry, PerformanceMemory, Workspace
from backend.services.s6_s8_analytics import self_improver_loop
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
        # PostgreSQL CI provisions a disposable database per run. Leave UUID-scoped
        # fixtures intact rather than bypassing the append-only ledger trigger.
        await engine.dispose()


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
        # PostgreSQL CI provisions a disposable database per run; immutable ledger
        # observations are intentionally not deleted during test teardown.
        await engine.dispose()



@pytest.mark.asyncio
async def test_postgres_partial_reversal_caps_and_full_reversal_offsets_remaining_balance(monkeypatch):
    if not engine.url.drivername.startswith("postgresql"):
        pytest.skip("requires the dedicated PostgreSQL integration CI job")

    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", SECRET)
    workspace_id: str | None = None
    try:
        async with SessionLocal() as db:
            workspace = Workspace(
                name="Partial reversal ledger test",
                slug=f"partial-reversal-{uuid.uuid4().hex}",
            )
            db.add(workspace)
            await db.commit()
            workspace_id = workspace.id

        click_id = uuid.uuid4().hex
        with workspace_scope(workspace_id):
            async with SessionLocal() as db:
                campaign = Campaign(
                    name="Partial reversal campaign",
                    niche="test",
                    primary_destination="https://example.com/offer",
                )
                db.add(campaign)
                await db.flush()
                db.add(ClickEvent(
                    click_id=click_id,
                    campaign_id=campaign.id,
                    destination_url="https://example.com/offer",
                    chosen_destination="primary",
                ))
                db.add(Conversion(
                    workspace_id=workspace_id,
                    network=NETWORK,
                    external_event_id=ORIGINAL_EVENT_ID,
                    click_id=click_id,
                    commission=1.25,
                    revenue=9.50,
                    currency="USD",
                    status="approved",
                ))
                db.add(ConversionLedgerEntry(
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
                ))
                await db.commit()

        partial_payload = {
            "event_id": "postgres-partial-refund",
            "click_id": click_id,
            "status": "partial_refund",
            "original_event_id": ORIGINAL_EVENT_ID,
            "commission": "0.50",
            "revenue": "2.00",
            "currency": "USD",
        }
        partial_body = json.dumps(partial_payload, separators=(",", ":")).encode("utf-8")
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            partial_response = await client.post(
                f"/api/webhooks/conversions/{NETWORK}",
                content=partial_body,
                headers=_signed_headers(partial_body),
            )
        assert partial_response.status_code == 200
        assert partial_response.json()["commission_adjustment"] == -0.5
        assert partial_response.json()["revenue_adjustment"] == -2.0
        assert partial_response.json()["remaining_commission"] == "0.75"
        assert partial_response.json()["remaining_revenue"] == "7.5"

        full_payload = {
            "event_id": "postgres-final-refund",
            "click_id": click_id,
            "status": "refunded",
            "original_event_id": ORIGINAL_EVENT_ID,
            "currency": "USD",
        }
        full_body = json.dumps(full_payload, separators=(",", ":")).encode("utf-8")
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            full_response = await client.post(
                f"/api/webhooks/conversions/{NETWORK}",
                content=full_body,
                headers=_signed_headers(full_body),
            )
        assert full_response.status_code == 200
        assert full_response.json()["commission_adjustment"] == -0.75
        assert full_response.json()["revenue_adjustment"] == -7.5
        assert full_response.json()["remaining_commission"] == "0"
        assert full_response.json()["remaining_revenue"] == "0"

        with workspace_scope(workspace_id):
            async with SessionLocal() as db:
                conversions = list((await db.scalars(select(Conversion))).all())
                original = next(row for row in conversions if row.external_event_id == ORIGINAL_EVENT_ID)
                partial = next(row for row in conversions if row.external_event_id == "postgres-partial-refund")
                full = next(row for row in conversions if row.external_event_id == "postgres-final-refund")
                assert original.status == "reversed"
                assert partial.status == "partially_reversed"
                assert full.status == "reversed"
                assert sum(row.commission for row in conversions) == pytest.approx(0.0)
                assert sum(row.revenue for row in conversions) == pytest.approx(0.0)

                ledger_rows = list((await db.scalars(select(ConversionLedgerEntry))).all())
                assert len(ledger_rows) == 3
                assert sum((row.commission_amount for row in ledger_rows), Decimal("0")) == Decimal("0.000000")
                assert sum((row.revenue_amount for row in ledger_rows), Decimal("0")) == Decimal("0.000000")
    finally:
        await engine.dispose()



@pytest.mark.asyncio
async def test_postgres_learning_nets_partial_reversal_and_excludes_reversed_outcomes(monkeypatch):
    if not engine.url.drivername.startswith("postgresql"):
        pytest.skip("requires the dedicated PostgreSQL integration CI job")

    settings = get_settings()
    monkeypatch.setattr(settings, "min_conversions_for_learning", 1)
    monkeypatch.setattr(settings, "min_hook_conversion_rate", 0.0)
    workspace_id: str | None = None
    try:
        async with SessionLocal() as db:
            workspace = Workspace(
                name="PostgreSQL learning reversal test",
                slug=f"learning-reversal-{uuid.uuid4().hex}",
            )
            db.add(workspace)
            await db.commit()
            workspace_id = workspace.id

        hook = "postgres-partial-refund-hook"
        click_id = uuid.uuid4().hex
        with workspace_scope(workspace_id):
            async with SessionLocal() as db:
                campaign = Campaign(
                    name="Learning reversal campaign",
                    niche="test",
                    primary_destination="https://example.com/offer",
                )
                db.add(campaign)
                await db.flush()
                db.add(ClickEvent(
                    click_id=click_id,
                    campaign_id=campaign.id,
                    destination_url="https://example.com/offer",
                    chosen_destination="primary",
                    utm_json={"utm_content": hook},
                ))
                db.add_all([
                    Conversion(
                        workspace_id=workspace_id,
                        network=NETWORK,
                        external_event_id="learning-partial-original",
                        click_id=click_id,
                        commission=1.25,
                        revenue=10.0,
                        hook=hook,
                        status="partially_reversed",
                        event_json={"reversal": False},
                    ),
                    Conversion(
                        workspace_id=workspace_id,
                        network=NETWORK,
                        external_event_id="learning-partial-event",
                        click_id=click_id,
                        commission=-0.50,
                        revenue=-2.0,
                        hook=hook,
                        status="partially_reversed",
                        event_json={"reversal": True, "partial_reversal": True},
                    ),
                    Conversion(
                        workspace_id=workspace_id,
                        network=NETWORK,
                        external_event_id="learning-fully-reversed",
                        click_id=click_id,
                        commission=5.0,
                        revenue=50.0,
                        hook=hook,
                        status="reversed",
                        event_json={"reversal": False},
                    ),
                ])
                db.add_all([
                    ConversionLedgerEntry(
                        workspace_id=workspace_id,
                        network=NETWORK,
                        external_event_id="learning-partial-original",
                        click_id=click_id,
                        entry_type="conversion",
                        commission_amount=Decimal("1.250000"),
                        revenue_amount=Decimal("10.000000"),
                        currency="USD",
                        status="partially_reversed",
                        evidence_status="signed_webhook_verified",
                        source_event_json={"test_fixture": True},
                    ),
                    ConversionLedgerEntry(
                        workspace_id=workspace_id,
                        network=NETWORK,
                        external_event_id="learning-partial-event",
                        click_id=click_id,
                        entry_type="reversal",
                        original_event_id="learning-partial-original",
                        commission_amount=Decimal("-0.500000"),
                        revenue_amount=Decimal("-2.000000"),
                        currency="USD",
                        status="partially_reversed",
                        evidence_status="signed_webhook_verified",
                        source_event_json={"test_fixture": True},
                    ),
                    ConversionLedgerEntry(
                        workspace_id=workspace_id,
                        network=NETWORK,
                        external_event_id="learning-fully-reversed",
                        click_id=click_id,
                        entry_type="conversion",
                        commission_amount=Decimal("5.000000"),
                        revenue_amount=Decimal("50.000000"),
                        currency="USD",
                        status="reversed",
                        evidence_status="signed_webhook_verified",
                        source_event_json={"test_fixture": True},
                    ),
                    ConversionLedgerEntry(
                        workspace_id=workspace_id,
                        network=NETWORK,
                        external_event_id="learning-full-reversal-event",
                        click_id=click_id,
                        entry_type="reversal",
                        original_event_id="learning-fully-reversed",
                        commission_amount=Decimal("-5.000000"),
                        revenue_amount=Decimal("-50.000000"),
                        currency="USD",
                        status="reversed",
                        evidence_status="signed_webhook_verified",
                        source_event_json={"test_fixture": True},
                    ),
                ])
                await db.commit()

        result = await self_improver_loop(workspace_id=workspace_id)
        assert result["conversions_scanned"] == 1
        assert result["performance_memory_candidates_saved"] == 1
        assert len(result["learned_hooks"]) == 1
        assert result["learned_hooks"][0]["hook"] == hook
        assert result["learned_hooks"][0]["conversions"] == 1
        assert result["learned_hooks"][0]["commission"] == pytest.approx(0.75)

        with workspace_scope(workspace_id):
            async with SessionLocal() as db:
                memory = await db.scalar(
                    select(PerformanceMemory).where(PerformanceMemory.hook == hook)
                )
                assert memory is not None
                assert memory.conversion_count == 1
                assert memory.commission_recorded == pytest.approx(0.75)
    finally:
        # PostgreSQL CI provisions a disposable database per run; the append-only
        # ledger intentionally retains these UUID-scoped observations.
        await engine.dispose()
