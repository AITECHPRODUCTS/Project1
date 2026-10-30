from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import main
from backend.database import Base, get_session
from backend.models import ProviderAccountConnection, ProviderOrderObservation, Workspace
from backend.services import clickbank_accounts as clickbank
from backend.tenancy import workspace_scope


def _provider_order(receipt="CB123456", transaction_type="SALE", amount="12.50", sku="ITEM-1"):
    return {
        "transactionTime":"2026-10-20T12:00:00Z",
        "receipt":receipt,
        "transactionType":transaction_type,
        "currency":"USD",
        "vendor":"vendor-main",
        "affiliate":"creator-main",
        "role":"AFFILIATE",
        "email":"buyer@example.invalid",
        "firstName":"Buyer",
        "lastName":"Name",
        "postalCode":"10000",
        "customerContactInfo":[{"field":"phone","value":"555-0100"}],
        "lineItemData":[{
            "itemNo":sku,
            "productTitle":"Sample product",
            "customerAmount":"49.00",
            "accountAmount":amount,
            "lineItemType":"STANDARD",
            "status":"ACTIVE",
            "recurring":False,
            "shippable":False,
        }],
    }


@pytest.mark.asyncio
async def test_orders_list_paginates_206_and_minimizes_customer_data(monkeypatch):
    calls=[]
    async def fake_page(api_key, **kwargs):
        calls.append(kwargs)
        if kwargs["page"]==1:
            return {"orderData":[_provider_order()]},206
        return {"orderData":[_provider_order(receipt="CB123457",transaction_type="RFND",amount="-12.50")]},200
    monkeypatch.setattr(clickbank,"_request_clickbank_orders_page",fake_page)

    report=await clickbank.fetch_clickbank_order_transactions(
        "API-"+"x"*40,
        account="creator-main",
        start_date=date(2026,10,1),
        end_date=date(2026,10,30),
        start_page=1,
        max_pages=5,
    )
    assert len(calls)==2
    assert [call["page"] for call in calls]==[1,2]
    assert all(call["account"]=="creator-main" for call in calls)
    assert report["pages_retrieved"]==2 and report["has_more"] is False
    assert len(report["transactions"])==2
    row=report["transactions"][0]
    assert row["account_amount"]=="12.50"
    assert row["role"]=="AFFILIATE"
    assert row["product_title"]=="Sample product"
    assert "email" not in row and "firstName" not in row and "postalCode" not in row
    assert "customerContactInfo" not in row


@pytest.mark.asyncio
async def test_orders_list_returns_resume_page_when_page_limit_is_reached(monkeypatch):
    async def partial(*args,**kwargs):
        return {"orderData":[_provider_order(receipt="CB12345"+str(kwargs["page"]))]},206
    monkeypatch.setattr(clickbank,"_request_clickbank_orders_page",partial)
    report=await clickbank.fetch_clickbank_order_transactions(
        "API-"+"x"*40,account="creator-main",
        start_date=date(2026,10,1),end_date=date(2026,10,30),
        start_page=11,max_pages=2,
    )
    assert report["pages_retrieved"]==2
    assert report["has_more"] is True
    assert report["next_page"]==13


@pytest.mark.asyncio
async def test_orders_list_uses_fixed_endpoint_authorization_and_page_header(monkeypatch):
    captured={}
    class FakeResponse:
        status_code=206
        headers={"content-type":"application/json"}
        async def aiter_bytes(self):
            yield json.dumps({"orderData":[]}).encode()
    @asynccontextmanager
    async def fake_open(url, **kwargs):
        captured["url"]=url
        captured.update(kwargs)
        yield FakeResponse()
    monkeypatch.setattr(clickbank,"open_public_http_response",fake_open)
    payload,status=await clickbank._request_clickbank_orders_page(
        "API-"+"x"*40,
        account="creator-main",
        start_date=date(2026,10,1),
        end_date=date(2026,10,30),
        page=9,
    )
    assert status==206 and payload=={"orderData":[]}
    assert captured["url"]=="https://api.clickbank.com/rest/1.3/orders2/list"
    assert captured["method"]=="GET"
    assert captured["params"]=={
        "affiliate":"creator-main","role":"AFFILIATE",
        "startDate":"2026-10-01","endDate":"2026-10-30",
    }
    assert captured["headers"]["Authorization"]=="API-"+"x"*40
    assert captured["headers"]["Page"]=="9"


