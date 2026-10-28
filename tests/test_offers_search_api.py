from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import main
from backend.database import Base, get_session
from backend.models import Offer


@pytest.fixture
def offer_catalog_client(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'offer-catalog.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            db.add_all([
                Offer(
                    network="openaffiliate", external_id="oa-analytics-pro",
                    name="Creator Analytics Pro", description="Advanced analytics for creators",
                    category="analytics", reward_type="recurring_percentage", reward_value="25",
                    cookie_days=60, traffic_score=100.0, gravity_score=5.0,
                    normalized_gravity=5.0, epc=2.5, conversion_rate=0.12,
                    recurring_commission=True, source_stars=4.8, verified=True,
                    source_url="https://provider.example/oa-analytics-pro",
                ),
                Offer(
                    network="openaffiliate", external_id="oa-email",
                    name="Creator Email Suite", description="Newsletter and email automation",
                    category="email-marketing", reward_type="recurring_percentage", reward_value="15",
                    cookie_days=45, traffic_score=None, gravity_score=None,
                    normalized_gravity=None, epc=None, conversion_rate=None,
                    recurring_commission=True, source_stars=None, verified=False,
                ),
                Offer(
                    network="clickbank", external_id="cb-analytics-basic",
                    name="Creator Analytics Basic", description="Simple reporting for creators",
                    category="analytics", reward_type="one_time", reward_value="30",
                    cookie_days=30, traffic_score=30.0, gravity_score=1.0,
                    normalized_gravity=1.0, epc=1.0, conversion_rate=0.05,
                    recurring_commission=False, source_stars=4.0, verified=False,
                ),
                Offer(
                    network="jvzoo", external_id="jv-analytics-suite",
                    name="Analytics Suite", description="Analytics dashboard for publishers",
                    category="analytics", reward_type="recurring_percentage", reward_value="20",
                    cookie_days=90, traffic_score=200.0, gravity_score=8.0,
                    normalized_gravity=8.0, epc=3.0, conversion_rate=0.1,
                    recurring_commission=True, source_stars=4.5, verified=True,
                ),
                Offer(
                    network="cj", external_id="cj-unknown-metrics",
                    name="Metrics Unknown", description="A program without measured values",
                    category="tools", reward_type=None, reward_value=None,
                    cookie_days=None, traffic_score=None, gravity_score=None,
                    normalized_gravity=None, epc=None, conversion_rate=None,
                    recurring_commission=None, source_stars=None, verified=False,
                ),
            ])
            await db.commit()

    asyncio.run(setup())

    async def override_session():
        async with sessions() as db:
            yield db

    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    with TestClient(main.app) as client:
        yield client

    main.app.dependency_overrides.pop(get_session, None)
    asyncio.run(engine.dispose())


def test_offer_catalog_filters_network_category_reward_and_evidence_state(offer_catalog_client):
    response = offer_catalog_client.get(
        "/api/offers",
        params={
            "q": "creator",
            "network": "OPENAFFILIATE",
            "category": "analytics",
            "reward_type": "RECURRING_PERCENTAGE",
            "recurring_commission": "true",
            "min_cookie_days": 45,
            "provider_claimed_verified": "true",
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["count"] == 1
    assert result["total_count"] == 1
    assert result["data"][0]["external_id"] == "oa-analytics-pro"
    assert result["data"][0]["verification_basis"] == "provider_claimed_unattested"


def test_offer_catalog_searches_description_and_keeps_unknown_metrics_unknown(offer_catalog_client):
    response = offer_catalog_client.get("/api/offers?q=newsletter")
    assert response.status_code == 200
    result = response.json()
    assert result["total_count"] == 1
    item = result["data"][0]
    assert item["external_id"] == "oa-email"
    assert item["epc"] is None
    assert item["conversion_rate"] is None
    assert item["verification_basis"] == "provider_not_verified_or_unknown"


def test_offer_catalog_sorts_null_metrics_last_and_paginates(offer_catalog_client):
    first_page = offer_catalog_client.get(
        "/api/offers",
        params={"sort_by": "epc", "sort_order": "desc", "limit": 2},
    )
    assert first_page.status_code == 200
    first = first_page.json()
    assert first["count"] == 2
    assert first["total_count"] == 5
    assert [item["external_id"] for item in first["data"]] == [
        "jv-analytics-suite", "oa-analytics-pro",
    ]
    second_page = offer_catalog_client.get(
        "/api/offers",
        params={"sort_by": "epc", "sort_order": "desc", "limit": 2, "offset": 2},
    )
    assert second_page.status_code == 200
    second = second_page.json()
    assert second["offset"] == 2
    assert second["total_count"] == 5
    assert all(item["epc"] is None for item in second["data"])


def test_offer_catalog_rejects_unapproved_sort_fields_and_unbounded_paging(offer_catalog_client):
    bad_sort = offer_catalog_client.get("/api/offers?sort_by=verified;DROP")
    too_deep = offer_catalog_client.get("/api/offers?offset=100001")
    too_large = offer_catalog_client.get("/api/offers?limit=201")
    assert bad_sort.status_code == 422
    assert too_deep.status_code == 422
    assert too_large.status_code == 422
