from __future__ import annotations

import asyncio
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, ContentAsset, ExternalAction, PlatformExecutionControl, Workspace
from backend.services.bio_link_page import build_bio_link_page, validate_bio_link_url


def page_payload(**overrides):
    payload = {
        "title": "Creator links",
        "headline": "Helpful tools and resources",
        "subheadline": "A curated collection of resources I actually use.",
        "links": [
            {
                "label": "Analytics guide",
                "url": "https://example.com/analytics?ref=creator",
                "description": "Learn the basics of product analytics.",
                "is_affiliate": False,
            },
            {
                "label": "Recommended analytics software",
                "url": "https://merchant.example.com/analytics",
                "description": "A tool I may earn a commission from.",
                "is_affiliate": True,
            },
        ],
        "affiliate_disclosure": "Disclosure: I may earn a commission from qualifying purchases.",
        "footer_note": "Independent recommendations. Check current product terms.",
    }
    payload.update(overrides)
    return payload


def test_bio_link_html_escapes_untrusted_text_and_marks_affiliate_links():
    payload = page_payload(
        headline='Helpful <script>alert("x")</script> resources',
        links=[{
            "label": 'Offer <img src=x onerror="alert(1)">',
            "url": "https://example.com/offer",
            "description": "A <b>trusted</b> offer",
            "is_affiliate": True,
        }],
    )
    built = build_bio_link_page(payload, page_id="test-page-123")
    body = built["html"]
    assert "<script>alert(" not in body
    assert "&lt;script&gt;" in body
    assert "&lt;img" in body
    assert "onerror=&quot;alert(1)&quot;" in body
    assert 'rel="sponsored nofollow noopener noreferrer"' in body
    assert "affiliate-disclosure" in body
    assert built["affiliate_link_count"] == 1
    assert built["external_scripts"] is False


def test_bio_link_tracking_preserves_existing_query_and_adds_missing_utm_values():
    built = build_bio_link_page(page_payload(), page_id="page-123")
    first = parse_qs(urlsplit(built["tracked_urls"][0]).query)
    assert first["ref"] == ["creator"]
    assert first["utm_source"] == ["omni_affiliate_os"]
    assert first["utm_medium"] == ["bio_link"]
    assert first["utm_content"] == ["page-123.1"]
    assert len(built["sha256"]) == 64


@pytest.mark.parametrize("url", [
    "javascript:alert(1)",
    "data:text/html,<script>",
    "https://user:pass@example.com/secret",
    "https://127.0.0.1/private",
    "http://localhost/admin",
    "https://host.internal/private",
])
def test_bio_link_rejects_unsafe_destinations(url):
    with pytest.raises(ValueError):
        validate_bio_link_url(url)


def test_bio_link_schema_requires_disclosure_for_affiliate_links():
    from pydantic import ValidationError
    from backend.schemas import BioLinkPageCreateRequest
    payload = page_payload(affiliate_disclosure="")
    with pytest.raises(ValidationError, match="clear affiliate disclosure"):
        BioLinkPageCreateRequest(**payload)


def _setup(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    active = {"workspace_id": "bio-link-workspace-a"}

    async def override_session():
        async with sessions() as session:
            yield session

    async def platform_admin():
        return {
            "email": "bio-admin@example.invalid",
            "user_id": "bio-admin-1",
            "workspace_id": active["workspace_id"],
            "workspace_role": "owner",
            "is_admin": True,
        }

    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, platform_admin)

    async def create_workspaces():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            db.add_all([
                Workspace(id="bio-link-workspace-a", name="Bio workspace A", slug="bio-link-workspace-a"),
                Workspace(id="bio-link-workspace-b", name="Bio workspace B", slug="bio-link-workspace-b"),
                PlatformExecutionControl(id=1, outbound_actions_paused=False),
            ])
            await db.commit()

    asyncio.run(create_workspaces())
    return engine, sessions, active


