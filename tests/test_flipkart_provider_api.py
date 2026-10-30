from __future__ import annotations

import asyncio
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, ProviderAccountConnection, ProviderCatalogObservation, Workspace
from backend.services.flipkart_accounts import decrypt_flipkart_api_token
from backend.tenancy import workspace_scope


TRACKING_ID = "creator123"
API_TOKEN = "private-token-" + "x" * 32


def _client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'flipkart-provider.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            a = Workspace(name="Flipkart Publisher A", slug="flipkart-publisher-a")
            b = Workspace(name="Flipkart Publisher B", slug="flipkart-publisher-b")
            db.add_all([a, b])
            await db.commit()
            return a.id, b.id

    workspace_a, workspace_b = asyncio.run(setup())
    user = {
        "workspace_id": workspace_a,
        "workspace_role": "owner",
        "email": "publisher@example.test",
        "user_id": "publisher-user",
        "is_admin": False,
    }

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


def _verified(**overrides):
    return {
        "tracking_id": TRACKING_ID,
        "categories": ["api", "api_v1"],
        "capabilities": ["product_feed.directory.read", "products.search", "offers.list"],
        **overrides,
    }


def _products(**overrides):
    return {
        "provider_id": "flipkart",
        "evidence_type": "provider_reported_product_search",
        "source_endpoint": "affiliate/1.0/search.json",
        "query": "android phone",
        "requested_count": 10,
        "result_count": 1,
        "products": [{
            "external_id": "MOBABC123",
            "title": "Sample Android Phone",
            "description": "Provider supplied product description",
            "brand": "ExampleBrand",
            "category": "Mobiles / Smartphones",
            "product_url": "https://www.flipkart.com/sample-phone",
            "image_url": "https://rukminim1.flixcart.com/sample.jpeg",
            "price_amount": "12999",
            "mrp_amount": "15999",
            "currency": "INR",
            "in_stock": True,
            "discount_percentage": "18",
            "attributes": {"ram": "8 GB"},
        }],
        "commission_terms_status": "not_exposed_by_product_search_endpoint",
        "note": "Commission rate, cookie duration, payout terms, account eligibility and approval were not supplied.",
        **overrides,
    }


def _offers(**overrides):
    return {
        "provider_id": "flipkart",
        "evidence_type": "provider_reported_active_offers",
        "source_endpoint": "affiliate/offers/v1/all/json",
        "offer_kind": "all",
        "result_count": 1,
        "offers": [{
            "external_id": "offer-hash-1",
            "title": "Weekend electronics offer",
            "description": "Provider supplied offer description",
            "category": "Electronics",
            "offer_url": "https://www.flipkart.com/offers/sample",
            "image_url": None,
            "availability_status": "LIVE",
            "is_available": True,
            "start_at": "2026-10-29T00:00:00+00:00",
            "end_at": "2026-11-02T23:59:59+00:00",
        }],
        "commission_terms_status": "not_exposed_by_offer_feed",
        "note": "Commission rate, cookie duration, payout terms, account eligibility and approval were not supplied.",
        **overrides,
    }


