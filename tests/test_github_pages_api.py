from __future__ import annotations

import asyncio
import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, ContentAsset, ExternalAction, PlatformExecutionControl, Workspace


def _page_payload():
    return {
        "title": "Creator resource links",
        "headline": "Helpful tools and resources",
        "subheadline": "A curated list of resources and products worth exploring.",
        "links": [{
            "label": "Analytics guide", "url": "https://example.com/analytics",
            "description": "A practical analytics guide.", "is_affiliate": False,
        }],
        "affiliate_disclosure": "",
        "footer_note": "Independent recommendations.",
    }


def _setup(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    active = {"workspace_id": "gh-pages-workspace-a"}

    async def override_session():
        async with sessions() as session:
            yield session

    async def platform_admin():
        return {
            "email": "gh-pages-admin@example.invalid",
            "user_id": "gh-pages-admin-1",
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
                Workspace(id="gh-pages-workspace-a", name="Pages workspace A", slug="gh-pages-workspace-a"),
                Workspace(id="gh-pages-workspace-b", name="Pages workspace B", slug="gh-pages-workspace-b"),
                PlatformExecutionControl(id=1, outbound_actions_paused=False),
            ])
            await db.commit()

    asyncio.run(create_workspaces())
    monkeypatch.setattr(main.settings, "github_pages_deploy_execute", True)
    monkeypatch.setattr(main.settings, "github_pages_repository", "exampleorg/creator-site")
    monkeypatch.setattr(main.settings, "github_pages_branch", "gh-pages")
    monkeypatch.setattr(main.settings, "github_pages_directory", "resources/links")
    monkeypatch.setattr(main.settings, "github_pages_token", "github_test_token_with_sufficient_length_12345")
    return engine, sessions, active


def test_github_pages_status_does_not_expose_token_and_reports_unverified_state(monkeypatch):
    engine, _, _ = _setup(monkeypatch)
    try:
        with TestClient(main.app) as client:
            response = client.get("/api/distribution/github-pages/status")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["configuration_ready"] is True
        assert data["publish_ready"] is True
        assert data["provider_connection_verified"] is False
        assert "github_test_token" not in response.text
    finally:
        asyncio.run(engine.dispose())


def test_github_pages_publish_uses_live_compliance_gate_and_external_action_idempotency(monkeypatch):
    engine, sessions, active = _setup(monkeypatch)
    try:
        compliance_calls = []
        publish_calls = []

        async def allow_compliance(*args, **kwargs):
            compliance_calls.append(kwargs)
            return object()

        async def fake_deploy(*, html_content, title, asset_id, settings):
            publish_calls.append((asset_id, html_content))
            return {
                "repository": "exampleorg/creator-site",
                "branch": "gh-pages",
                "directory": "resources/links",
                "content_path": "resources/links/index.html",
                "published_url": "https://exampleorg.github.io/creator-site/resources/links/",
                "page_sha256": hashlib.sha256(html_content.encode()).hexdigest(),
                "file_sha": "file-sha", "commit_sha": "commit-sha",
                "commit_url": "https://github.com/exampleorg/creator-site/commit/commit-sha",
                "status": "published",
            }

        monkeypatch.setattr(main, "_require_live_compliance_approval", allow_compliance)
        monkeypatch.setattr(main, "deploy_github_pages_html", fake_deploy)
        with TestClient(main.app) as client:
            page = client.post("/api/distribution/bio-links", json=_page_payload())
            assert page.status_code == 201, page.text
            asset_id = page.json()["id"]
            payload = {
                "asset_id": asset_id,
                "target_jurisdictions": ["US", "GB"],
                "confirm_live_publish": True,
            }
            headers = {"Idempotency-Key": "github-pages-deploy-key-0001"}
            first = client.post("/api/distribution/github-pages/deploy", json=payload, headers=headers)
            replay = client.post("/api/distribution/github-pages/deploy", json=payload, headers=headers)
        assert first.status_code == 200, first.text
        assert replay.status_code == 200, replay.text
        assert replay.json() == first.json()
        assert first.json()["deployment_status"] == "published"
        assert len(compliance_calls) == 1
        assert compliance_calls[0]["channel"] == "github_pages"
        assert len(publish_calls) == 1

        async def rows():
            async with sessions() as db:
                asset = await db.get(ContentAsset, asset_id)
                actions = list((await db.scalars(select(ExternalAction).where(
                    ExternalAction.action_type == "github_pages_deploy"
                ))).all())
                audits = list((await db.scalars(select(AuditLog).where(
                    AuditLog.action == "github_pages.deploy"
                ))).all())
                return asset, actions, audits
        asset, actions, audits = asyncio.run(rows())
        assert asset is not None
        assert asset.metadata_json["github_pages_publication"]["status"] == "published"
        assert len(actions) == 1 and actions[0].status == "completed"
        assert len(audits) == 1
    finally:
        asyncio.run(engine.dispose())