def _api_client(tmp_path):
    engine=create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'provider-orders.db'}")
    sessions=async_sessionmaker(engine,expire_on_commit=False)
    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            workspace=Workspace(name="Order Import",slug="clickbank-order-import")
            db.add(workspace)
            await db.commit()
            connection=ProviderAccountConnection(
                workspace_id=workspace.id,provider_id="clickbank",status="connected_read_only",
                credential_ciphertext="encrypted",credential_fingerprint="f"*64,
                credential_key_version=1,account_nicknames_json=["creator-main"],
                capabilities_json=["quickstats.accounts.read"],
            )
            db.add(connection)
            await db.commit()
            return workspace.id,connection.id
    workspace_id,connection_id=asyncio.run(setup())
    user={"workspace_id":workspace_id,"workspace_role":"owner","email":"publisher@example.test","user_id":"owner-user","is_admin":False}
    async def override_session():
        async with sessions() as db:
            yield db
    async def override_auth():
        return user
    main.app.dependency_overrides[get_session]=override_session
    main.app.dependency_overrides[main.require_auth]=override_auth
    return engine,sessions,user,workspace_id,connection_id,TestClient(main.app)


def _api_cleanup(engine,client):
    main.app.dependency_overrides.pop(get_session,None)
    main.app.dependency_overrides.pop(main.require_auth,None)
    client.close()
    asyncio.run(engine.dispose())


def test_order_import_persists_idempotent_pii_minimized_observations(monkeypatch,tmp_path):
    engine,sessions,user,workspace_id,connection_id,client=_api_client(tmp_path)
    async def decrypt(*args,**kwargs):
        return "API-"+"x"*40
    report={
        "account":"creator-main",
        "transactions":[{
            "receipt":"CB123456","transaction_time":"2026-10-20T12:00:00+00:00",
            "transaction_type":"SALE","role":"AFFILIATE","account_nickname":"creator-main",
            "vendor_nickname":"vendor-main","affiliate_nickname":"creator-main","currency":"USD",
            "item_number":"ITEM-1","line_item_type":"STANDARD","product_title":"Sample product",
            "account_amount":"12.50","customer_amount":"49.00","line_item_status":"ACTIVE",
            "recurring":False,"shippable":False,"event_key":"e"*64,"source_fingerprint":"f"*64,
        }],
        "pages_retrieved":1,"source_order_count":1,"skipped_unidentified_count":0,
        "skipped_scope_count":0,"has_more":False,"next_page":None,
    }
    async def fetch_orders(*args,**kwargs):
        assert kwargs["account"]=="creator-main"
        assert kwargs["start_date"]==date(2026,10,1)
        return report
    monkeypatch.setattr(main,"decrypt_clickbank_api_key",decrypt)
    monkeypatch.setattr(main,"fetch_clickbank_order_transactions",fetch_orders)
    body={"account":"creator-main","start_date":"2026-10-01","end_date":"2026-10-30","max_pages":5}
    try:
        with client:
            first=client.post(f"/api/provider-connections/{connection_id}/orders/import",json=body)
            assert first.status_code==200,first.text
            result=first.json()
            assert result["imported_count"]==1 and result["duplicate_count"]==0
            assert result["pii_stored"] is False
            assert result["transactions"][0]["account_amount"]=="12.50"
            assert result["financial_semantics"].endswith("not_confirmed_commission_or_payout")
            assert "buyer@example.invalid" not in first.text
            assert "customerContactInfo" not in first.text

            second=client.post(f"/api/provider-connections/{connection_id}/orders/import",json=body)
            assert second.status_code==200,second.text
            assert second.json()["imported_count"]==0
            assert second.json()["duplicate_count"]==1

            unlinked={**body,"account":"not-linked"}
            assert client.post(f"/api/provider-connections/{connection_id}/orders/import",json=unlinked).status_code==404
            invalid={**body,"start_date":"2026-10-31","end_date":"2026-10-01"}
            assert client.post(f"/api/provider-connections/{connection_id}/orders/import",json=invalid).status_code==422

        async def read_rows():
            with workspace_scope(workspace_id):
                async with sessions() as db:
                    return list((await db.scalars(select(ProviderOrderObservation))).all())
        rows=asyncio.run(read_rows())
        assert len(rows)==1
        assert rows[0].account_amount==Decimal("12.500000")
        assert rows[0].evidence_status=="provider_reported_unreconciled"
        assert not hasattr(rows[0],"email")
    finally:
        _api_cleanup(engine,client)


def test_order_import_is_workspace_scoped_and_admin_gated(monkeypatch,tmp_path):
    engine,sessions,user,workspace_id,connection_id,client=_api_client(tmp_path)
    body={"account":"creator-main","start_date":"2026-10-01","end_date":"2026-10-30"}
    async def decrypt(*args,**kwargs): return "API-"+"x"*40
    async def fetch(*args,**kwargs): return {"account":"creator-main","transactions":[],"pages_retrieved":1,"source_order_count":0,"skipped_unidentified_count":0,"skipped_scope_count":0,"has_more":False,"next_page":None}
    monkeypatch.setattr(main,"decrypt_clickbank_api_key",decrypt)
    monkeypatch.setattr(main,"fetch_clickbank_order_transactions",fetch)
    try:
        with client:
            user["workspace_role"]="member"
            denied=client.post(f"/api/provider-connections/{connection_id}/orders/import",json=body)
            assert denied.status_code==403
    finally:
        _api_cleanup(engine,client)