def test_flipkart_connect_encrypts_token_and_never_returns_or_audits_secret(monkeypatch, tmp_path):
    engine, sessions, user, workspace_a, _, client = _client(tmp_path)
    calls = []

    async def verify(tracking_id, token):
        calls.append((tracking_id, token))
        return _verified()

    monkeypatch.setattr(main, "verify_flipkart_credentials", verify)
    try:
        with client:
            response = client.post(
                "/api/provider-connections/flipkart",
                json={"tracking_id": TRACKING_ID, "api_token": API_TOKEN},
            )
            assert response.status_code == 201, response.text
            body = response.json()
            assert body["provider_id"] == "flipkart"
            assert body["status"] == "connected_read_only"
            assert body["account_nicknames"] == [TRACKING_ID]
            assert body["capabilities"] == ["product_feed.directory.read", "products.search", "offers.list"]
            assert body["permissions_verified"] == ["Product Feed Directory", "Product Search", "Active Offers"]
            assert body["categories"] == ["api", "api_v1"]
            assert API_TOKEN not in response.text
            assert "credential_ciphertext" not in response.text
            listed = client.get("/api/provider-connections")
            assert listed.status_code == 200
            assert listed.json()["data"][0]["credential_present"] is True

        async def inspect():
            with workspace_scope(workspace_a):
                async with sessions() as db:
                    row = await db.scalar(select(ProviderAccountConnection).where(
                        ProviderAccountConnection.workspace_id == workspace_a,
                        ProviderAccountConnection.provider_id == "flipkart",
                    ))
                    audit = await db.scalar(select(AuditLog).where(
                        AuditLog.workspace_id == workspace_a,
                        AuditLog.action == "integration.provider_account_connected",
                    ))
                    return row, audit

        row, audit = asyncio.run(inspect())
        assert row is not None
        assert row.credential_ciphertext != API_TOKEN
        assert decrypt_flipkart_api_token(row.credential_ciphertext) == API_TOKEN
        assert row.credential_fingerprint != API_TOKEN
        assert audit is not None and API_TOKEN not in str(audit.details_json)
        assert calls == [(TRACKING_ID, API_TOKEN)]
    finally:
        _cleanup(engine, client)


def test_flipkart_duplicate_credentials_are_rejected_without_second_provider_call(monkeypatch, tmp_path):
    engine, _, _, _, _, client = _client(tmp_path)
    calls = []

    async def verify(tracking_id, token):
        calls.append((tracking_id, token))
        return _verified()

    monkeypatch.setattr(main, "verify_flipkart_credentials", verify)
    try:
        with client:
            first = client.post("/api/provider-connections/flipkart", json={"tracking_id": TRACKING_ID, "api_token": API_TOKEN})
            second = client.post("/api/provider-connections/flipkart", json={"tracking_id": TRACKING_ID, "api_token": API_TOKEN})
        assert first.status_code == 201
        assert second.status_code == 409
        assert calls == [(TRACKING_ID, API_TOKEN)]
    finally:
        _cleanup(engine, client)


