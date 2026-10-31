from __future__ import annotations

import asyncio
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, ProviderAccountConnection, ProviderCatalogObservation, Workspace
from backend.services.digistore24_accounts import decrypt_digistore24_api_key
from backend.tenancy import workspace_scope

API_KEY = "ds24-read-" + "d" * 40


def _client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'digistore24-provider.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            first = Workspace(name="Digistore Publisher A", slug="digistore-publisher-a")
            second = Workspace(name="Digistore Publisher B", slug="digistore-publisher-b")
            db.add_all([first, second])
            await db.commit()
            return first.id, second.id

    workspace_a, workspace_b = asyncio.run(setup())
    user = {"workspace_id":workspace_a,"workspace_role":"owner","email":"publisher@example.test","user_id":"publisher-user","is_admin":False}

    async def override_session():
        async with sessions() as db:
            yield db

    async def override_auth():
        return user

    main.app.dependency_overrides[get_session] = override_session
    main.app.dependency_overrides[main.require_auth] = override_auth
    return engine, sessions, user, workspace_a, workspace_b, TestClient(main.app)


def _cleanup(engine, client):
    main.app.dependency_overrides.pop(get_session, None)
    main.app.dependency_overrides.pop(main.require_auth, None)
    client.close()
    asyncio.run(engine.dispose())


def _entry(**overrides):
    return {
        "external_id":"12345","title":"Practical AI Marketing Course","description":"Provider marketplace description",
        "category":"Education","product_url":"https://vendor.example.test/course","price_amount":"79.0","currency":"EUR",
        "affiliate_share":"50","affiliate_profit_per_visitor":"2.75","affiliate_profit_per_sale":"39.5",
        "stats_stars":"4.7","stats_cancel_rate":"3.2","stats_conversion_rate":"2.8","stats_orders_with_affiliates":321,
        "approval_status":"active","approval_status_message":None,"vendor_name":"Example Vendor",
        "affiliate_support_url":"https://vendor.example.test/affiliates","product_created_at":None,"stats_updated_at":None,
        **overrides
    }


def _report(**overrides):
    return {
        "provider_id":"digistore24","evidence_type":"provider_reported_affiliate_marketplace","source_endpoint":"listMarketplaceEntries",
        "query":"marketing","provider_list_count":1,"normalized_count":1,"result_count":1,"entries":[_entry()],
        "commission_terms_status":"provider_marketplace_fields_only",
        "note":"Marketplace values are provider-reported; vendor approval is separate.",**overrides
    }


def _verified():
    return {"account_references":["123456"],"marketplace_entry_count":1,"capabilities":["account.ping","marketplace.entries.read"]}


def test_connect_encrypts_key_and_never_returns_or_audits_secret(monkeypatch, tmp_path):
    engine, sessions, _, workspace_a, _, client = _client(tmp_path)
    calls = []

    async def verify(api_key):
        calls.append(api_key)
        return _verified()

    monkeypatch.setattr(main, "verify_digistore24_api_key", verify)
    try:
        with client:
            response = client.post("/api/provider-connections/digistore24", json={"api_key":API_KEY})
            assert response.status_code == 201, response.text
            body = response.json()
            assert body["provider_id"] == "digistore24"
            assert body["status"] == "connected_read_only"
            assert body["account_nicknames"] == ["123456"]
            assert body["permissions_verified"] == ["Marketplace entries read"]
            assert API_KEY not in response.text and "credential_ciphertext" not in response.text
            assert client.get("/api/provider-connections").json()["data"][0]["credential_present"] is True

        async def inspect():
            with workspace_scope(workspace_a):
                async with sessions() as db:
                    row = await db.scalar(select(ProviderAccountConnection).where(
                        ProviderAccountConnection.workspace_id==workspace_a,ProviderAccountConnection.provider_id=="digistore24"))
                    audit = await db.scalar(select(AuditLog).where(
                        AuditLog.workspace_id==workspace_a,AuditLog.action=="integration.provider_account_connected",
                        AuditLog.resource_type=="provider_account_connection"))
                    return row,audit

        row,audit=asyncio.run(inspect())
        assert row is not None and decrypt_digistore24_api_key(row.credential_ciphertext)==API_KEY
        assert row.credential_fingerprint!=API_KEY and API_KEY not in str(audit.details_json)
        assert calls==[API_KEY]
    finally:
        _cleanup(engine,client)


