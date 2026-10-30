from __future__ import annotations
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, ProviderAccountConnection, Workspace
from backend.services.clickbank_accounts import decrypt_clickbank_api_key
from backend.tenancy import workspace_scope


def _client(tmp_path):
    engine=create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'provider-connections.db'}")
    sessions=async_sessionmaker(engine,expire_on_commit=False)
    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            a=Workspace(name="Publisher A",slug="provider-connection-a")
            b=Workspace(name="Publisher B",slug="provider-connection-b")
            db.add_all([a,b]);await db.commit()
            return a.id,b.id
    workspace_a,workspace_b=asyncio.run(setup())
    user={"workspace_id":workspace_a,"workspace_role":"owner","email":"publisher@example.test","user_id":"publisher-user","is_admin":False}
    async def override_session():
        async with sessions() as db: yield db
    async def override_auth(): return user
    main.app.dependency_overrides[get_session]=override_session
    main.app.dependency_overrides[main.require_auth]=override_auth
    return engine,sessions,user,workspace_a,workspace_b,TestClient(main.app)


def _cleanup(engine,client):
    main.app.dependency_overrides.pop(get_session,None)
    main.app.dependency_overrides.pop(main.require_auth,None)
    client.close();asyncio.run(engine.dispose())


def test_clickbank_connect_encrypts_and_never_returns_credential(monkeypatch,tmp_path):
    engine,sessions,user,workspace_a,_,client=_client(tmp_path)
    key="API-"+"a"*40
    calls=[]
    async def verified(value): calls.append(value);return ["creator-main","creator-secondary"]
    monkeypatch.setattr(main,"verify_clickbank_api_key",verified)
    try:
        with client:
            response=client.post("/api/provider-connections/clickbank",json={"api_key":key})
            assert response.status_code==201,response.text
            body=response.json()
            assert body["status"]=="connected_read_only"
            assert body["account_nicknames"]==["creator-main","creator-secondary"]
            assert body["permissions_verified"]==["API Order Read"]
            assert key not in response.text and "credential_ciphertext" not in response.text
            assert client.get("/api/provider-connections").json()["data"][0]["credential_present"] is True
        async def inspect():
            with workspace_scope(workspace_a):
                async with sessions() as db:
                    row=await db.scalar(select(ProviderAccountConnection).where(ProviderAccountConnection.workspace_id==workspace_a))
                    audit=await db.scalar(select(AuditLog).where(AuditLog.workspace_id==workspace_a,AuditLog.action=="integration.provider_account_connected"))
                    return row,audit
        row,audit=asyncio.run(inspect())
        assert row is not None and key not in row.credential_ciphertext
        assert decrypt_clickbank_api_key(row.credential_ciphertext)==key
        assert audit is not None and key not in str(audit.details_json)
    finally:_cleanup(engine,client)


def test_clickbank_duplicate_key_is_rejected_without_second_provider_call(monkeypatch,tmp_path):
    engine,_,_,_,_,client=_client(tmp_path)
    key="API-"+"b"*40;calls=[]
    async def verified(value): calls.append(value);return ["creator-main"]
    monkeypatch.setattr(main,"verify_clickbank_api_key",verified)
    try:
        with client:
            first=client.post("/api/provider-connections/clickbank",json={"api_key":key})
            second=client.post("/api/provider-connections/clickbank",json={"api_key":key})
        assert first.status_code==201 and second.status_code==409
        assert calls==[key]
    finally:_cleanup(engine,client)


def test_clickbank_workspace_isolation_permissions_test_and_disconnect(monkeypatch,tmp_path):
    engine,sessions,user,workspace_a,workspace_b,client=_client(tmp_path)
    key="API-"+"c"*40;calls=[]
    async def verified(value): calls.append(value);return ["creator-main","creator-updated"]
    monkeypatch.setattr(main,"verify_clickbank_api_key",verified)
    try:
        with client:
            created=client.post("/api/provider-connections/clickbank",json={"api_key":key})
            assert created.status_code==201,created.text
            connection_id=created.json()["id"]
            user["workspace_id"]=workspace_b
            assert client.get("/api/provider-connections").json()["data"]==[]
            assert client.post(f"/api/provider-connections/{connection_id}/test").status_code==404
            assert client.delete(f"/api/provider-connections/{connection_id}").status_code==404
            user["workspace_id"]=workspace_a
            user["workspace_role"]="member"
            assert client.post("/api/provider-connections/clickbank",json={"api_key":"API-"+"d"*40}).status_code==403
            user["workspace_role"]="owner"
            tested=client.post(f"/api/provider-connections/{connection_id}/test")
            assert tested.status_code==200,tested.text
            assert tested.json()["account_nicknames"]==["creator-main","creator-updated"]
            async def quickstats(_key, *, start_date, end_date, account=None):
                assert start_date.isoformat()=="2026-10-01"
                assert end_date.isoformat()=="2026-10-30"
                assert account=="creator-main"
                return {
                    "accounts":["creator-main"],
                    "daily":[{"account":"creator-main","date":"2026-10-01","sales":"10","refunds":"1","chargebacks":"0"}],
                    "totals":{"sales":"10","refunds":"1","chargebacks":"0"},
                }
            monkeypatch.setattr(main,"fetch_clickbank_quickstats",quickstats)
            report=client.get(
                f"/api/provider-connections/{connection_id}/quickstats",
                params={"start_date":"2026-10-01","end_date":"2026-10-30","account":"creator-main"},
            )
            assert report.status_code==200,report.text
            assert report.json()["evidence_type"]=="provider_reported_aggregate"
            assert report.json()["metric_scope"]=="sales_refunds_chargebacks_not_affiliate_commission_or_payout"
            assert report.json()["totals"]["sales"]=="10"
            unknown=client.get(
                f"/api/provider-connections/{connection_id}/quickstats",
                params={"start_date":"2026-10-01","end_date":"2026-10-30","account":"not-linked"},
            )
            assert unknown.status_code==404

            removed=client.delete(f"/api/provider-connections/{connection_id}")
            assert removed.status_code==200,removed.text
            assert removed.json()["provider_key_revoked_remotely"] is False
            listed=client.get("/api/provider-connections").json()["data"][0]
            assert listed["status"]=="disconnected" and listed["credential_present"] is False
        async def inspect():
            with workspace_scope(workspace_a):
                async with sessions() as db:
                    return await db.scalar(select(ProviderAccountConnection).where(ProviderAccountConnection.workspace_id==workspace_a))
        row=asyncio.run(inspect())
        assert row.credential_ciphertext is None and row.credential_fingerprint is None
        assert calls==[key,key]
    finally:_cleanup(engine,client)


def test_rejected_clickbank_key_is_not_persisted_or_echoed(monkeypatch,tmp_path):
    from backend.services.clickbank_accounts import ClickBankAccessError
    engine,sessions,user,workspace_a,_,client=_client(tmp_path)
    key="API-"+"e"*40
    async def rejected(value): raise ClickBankAccessError("ClickBank rejected API Order Read access.")
    monkeypatch.setattr(main,"verify_clickbank_api_key",rejected)
    try:
        with client:
            response=client.post("/api/provider-connections/clickbank",json={"api_key":key})
        assert response.status_code==422 and key not in response.text
        async def inspect():
            with workspace_scope(workspace_a):
                async with sessions() as db:return list((await db.scalars(select(ProviderAccountConnection))).all())
        assert asyncio.run(inspect())==[]
    finally:_cleanup(engine,client)