def test_flipkart_search_and_offers_persist_workspace_snapshots_and_upsert(monkeypatch, tmp_path):
    engine, sessions, user, workspace_a, workspace_b, client = _client(tmp_path)
    verify_calls = []

    async def verify(tracking_id, token):
        verify_calls.append((tracking_id, token))
        return _verified()

    async def search(tracking_id, token, *, query, result_count):
        assert tracking_id == TRACKING_ID and token == API_TOKEN
        assert query == "android phone" and result_count == 10
        return _products()

    async def offers(tracking_id, token, *, kind):
        assert tracking_id == TRACKING_ID and token == API_TOKEN
        return _offers(offer_kind=kind)

    monkeypatch.setattr(main, "verify_flipkart_credentials", verify)
    monkeypatch.setattr(main, "search_flipkart_products", search)
    monkeypatch.setattr(main, "fetch_flipkart_offers", offers)
    try:
        with client:
            connection = client.post(
                "/api/provider-connections/flipkart",
                json={"tracking_id": TRACKING_ID, "api_token": API_TOKEN},
            )
            assert connection.status_code == 201, connection.text
            connection_id = connection.json()["id"]

            search_response = client.post(
                f"/api/provider-connections/{connection_id}/flipkart/products/search",
                json={"query": "android phone", "result_count": 10},
            )
            assert search_response.status_code == 200, search_response.text
            assert search_response.json()["persisted_count"] == 1
            assert search_response.json()["products"][0]["price_amount"] == "12999"
            assert search_response.json()["commission_terms_status"] == "not_exposed_by_product_search_endpoint"
            assert API_TOKEN not in search_response.text

            # Re-importing an existing product updates its snapshot, rather than creating duplicates.
            updated_payload = _products()
            updated_payload["products"][0]["price_amount"] = "11999"

            async def updated_search(tracking_id, token, *, query, result_count):
                return updated_payload

            monkeypatch.setattr(main, "search_flipkart_products", updated_search)
            repeated = client.post(
                f"/api/provider-connections/{connection_id}/flipkart/products/search",
                json={"query": "android phone", "result_count": 10},
            )
            assert repeated.status_code == 200, repeated.text
            assert repeated.json()["persisted_count"] == 1

            offer_response = client.get(
                f"/api/provider-connections/{connection_id}/flipkart/offers",
                params={"kind": "all"},
            )
            assert offer_response.status_code == 200, offer_response.text
            assert offer_response.json()["persisted_count"] == 1
            assert offer_response.json()["offers"][0]["title"] == "Weekend electronics offer"
            assert offer_response.json()["commission_terms_status"] == "not_exposed_by_offer_feed"

            saved_products = client.get(
                f"/api/provider-connections/{connection_id}/flipkart/catalog",
                params={"kind": "product", "limit": 100, "offset": 0},
            )
            assert saved_products.status_code == 200, saved_products.text
            assert saved_products.json()["count"] == 1
            assert saved_products.json()["products"][0]["price_amount"] == "11999"
            assert saved_products.json()["commission_terms_status"] == "not_exposed_by_product_search_endpoint"

            saved_offers = client.get(
                f"/api/provider-connections/{connection_id}/flipkart/catalog",
                params={"kind": "offer", "limit": 100, "offset": 0},
            )
            assert saved_offers.status_code == 200, saved_offers.text
            assert saved_offers.json()["count"] == 1
            assert saved_offers.json()["offers"][0]["title"] == "Weekend electronics offer"

            # Connections and catalog observations are scoped to the workspace that owns the token.
            user["workspace_id"] = workspace_b
            assert client.get("/api/provider-connections").json()["data"] == []
            assert client.post(
                f"/api/provider-connections/{connection_id}/flipkart/products/search",
                json={"query": "android phone"},
            ).status_code == 404
            user["workspace_id"] = workspace_a
            user["workspace_role"] = "member"
            denied = client.post(
                f"/api/provider-connections/{connection_id}/flipkart/products/search",
                json={"query": "android phone"},
            )
            assert denied.status_code == 403
            user["workspace_role"] = "owner"

            disconnected = client.delete(f"/api/provider-connections/{connection_id}")
            assert disconnected.status_code == 200, disconnected.text
            assert disconnected.json()["provider_key_revoked_remotely"] is False
            assert "Flipkart Affiliate API settings" in disconnected.json()["detail"]
            # Saved provider observations remain readable locally after disconnect;
            # this endpoint must not need or reuse the removed remote credential.
            saved_after_disconnect = client.get(
                f"/api/provider-connections/{connection_id}/flipkart/catalog",
                params={"kind": "product", "limit": 100, "offset": 0},
            )
            assert saved_after_disconnect.status_code == 200
            assert saved_after_disconnect.json()["count"] == 1

        async def inspect():
            with workspace_scope(workspace_a):
                async with sessions() as db:
                    rows = list((await db.scalars(select(ProviderCatalogObservation).where(
                        ProviderCatalogObservation.workspace_id == workspace_a,
                    ))).all())
                    connection = await db.scalar(select(ProviderAccountConnection).where(
                        ProviderAccountConnection.workspace_id == workspace_a,
                        ProviderAccountConnection.provider_id == "flipkart",
                    ))
                    return rows, connection

        rows, connection_row = asyncio.run(inspect())
        assert len(rows) == 2
        by_type = {row.observation_type: row for row in rows}
        assert by_type["product"].external_id == "MOBABC123"
        assert by_type["product"].price_amount == Decimal("11999.0000")
        assert by_type["product"].currency == "INR"
        assert by_type["product"].is_available is True
        assert "commission_terms_status" not in by_type["product"].snapshot_json
        assert by_type["offer"].title == "Weekend electronics offer"
        assert by_type["offer"].is_available is True
        assert by_type["offer"].starts_at is not None and by_type["offer"].ends_at is not None
        assert connection_row.status == "disconnected"
        assert connection_row.credential_ciphertext is None
        assert connection_row.credential_fingerprint is None
        assert verify_calls == [(TRACKING_ID, API_TOKEN)]
    finally:
        _cleanup(engine, client)


