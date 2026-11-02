from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import main
from backend.database import Base, get_session
from backend.models import (
    AuditLog,
    ConversionLedgerEntry,
    ProviderAccountConnection,
    ProviderOrderObservation,
    ProviderOrderReconciliationReview,
    Workspace,
)
from backend.tenancy import workspace_scope


def _client(tmp_path, *, role="owner", order_type="SALE", account_amount="12.500000", ledger_amount="12.500000", attribution="matched_clickbank_tid"):
    engine=create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'clickbank-reconciliation.db'}")
    sessions=async_sessionmaker(engine,expire_on_commit=False)
    click_id="a"*32

    async def seed():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            workspace=Workspace(name="ClickBank reconcile",slug="clickbank-reconcile")
            db.add(workspace)
            await db.flush()
            provider=ProviderAccountConnection(
                workspace_id=workspace.id,provider_id="clickbank",status="connected_read_only",
                credential_ciphertext="encrypted",credential_fingerprint="f"*64,
                credential_key_version=1,account_nicknames_json=["creator-main"],
                capabilities_json=["orders.read"],
            )
            db.add(provider)
            await db.flush()
            observation=ProviderOrderObservation(
                workspace_id=workspace.id,connection_id=provider.id,provider_id="clickbank",
                event_key="e"*64,source_fingerprint="f"*64,click_id=click_id if attribution=="matched_clickbank_tid" else None,
                attribution_status=attribution,account_nickname="creator-main",receipt="CB-RECEIPT-1",
                transaction_time="2026-10-20T12:00:00+00:00",transaction_type=order_type,role="AFFILIATE",
                product_title="Sample product",currency="USD",account_amount=Decimal(account_amount),
                line_item_status="ACTIVE",evidence_status="provider_reported_unreconciled",
            )
            ledger=ConversionLedgerEntry(
                workspace_id=workspace.id,network="clickbank",external_event_id="cb-event-1",
                click_id=click_id,entry_type="conversion",original_event_id=None,
                commission_amount=Decimal(ledger_amount),revenue_amount=Decimal("49.000000"),
                currency="USD",status="approved",evidence_status="signed_webhook_verified",
                source_event_json={"source":"signed-webhook-test"},
            )
            db.add_all([observation,ledger])
            await db.commit()
            return workspace.id,observation.id,ledger.id,ledger.commission_amount

    workspace_id,observation_id,ledger_id,original_amount=asyncio.run(seed())
    user={
        "user_id":"owner-user","workspace_id":workspace_id,"email":"owner@example.test",
        "workspace_role":role,"is_admin":False,
    }

    async def override_session():
        async with sessions() as db:
            yield db
    async def override_auth():
        return user
    async def override_admin():
        if role not in {"owner","admin"}:
            from fastapi import HTTPException
            raise HTTPException(403,"Workspace owner/admin permission required")
        return user

    main.app.dependency_overrides[get_session]=override_session
    main.app.dependency_overrides[main.require_auth]=override_auth
    main.app.dependency_overrides[main.require_admin]=override_admin
    return engine,sessions,workspace_id,observation_id,ledger_id,original_amount,TestClient(main.app)


def _cleanup(engine,client):
    main.app.dependency_overrides.pop(get_session,None)
    main.app.dependency_overrides.pop(main.require_auth,None)
    main.app.dependency_overrides.pop(main.require_admin,None)
    client.close()
    asyncio.run(engine.dispose())


def test_clickbank_reconciliation_queue_only_offers_exact_signed_currency_and_amount_match(tmp_path):
    engine,sessions,workspace_id,observation_id,ledger_id,_,client=_client(tmp_path)
    try:
        with client:
            response=client.get("/api/finance/provider-orders/reconciliation")
        assert response.status_code==200,response.text
        result=response.json()
        assert result["read_only"] is True
        assert result["commission_ledger_mutated"] is False
        assert result["payout_confirmed"] is False
        row=result["data"][0]
        assert row["observation_id"]==observation_id
        assert row["candidate_count"]==1
        assert row["candidates"][0]["ledger_entry_id"]==ledger_id
        assert row["candidates"][0]["evidence_status"]=="signed_webhook_verified"
        assert row["match_block_reason"] is None
    finally:
        _cleanup(engine,client)


