from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, ProviderAccountConnection, ProviderCatalogObservation, Workspace
from backend.tenancy import workspace_scope

DS24_KEY = "test-ds24-" + "d" * 36
FLIPKART_TOKEN = "test-flipkart-" + "f" * 36


def _client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'affiliate-research.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            workspace_a = Workspace(name="Research Workspace A", slug="research-workspace-a")
            workspace_b = Workspace(name="Research Workspace B", slug="research-workspace-b")
            db.add_all([workspace_a, workspace_b])
            await db.commit()
            return workspace_a.id, workspace_b.id

    workspace_a, workspace_b = asyncio.run(setup())
    user = {"workspace_id": workspace_a, "workspace_role": "owner", "email": "research-owner@example.test", "user_id": "research-owner", "is_admin": False, "account_type": "affiliate_publisher"}

    async def override_session():
        async with sessions() as db:
            yield db

    async def override_auth():
        return user

    main.app.dependency_overrides[get_session] = override_session
    main.app.dependency_overrides[main.require_auth] = override_auth
    return engine, sessions, workspace_a, workspace_b, TestClient(main.app)


def _cleanup(engine, client):
    main.app.dependency_overrides.pop(get_session, None)
    main.app.dependency_overrides.pop(main.require_auth, None)
    client.close()
    asyncio.run(engine.dispose())


def _digistore_entry():
    return {
        "external_id": "12345", "title": "Ethical AI Marketing Course",
        "description": "Provider supplied product description", "category": "Education",
        "vendor_name": "Example Vendor", "product_url": "https://vendor.example.test/course",
        "price_amount": "79.0", "currency": "EUR", "affiliate_share": "50",
        "affiliate_profit_per_visitor": "2.75", "affiliate_profit_per_sale": "39.5",
        "stats_stars": "4.7", "stats_cancel_rate": "3.2", "stats_conversion_rate": "2.8",
        "stats_orders_with_affiliates": 321, "approval_status": "active",
        "approval_status_message": None, "affiliate_support_url": None,
        "product_created_at": None, "stats_updated_at": None,
    }


def _flipkart_product():
    return {
        "external_id": "FK-123", "title": "Creator Video Camera",
        "description": "Provider supplied product description", "category": "Electronics",
        "brand": "Example Brand", "product_url": "https://www.flipkart.com/item/p/itm123",
        "image_url": None, "price_amount": "1999.00", "mrp_amount": "2499.00",
        "currency": "INR", "discount_percentage": "20", "in_stock": True,
    }


def _seed_connections(sessions, workspace_a, workspace_b):
    async def seed():
        async with sessions() as db:
            db.add_all([
                ProviderAccountConnection(workspace_id=workspace_a, provider_id="digistore24", status="connected_read_only",
                    credential_ciphertext="x", credential_fingerprint="a" * 64,
                    account_nicknames_json=["ds-account-1"], capabilities_json=["marketplace.entries.read"]),
                ProviderAccountConnection(workspace_id=workspace_a, provider_id="flipkart", status="connected_read_only",
                    credential_ciphertext="y", credential_fingerprint="b" * 64,
                    account_nicknames_json=["tracking-123"], capabilities_json=["products.search.read"]),
                ProviderAccountConnection(workspace_id=workspace_b, provider_id="digistore24", status="connected_read_only",
                    credential_ciphertext="z", credential_fingerprint="c" * 64,
                    account_nicknames_json=["other-account"], capabilities_json=["marketplace.entries.read"]),
            ])
            await db.commit()
    asyncio.run(seed())


def _patch_providers(monkeypatch):
    def decrypt_ds24(ciphertext, key_version=1):
        if ciphertext == "x":
            return DS24_KEY
        raise AssertionError("A connection outside the active workspace was accessed")

    def decrypt_flipkart(ciphertext, key_version=1):
        if ciphertext == "y":
            return FLIPKART_TOKEN
        raise AssertionError("A connection outside the active workspace was accessed")

    async def search_ds24(api_key, *, query, limit):
        assert api_key == DS24_KEY and query == "creator tools" and limit == 5
        return {"provider_id": "digistore24", "evidence_type": "provider_reported_affiliate_marketplace",
            "source_endpoint": "listMarketplaceEntries", "entries": [_digistore_entry()], "result_count": 1, "note": "Provider supplied snapshot."}

    async def search_flipkart(tracking_id, api_token, *, query, result_count):
        assert tracking_id == "tracking-123" and api_token == FLIPKART_TOKEN
        assert query == "creator tools" and result_count == 5
        return {"provider_id": "flipkart", "evidence_type": "provider_reported_product_search",
            "source_endpoint": "affiliate/1.0/search.json", "products": [_flipkart_product()], "result_count": 1, "note": "Provider supplied snapshot."}

    monkeypatch.setattr(main, "decrypt_digistore24_api_key", decrypt_ds24)
    monkeypatch.setattr(main, "decrypt_flipkart_api_token", decrypt_flipkart)
    monkeypatch.setattr(main, "search_digistore24_marketplace", search_ds24)
    monkeypatch.setattr(main, "search_flipkart_products", search_flipkart)