def test_rejected_flipkart_credentials_are_not_persisted_or_echoed(monkeypatch, tmp_path):
    from backend.services.flipkart_accounts import FlipkartAccessError

    engine, sessions, _, workspace_a, _, client = _client(tmp_path)

    async def rejected(tracking_id, token):
        raise FlipkartAccessError("Flipkart rejected the supplied affiliate token.")

    monkeypatch.setattr(main, "verify_flipkart_credentials", rejected)
    try:
        with client:
            response = client.post(
                "/api/provider-connections/flipkart",
                json={"tracking_id": TRACKING_ID, "api_token": API_TOKEN},
            )
        assert response.status_code == 422
        assert API_TOKEN not in response.text

        async def inspect():
            with workspace_scope(workspace_a):
                async with sessions() as db:
                    return list((await db.scalars(select(ProviderAccountConnection))).all())

        assert asyncio.run(inspect()) == []
    finally:
        _cleanup(engine, client)


def test_two_flipkart_accounts_keep_same_product_snapshots_isolated(monkeypatch, tmp_path):
    engine, sessions, _, workspace_a, _, client = _client(tmp_path)
    second_tracking_id = "creator456"
    second_token = "second-private-token-" + "y" * 32

    async def verify(tracking_id, token):
        return _verified(tracking_id=tracking_id)

    async def search(tracking_id, token, *, query, result_count):
        value = "12999" if tracking_id == TRACKING_ID else "11999"
        result = _products()
        result["products"][0]["price_amount"] = value
        result["products"][0]["product_url"] = "https://www.flipkart.com/" + tracking_id + "/same-product"
        return result

    monkeypatch.setattr(main, "verify_flipkart_credentials", verify)
    monkeypatch.setattr(main, "search_flipkart_products", search)
    try:
        with client:
            first = client.post(
                "/api/provider-connections/flipkart",
                json={"tracking_id": TRACKING_ID, "api_token": API_TOKEN},
            )
            second = client.post(
                "/api/provider-connections/flipkart",
                json={"tracking_id": second_tracking_id, "api_token": second_token},
            )
            assert first.status_code == 201, first.text
            assert second.status_code == 201, second.text
            first_id, second_id = first.json()["id"], second.json()["id"]
            assert first_id != second_id

            first_result = client.post(
                f"/api/provider-connections/{first_id}/flipkart/products/search",
                json={"query": "android phone", "result_count": 10},
            )
            second_result = client.post(
                f"/api/provider-connections/{second_id}/flipkart/products/search",
                json={"query": "android phone", "result_count": 10},
            )
            assert first_result.status_code == 200, first_result.text
            assert second_result.status_code == 200, second_result.text

        async def inspect():
            with workspace_scope(workspace_a):
                async with sessions() as db:
                    return list((await db.scalars(select(ProviderCatalogObservation).where(
                        ProviderCatalogObservation.workspace_id == workspace_a,
                        ProviderCatalogObservation.observation_type == "product",
                        ProviderCatalogObservation.external_id == "MOBABC123",
                    ))).all())

        rows = asyncio.run(inspect())
        assert len(rows) == 2
        by_connection = {row.connection_id: row for row in rows}
        assert by_connection[first_id].price_amount == Decimal("12999.0000")
        assert by_connection[second_id].price_amount == Decimal("11999.0000")
        assert by_connection[first_id].provider_url.endswith("/" + TRACKING_ID + "/same-product")
        assert by_connection[second_id].provider_url.endswith("/" + second_tracking_id + "/same-product")
    finally:
        _cleanup(engine, client)