def test_clickbank_reconciliation_review_is_append_only_and_does_not_mutate_commission_ledger(tmp_path):
    engine,sessions,workspace_id,observation_id,ledger_id,original_amount,client=_client(tmp_path)
    body={
        "decision":"matched_to_conversion",
        "candidate_ledger_entry_id":ledger_id,
        "note":"Verified the provider receipt against the signed conversion event",
    }
    try:
        with client:
            response=client.patch(f"/api/finance/provider-orders/{observation_id}/review",json=body)
            assert response.status_code==200,response.text
            result=response.json()
            assert result["decision"]=="matched_to_conversion"
            assert result["commission_ledger_mutated"] is False
            assert result["payout_confirmed"] is False
            assert result["transfers_initiated"] is False
            duplicate=client.patch(f"/api/finance/provider-orders/{observation_id}/review",json=body)
            assert duplicate.status_code==409
        async def inspect():
            with workspace_scope(workspace_id):
                async with sessions() as db:
                    review=await db.scalar(select(ProviderOrderReconciliationReview))
                    ledger=await db.scalar(select(ConversionLedgerEntry).where(ConversionLedgerEntry.id==ledger_id))
                    audit=await db.scalar(select(AuditLog).where(AuditLog.action=="finance.provider_order_reconciliation.reviewed"))
                    return review,ledger,audit
        review,ledger,audit=asyncio.run(inspect())
        assert review is not None and review.ledger_entry_id==ledger_id
        assert ledger.commission_amount==original_amount==Decimal("12.500000")
        assert audit is not None and audit.details_json["payout_confirmed"] is False
        async def reject_mutation():
            with workspace_scope(workspace_id):
                async with sessions() as db:
                    row=await db.scalar(select(ProviderOrderReconciliationReview))
                    row.note="tampered"
                    with pytest.raises(ValueError,match="append-only"):
                        await db.commit()
                    await db.rollback()
        asyncio.run(reject_mutation())
    finally:
        _cleanup(engine,client)


def test_clickbank_reconciliation_rejects_amount_or_transaction_mismatch(tmp_path):
    engine,sessions,workspace_id,observation_id,ledger_id,_,client=_client(
        tmp_path,order_type="RFND",account_amount="12.500000",ledger_amount="12.500000"
    )
    body={"decision":"matched_to_conversion","candidate_ledger_entry_id":ledger_id}
    try:
        with client:
            queue=client.get("/api/finance/provider-orders/reconciliation").json()
            assert queue["data"][0]["candidate_count"]==0
            assert queue["data"][0]["match_block_reason"]=="non_sale_transaction"
            denied=client.patch(f"/api/finance/provider-orders/{observation_id}/review",json=body)
            assert denied.status_code==422
        async def no_review():
            with workspace_scope(workspace_id):
                async with sessions() as db:
                    return await db.scalar(select(ProviderOrderReconciliationReview))
        assert asyncio.run(no_review()) is None
    finally:
        _cleanup(engine,client)


def test_clickbank_reconciliation_rejects_equal_click_with_different_amount(tmp_path):
    engine,sessions,workspace_id,observation_id,ledger_id,_,client=_client(
        tmp_path,account_amount="12.500000",ledger_amount="12.510000"
    )
    try:
        with client:
            queue=client.get("/api/finance/provider-orders/reconciliation").json()
            assert queue["data"][0]["candidate_count"]==0
            denied=client.patch(f"/api/finance/provider-orders/{observation_id}/review",json={
                "decision":"matched_to_conversion","candidate_ledger_entry_id":ledger_id,
            })
            assert denied.status_code==422
    finally:
        _cleanup(engine,client)


def test_clickbank_reconciliation_review_requires_workspace_admin(tmp_path):
    engine,sessions,workspace_id,observation_id,ledger_id,_,client=_client(tmp_path,role="member")
    try:
        with client:
            denied=client.patch(f"/api/finance/provider-orders/{observation_id}/review",json={
                "decision":"matched_to_conversion","candidate_ledger_entry_id":ledger_id,
            })
        assert denied.status_code==403
    finally:
        _cleanup(engine,client)