def test_bio_link_api_creates_preview_and_isolates_workspace_assets(monkeypatch):
    engine, sessions, active = _setup(monkeypatch)
    try:
        with TestClient(main.app) as client:
            created = client.post("/api/distribution/bio-links", json=page_payload())
            assert created.status_code == 201, created.text
            asset_id = created.json()["id"]
            assert created.json()["status"] == "draft"
            assert created.json()["affiliate_link_count"] == 1
            assert created.json()["page_sha256"]
            preview = client.get(created.json()["preview_url"])
            assert preview.status_code == 200
            assert "affiliate-disclosure" in preview.text
            listing = client.get("/api/distribution/bio-links")
            assert listing.status_code == 200 and listing.json()["count"] == 1

            active["workspace_id"] = "bio-link-workspace-b"
            other_listing = client.get("/api/distribution/bio-links")
            other_preview = client.get(f"/api/distribution/bio-links/{asset_id}/preview")
            assert other_listing.status_code == 200 and other_listing.json()["count"] == 0
            assert other_preview.status_code == 404

        async def checks():
            async with sessions() as db:
                rows = list((await db.scalars(select(ContentAsset))).all())
                audit = list((await db.scalars(select(AuditLog).where(AuditLog.action == "bio_link_page.created"))).all())
                return rows, audit
        rows, audit = asyncio.run(checks())
        assert len(rows) == 1 and rows[0].asset_type == "bio_link_page"
        assert len(audit) == 1 and audit[0].details_json["external_scripts"] is False
    finally:
        asyncio.run(engine.dispose())


def test_bio_link_publish_uses_compliance_gate_and_idempotency(monkeypatch):
    engine, sessions, active = _setup(monkeypatch)
    monkeypatch.setattr(main.settings, "cms_publish_execute", True)
    compliance_calls = []
    publish_calls = []

    async def allow_compliance(*args, **kwargs):
        compliance_calls.append(kwargs)
        return object()

    async def fake_publish(**kwargs):
        publish_calls.append(kwargs)
        return {"provider": "wordpress", "status": "publish", "remote_id": "cms-bio-123", "url": "https://example.com/my-links"}

    monkeypatch.setattr(main, "_require_live_compliance_approval", allow_compliance, raising=False)
    monkeypatch.setattr(main, "publish_article", fake_publish)
    try:
        with TestClient(main.app) as client:
            created = client.post("/api/distribution/bio-links", json=page_payload())
            assert created.status_code == 201, created.text
            asset_id = created.json()["id"]
            publish_payload = {
                "provider": "wordpress",
                "target_jurisdictions": ["US", "GB"],
                "canonical_url": "https://example.com/my-links",
                "status": "publish",
                "confirm_live_publish": True,
            }
            headers = {"Idempotency-Key": "bio-link-publish-key-0001"}
            first = client.post(f"/api/distribution/bio-links/{asset_id}/publish", json=publish_payload, headers=headers)
            replay = client.post(f"/api/distribution/bio-links/{asset_id}/publish", json=publish_payload, headers=headers)
            assert first.status_code == 200, first.text
            assert replay.status_code == 200, replay.text
            assert replay.json() == first.json()
            assert first.json()["asset_status"] == "published"
            assert len(compliance_calls) == 1
            assert len(publish_calls) == 1

        async def rows():
            async with sessions() as db:
                asset = await db.get(ContentAsset, asset_id)
                actions = list((await db.scalars(select(ExternalAction).where(ExternalAction.action_type == "bio_link_publish"))).all())
                audits = list((await db.scalars(select(AuditLog).where(AuditLog.action.in_([
                    "bio_link_page.created", "bio_link_publish", "bio_link_publish_idempotency_replay"
                ])))).all())
                return asset, actions, audits
        asset, actions, audits = asyncio.run(rows())
        assert asset is not None and asset.status == "published"
        assert len(actions) == 1 and actions[0].status == "completed"
        assert len(audits) >= 2
    finally:
        asyncio.run(engine.dispose())


def test_bio_link_live_publish_requires_explicit_confirmation(monkeypatch):
    engine, _, _ = _setup(monkeypatch)
    try:
        with TestClient(main.app) as client:
            created = client.post("/api/distribution/bio-links", json=page_payload())
            asset_id = created.json()["id"]
            response = client.post(
                f"/api/distribution/bio-links/{asset_id}/publish",
                json={
                    "provider": "wordpress",
                    "canonical_url": "https://example.com/my-links",
                    "status": "publish",
                    "confirm_live_publish": False,
                },
                headers={"Idempotency-Key": "bio-link-publish-key-0002"},
            )
        assert response.status_code == 409
    finally:
        asyncio.run(engine.dispose())