def test_marketplace_search_upserts_and_enforces_tenant_and_role_scope(monkeypatch,tmp_path):
    engine,sessions,user,workspace_a,workspace_b,client=_client(tmp_path)

    async def verify(api_key): return _verified()
    async def search(api_key,*,query,limit):
        assert api_key==API_KEY and query=="marketing" and limit==20
        return _report()

    monkeypatch.setattr(main,"verify_digistore24_api_key",verify)
    monkeypatch.setattr(main,"search_digistore24_marketplace",search)
    try:
        with client:
            conn=client.post("/api/provider-connections/digistore24",json={"api_key":API_KEY})
            assert conn.status_code==201,conn.text
            connection_id=conn.json()["id"]
            first=client.post(f"/api/provider-connections/{connection_id}/digistore24/marketplace/search",json={"query":"marketing","limit":20})
            assert first.status_code==200,first.text
            assert first.json()["persisted_count"]==1
            assert first.json()["entries"][0]["affiliate_share"]=="50"
            assert API_KEY not in first.text

            updated=_report()
            updated["entries"][0]["price_amount"]="69.0"
            async def updated_search(api_key,*,query,limit): return updated
            monkeypatch.setattr(main,"search_digistore24_marketplace",updated_search)
            again=client.post(f"/api/provider-connections/{connection_id}/digistore24/marketplace/search",json={"query":"marketing","limit":20})
            assert again.status_code==200,again.text
            saved=client.get(f"/api/provider-connections/{connection_id}/digistore24/marketplace",params={"limit":50,"offset":0})
            assert saved.status_code==200 and saved.json()["count"]==1
            assert saved.json()["entries"][0]["price_amount"]=="69.0"

            user["workspace_id"]=workspace_b
            assert client.get("/api/provider-connections").json()["data"]==[]
            assert client.get(f"/api/provider-connections/{connection_id}/digistore24/marketplace").status_code==404
            user["workspace_id"]=workspace_a
            user["workspace_role"]="member"
            denied=client.post(f"/api/provider-connections/{connection_id}/digistore24/marketplace/search",json={"query":"marketing"})
            assert denied.status_code==403
            user["workspace_role"]="owner"
            disconnected=client.delete(f"/api/provider-connections/{connection_id}")
            assert disconnected.status_code==200 and disconnected.json()["provider_key_revoked_remotely"] is False
            local=client.get(f"/api/provider-connections/{connection_id}/digistore24/marketplace")
            assert local.status_code==200 and local.json()["count"]==1

        async def inspect():
            with workspace_scope(workspace_a):
                async with sessions() as db:
                    row=await db.scalar(select(ProviderAccountConnection).where(
                        ProviderAccountConnection.workspace_id==workspace_a,ProviderAccountConnection.provider_id=="digistore24"))
                    observations=list((await db.scalars(select(ProviderCatalogObservation).where(
                        ProviderCatalogObservation.workspace_id==workspace_a,ProviderCatalogObservation.provider_id=="digistore24"))).all())
                    return row,observations
        row,observations=asyncio.run(inspect())
        assert row.status=="disconnected" and row.credential_ciphertext is None and row.credential_fingerprint is None
        assert len(observations)==1 and observations[0].price_amount==Decimal("69.0000")
        assert observations[0].currency=="EUR" and observations[0].is_available is None
        assert "affiliate_share" in observations[0].snapshot_json
    finally:
        _cleanup(engine,client)


def test_rejected_key_is_not_persisted_or_echoed(monkeypatch,tmp_path):
    from backend.services.digistore24_accounts import Digistore24AccessError
    engine,sessions,_,workspace_a,_,client=_client(tmp_path)

    async def rejected(api_key):
        raise Digistore24AccessError("Digistore24 rejected the key.")

    monkeypatch.setattr(main,"verify_digistore24_api_key",rejected)
    try:
        with client:
            response=client.post("/api/provider-connections/digistore24",json={"api_key":API_KEY})
        assert response.status_code==422 and API_KEY not in response.text

        async def inspect():
            with workspace_scope(workspace_a):
                async with sessions() as db:
                    return list((await db.scalars(select(ProviderAccountConnection))).all())
        assert asyncio.run(inspect())==[]
    finally:
        _cleanup(engine,client)