def test_cross_provider_search_persists_scoped_provider_evidence(monkeypatch, tmp_path):
    engine, sessions, workspace_a, workspace_b, client = _client(tmp_path)
    _seed_connections(sessions, workspace_a, workspace_b)
    _patch_providers(monkeypatch)
    try:
        with client:
            response = client.post("/api/affiliate-research/search", json={"query": "creator tools", "limit": 5})
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["status"] == "provider_reported" and body["result_count"] == 2
            assert {item["provider_id"] for item in body["results"]} == {"digistore24", "flipkart"}
            assert body["execution"]["external_writes_executed"] is False
            assert body["execution"]["affiliate_applications_submitted"] is False
            assert body["execution"]["ad_spend_changed"] is False
            assert body["execution"]["payouts_transferred"] is False
            digistore = next(item for item in body["results"] if item["provider_id"] == "digistore24")
            flipkart = next(item for item in body["results"] if item["provider_id"] == "flipkart")
            assert digistore["provider_reported_metrics"]["affiliate_share"] == "50"
            assert digistore["commission_terms_status"] == "provider_marketplace_fields_only"
            assert flipkart["commission_terms_status"] == "not_exposed_by_product_search_endpoint"
            assert FLIPKART_TOKEN not in response.text and DS24_KEY not in response.text

        async def inspect():
            async with sessions() as db:
                with workspace_scope(workspace_a):
                    saved = list((await db.scalars(select(ProviderCatalogObservation).where(ProviderCatalogObservation.workspace_id == workspace_a))).all())
                    audits = list((await db.scalars(select(AuditLog).where(AuditLog.workspace_id == workspace_a, AuditLog.action == "affiliate_research.marketplace_search"))).all())
                with workspace_scope(workspace_b):
                    other = list((await db.scalars(select(ProviderCatalogObservation).where(ProviderCatalogObservation.workspace_id == workspace_b))).all())
                return saved, audits, other

        saved, audits, other = asyncio.run(inspect())
        assert len(saved) == 2 and len(audits) == 2 and other == []
    finally:
        _cleanup(engine, client)


def test_provider_failure_isolated_from_other_connected_catalogs(monkeypatch, tmp_path):
    engine, sessions, workspace_a, workspace_b, client = _client(tmp_path)
    _seed_connections(sessions, workspace_a, workspace_b)

    async def fail_ds24(api_key, *, query, limit):
        raise main.Digistore24AccessError("provider denied read access")

    async def search_flipkart(tracking_id, api_token, *, query, result_count):
        return {"provider_id": "flipkart", "evidence_type": "provider_reported_product_search",
            "source_endpoint": "affiliate/1.0/search.json", "products": [_flipkart_product()], "result_count": 1, "note": "Provider supplied snapshot."}

    monkeypatch.setattr(main, "decrypt_digistore24_api_key", lambda *args, **kwargs: DS24_KEY)
    monkeypatch.setattr(main, "decrypt_flipkart_api_token", lambda *args, **kwargs: FLIPKART_TOKEN)
    monkeypatch.setattr(main, "search_digistore24_marketplace", fail_ds24)
    monkeypatch.setattr(main, "search_flipkart_products", search_flipkart)
    try:
        with client:
            response = client.post("/api/affiliate-research/search", json={"query": "creator tools", "limit": 5})
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["status"] == "partial" and body["result_count"] == 1
            ds24 = next(item for item in body["providers"] if item["provider_id"] == "digistore24")
            flip = next(item for item in body["providers"] if item["provider_id"] == "flipkart")
            assert ds24["status"] == "degraded"
            assert ds24["errors"][0]["code"] == "credential_or_permission_rejected"
            assert flip["status"] == "provider_reported"
            assert body["execution"]["external_writes_executed"] is False
    finally:
        _cleanup(engine, client)


def test_search_validates_query_and_returns_not_configured_without_accounts(tmp_path):
    engine, sessions, _, _, client = _client(tmp_path)
    try:
        with client:
            invalid = client.post("/api/affiliate-research/search", json={"query": "x"})
            assert invalid.status_code == 422
            empty = client.post("/api/affiliate-research/search", json={"query": "garden"})
            assert empty.status_code == 200
            assert empty.json()["status"] == "not_configured"
            assert empty.json()["result_count"] == 0
            assert {item["status"] for item in empty.json()["providers"]} == {"not_configured"}
    finally:
        _cleanup(engine, client)
