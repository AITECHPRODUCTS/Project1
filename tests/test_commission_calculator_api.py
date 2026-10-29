from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base
from backend.models import AuditLog, ContentAsset, Workspace


def _client(tmp_path, active_workspace="commission-workspace"):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'commission-projection.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    active = {"workspace_id": active_workspace}

    async def prepare():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            session.add(Workspace(
                id="commission-workspace",
                name="Commission workspace",
                slug="commission-workspace",
            ))
            await session.commit()

    async def override_session():
        async with sessions() as session:
            yield session

    async def auth_user():
        return {
            "email": "commission-user@example.invalid",
            "user_id": "commission-user",
            "workspace_id": active["workspace_id"],
            "workspace_role": "owner",
            "is_admin": False,
        }

    asyncio.run(prepare())
    main.app.dependency_overrides[main.get_session] = override_session
    main.app.dependency_overrides[main.require_auth] = auth_user
    return engine, sessions, active, TestClient(main.app)


def _payload():
    return {
        "monthly_visitors": 100,
        "click_through_rate_pct": 10,
        "affiliate_conversion_rate_pct": 10,
        "programs": [{
            "name": "One-time Example",
            "reward_type": "cps_one_time",
            "commission_type": "percentage",
            "commission_value": 20,
            "currency": "USD",
            "average_order_value": 50,
        }],
    }


def _cleanup(engine, client):
    main.app.dependency_overrides.pop(main.get_session, None)
    main.app.dependency_overrides.pop(main.require_auth, None)
    client.close()
    asyncio.run(engine.dispose())


def test_commission_calculator_persists_review_required_workspace_draft_and_audit(tmp_path):
    engine, sessions, _, client = _client(tmp_path)
    try:
        with client:
            response = client.post("/api/research/commission-calculator", json=_payload())
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["asset_id"]
        assert body["asset_status"] == "draft"
        assert body["requires_review"] is True
        assert body["publishing_started"] is False
        assert body["currency_comparison"] == "USD"
        assert body["programs"][0]["estimated_first_month_commission"] == "10.000000"
        assert body["programs"][0]["estimated_12_month_commission"] == "120.000000"
        assert body["provider_metrics_verified"] is False
        assert body["earnings_guaranteed"] is False
        assert body["external_provider_calls_made"] is False
        assert body["money_transferred"] is False

        async def read_persisted():
            async with sessions() as session:
                asset = await session.get(ContentAsset, body["asset_id"])
                audit = await session.scalar(select(AuditLog).where(
                    AuditLog.action == "research.commission_projection.created",
                    AuditLog.resource_id == body["asset_id"],
                ))
            return asset, audit

        asset, audit = asyncio.run(read_persisted())
        assert asset is not None and asset.workspace_id == "commission-workspace"
        assert asset.asset_type == "commission_projection" and asset.status == "draft"
        assert json.loads(asset.body)["programs"][0]["estimated_12_month_commission"] == "120.000000"
        assert asset.metadata_json["provider_metrics_verified"] is False
        assert asset.metadata_json["publishing_started"] is False
        assert audit is not None and audit.outcome == "draft"
        assert audit.details_json["money_transferred"] is False
    finally:
        _cleanup(engine, client)


def test_commission_calculator_requires_an_active_workspace(tmp_path):
    engine, sessions, active, client = _client(tmp_path)
    try:
        active["workspace_id"] = ""
        with client:
            response = client.post("/api/research/commission-calculator", json=_payload())
        assert response.status_code == 403
        async def count_assets():
            async with sessions() as session:
                return await session.scalar(select(func.count()).select_from(ContentAsset))
        assert asyncio.run(count_assets()) == 0
    finally:
        _cleanup(engine, client)


def test_commission_calculator_rejects_mixed_currencies_and_saves_nothing(tmp_path):
    engine, sessions, _, client = _client(tmp_path)
    payload = _payload()
    payload["programs"].append({
        "name": "Pound program",
        "reward_type": "cps_one_time",
        "commission_type": "fixed",
        "commission_value": 12,
        "currency": "GBP",
    })
    try:
        with client:
            response = client.post("/api/research/commission-calculator", json=payload)
        assert response.status_code == 422, response.text
        async def count_assets():
            async with sessions() as session:
                return await session.scalar(select(func.count()).select_from(ContentAsset))
        assert asyncio.run(count_assets()) == 0
    finally:
        _cleanup(engine, client)


def test_commission_calculator_rejects_invalid_program_contract(tmp_path):
    engine, _, _, client = _client(tmp_path)
    payload = _payload()
    payload["unexpected"] = "ignore me"
    try:
        with client:
            response = client.post("/api/research/commission-calculator", json=payload)
        assert response.status_code == 422
    finally:
        _cleanup(engine, client)


def test_commission_calculator_recurring_projection_requires_explicit_duration(tmp_path):
    engine, _, _, client = _client(tmp_path)
    payload = _payload()
    payload["programs"][0]["reward_type"] = "cps_recurring"
    try:
        with client:
            response = client.post("/api/research/commission-calculator", json=payload)
        assert response.status_code == 422
    finally:
        _cleanup(engine, client)