def test_github_pages_live_publish_requires_confirmation_and_enabled_configuration(monkeypatch):
    engine, _, _ = _setup(monkeypatch)
    invoked = []

    async def fake_deploy(**kwargs):
        invoked.append(True)
        return {"status": "published"}

    monkeypatch.setattr(main, "deploy_github_pages_html", fake_deploy)
    try:
        with TestClient(main.app) as client:
            page = client.post("/api/distribution/bio-links", json=_page_payload())
            asset_id = page.json()["id"]
            no_confirmation = client.post("/api/distribution/github-pages/deploy", json={
                "asset_id": asset_id, "target_jurisdictions": ["US"], "confirm_live_publish": False,
            }, headers={"Idempotency-Key": "github-pages-deploy-key-0002"})
            monkeypatch.setattr(main.settings, "github_pages_deploy_execute", False)
            disabled = client.post("/api/distribution/github-pages/deploy", json={
                "asset_id": asset_id, "target_jurisdictions": ["US"], "confirm_live_publish": True,
            }, headers={"Idempotency-Key": "github-pages-deploy-key-0003"})
        assert no_confirmation.status_code == 409
        assert disabled.status_code == 409
        assert not invoked
    finally:
        asyncio.run(engine.dispose())


def test_github_pages_deploy_rejects_cross_workspace_asset(monkeypatch):
    engine, _, active = _setup(monkeypatch)
    invoked = []

    async def fake_compliance(*args, **kwargs):
        return object()

    async def fake_deploy(**kwargs):
        invoked.append(True)
        return {"status": "published"}

    monkeypatch.setattr(main, "_require_live_compliance_approval", fake_compliance)
    monkeypatch.setattr(main, "deploy_github_pages_html", fake_deploy)
    try:
        with TestClient(main.app) as client:
            page = client.post("/api/distribution/bio-links", json=_page_payload())
            assert page.status_code == 201
            active["workspace_id"] = "gh-pages-workspace-b"
            response = client.post("/api/distribution/github-pages/deploy", json={
                "asset_id": page.json()["id"], "target_jurisdictions": ["US"], "confirm_live_publish": True,
            }, headers={"Idempotency-Key": "github-pages-deploy-key-0004"})
        assert response.status_code == 404
        assert not invoked
    finally:
        asyncio.run(engine.dispose())


def test_github_pages_reconcile_verifies_unknown_provider_outcome(monkeypatch):
    engine, sessions, _ = _setup(monkeypatch)
    try:
        async def allow_compliance(*args, **kwargs):
            return object()

        async def fail_after_provider_write(*, html_content, title, asset_id, settings):
            raise ConnectionError("simulated connection lost after provider accepted the write")

        async def verify_match(*, html_content, settings):
            return {
                "matches_expected_content": True,
                "repository": "exampleorg/creator-site",
                "branch": "gh-pages",
                "directory": "resources/links",
                "content_path": "resources/links/index.html",
                "published_url": "https://exampleorg.github.io/creator-site/resources/links/",
                "page_sha256": hashlib.sha256(html_content.encode()).hexdigest(),
                "file_sha": "remote-file-sha",
                "file_exists": True,
            }

        monkeypatch.setattr(main, "_require_live_compliance_approval", allow_compliance)
        monkeypatch.setattr(main, "deploy_github_pages_html", fail_after_provider_write)
        monkeypatch.setattr(main, "verify_github_pages_html", verify_match)
        with TestClient(main.app, raise_server_exceptions=False) as client:
            page = client.post("/api/distribution/bio-links", json=_page_payload())
            asset_id = page.json()["id"]
            response = client.post("/api/distribution/github-pages/deploy", json={
                "asset_id": asset_id, "target_jurisdictions": ["US"], "confirm_live_publish": True,
            }, headers={"Idempotency-Key": "github-pages-deploy-key-0005"})
        assert response.status_code == 502
        async def unknown_action():
            async with sessions() as db:
                asset = await db.get(ContentAsset, asset_id)
                action = await db.scalar(select(ExternalAction).where(ExternalAction.action_type == "github_pages_deploy"))
                return asset, action
        asset, action = asyncio.run(unknown_action())
        assert asset.metadata_json["github_pages_publication"]["status"] == "outcome_unknown"
        assert action.status == "unknown"

        with TestClient(main.app) as client:
            reconciled = client.post(f"/api/distribution/github-pages/{asset_id}/reconcile")
        assert reconciled.status_code == 200, reconciled.text
        assert reconciled.json()["deployment_status"] == "published"
        async def completed_action():
            async with sessions() as db:
                return await db.scalar(select(ExternalAction).where(ExternalAction.action_type == "github_pages_deploy"))
        action = asyncio.run(completed_action())
        assert action.status == "completed"
    finally:
        asyncio.run(engine.dispose())
