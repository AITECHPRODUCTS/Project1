from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, Offer, OfferEvidenceSnapshot, Workspace
from backend.schemas import OfferEvidenceCaptureRequest
from backend.services import offer_evidence


def test_capture_offer_source_snapshots_records_sanitized_html_and_hashes(monkeypatch):
    body = (
        "<html><head><title>Official program terms</title>"
        '<meta name="description" content="Publisher terms and conditions"></head>'
        "<body><nav>navigation</nav><h1>Commission terms</h1>"
        "<p>Cookie duration is described here.</p><script>secret-looking-code()</script></body></html>"
    )

    async def fake_fetch(url: str, *, max_bytes: int, timeout: float):
        assert max_bytes == offer_evidence.MAX_SOURCE_BYTES
        assert timeout == 12.0
        return body, "text/html; charset=utf-8", 200

    monkeypatch.setattr(offer_evidence, "fetch_public_page", fake_fetch)
    result = asyncio.run(offer_evidence.capture_offer_source_snapshots(["https://merchant.example/terms"]))
    assert len(result) == 1
    item = result[0]
    assert item["fetch_status"] == "fetched"
    assert item["title"] == "Official program terms"
    assert item["description"] == "Publisher terms and conditions"
    assert "Commission terms" in item["excerpt"]
    assert "navigation" not in item["excerpt"]
    assert "secret-looking-code" not in item["excerpt"]
    assert len(item["response_sha256"]) == 64
    assert len(item["excerpt_sha256"]) == 64
    assert item["http_status"] == 200
    assert item["fetched_at"].tzinfo is not None


def test_capture_offer_source_snapshots_persists_failure_without_leaking_diagnostics(monkeypatch):
    async def fake_fetch(url: str, **kwargs):
        raise TimeoutError("private transport diagnostic must not be stored")

    monkeypatch.setattr(offer_evidence, "fetch_public_page", fake_fetch)
    result = asyncio.run(offer_evidence.capture_offer_source_snapshots(["https://merchant.example/terms"]))
    assert result[0]["fetch_status"] == "fetch_failed"
    assert result[0]["error_code"] == "TimeoutError"
    assert "detail" not in result[0]
    assert result[0]["excerpt"] == ""
    assert result[0]["response_sha256"] is None


@pytest.mark.parametrize(
    "url",
    [
        "http://merchant.example/terms",
        "https://user:pass@merchant.example/terms",
        "https://127.0.0.1/internal",
        "https://merchant.example:8443/terms",
        "https://merchant.example/terms?access_token=not-a-real-token",
    ],
)
def test_offer_evidence_capture_request_rejects_unsafe_or_credential_bearing_urls(url):
    with pytest.raises(ValidationError):
        OfferEvidenceCaptureRequest(source_urls=[url])


def test_offer_evidence_capture_request_deduplicates_sources():
    request = OfferEvidenceCaptureRequest(source_urls=[
        "https://merchant.example/terms",
        "https://merchant.example/terms",
    ])
    assert request.source_urls == ["https://merchant.example/terms"]


def _evidence_client(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'offer-evidence.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            primary = Workspace(name="Evidence A", slug="evidence-a")
            secondary = Workspace(name="Evidence B", slug="evidence-b")
            db.add_all([primary, secondary])
            await db.flush()
            offer = Offer(
                network="openaffiliate",
                external_id="evidence-offer",
                name="Evidence Offer",
                description="Provider terms need capture",
            )
            db.add(offer)
            await db.commit()
            return primary.id, secondary.id, offer.id

    workspace_a, workspace_b, offer_id = asyncio.run(setup())
    user = {
        "workspace_id": workspace_a,
        "workspace_role": "owner",
        "email": "evidence-reviewer@example.test",
        "user_id": "evidence-reviewer",
        "is_admin": False,
    }

    async def override_session():
        async with sessions() as db:
            yield db

    async def override_auth():
        return user

    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, override_auth)

    async def fake_capture(urls: list[str]):
        return [
            {
                "source_id": f"E{index:02d}",
                "source_url": url,
                "source_host": urlparse(url).hostname or "",
                "title": "Official terms page",
                "description": "Terms for publishers",
                "excerpt": "Commission terms are described for the publisher.",
                "response_sha256": "a" * 64,
                "excerpt_sha256": "b" * 64,
                "http_status": 200,
                "content_type": "text/html",
                "fetch_status": "fetched",
                "error_code": None,
                "fetched_at": datetime.now(timezone.utc),
            }
            for index, url in enumerate(urls, start=1)
        ]

    monkeypatch.setattr(main, "capture_offer_source_snapshots", fake_capture)
    return engine, sessions, user, workspace_b, offer_id, TestClient(main.app)


def _close_evidence_client(engine, client):
    main.app.dependency_overrides.pop(get_session, None)
    main.app.dependency_overrides.pop(main.require_auth, None)
    client.close()
    asyncio.run(engine.dispose())


def test_offer_evidence_capture_persists_audit_and_enforces_workspace_isolation(tmp_path, monkeypatch):
    engine, sessions, user, workspace_b, offer_id, client = _evidence_client(tmp_path, monkeypatch)
    url = "https://merchant.example/affiliate-terms"
    try:
        with client:
            captured = client.post(
                f"/api/offers/{offer_id}/evidence-snapshots",
                json={"source_urls": [url]},
            )
            assert captured.status_code == 200, captured.text
            body = captured.json()
            assert body["count"] == 1
            assert body["data"][0]["fetch_status"] == "fetched"
            assert body["data"][0]["response_sha256"] == "a" * 64
            assert body["freshness"]["status"] == "fresh"
            assert body["evidence_basis"] == "captured_public_page_text_unverified"

            async def verify_storage():
                async with sessions() as db:
                    snapshot_count = await db.scalar(
                        select(func.count()).select_from(OfferEvidenceSnapshot)
                    )
                    audits = list((await db.scalars(
                        select(AuditLog).where(AuditLog.action == "offer_evidence_snapshot_capture")
                    )).all())
                    return snapshot_count, audits

            snapshot_count, audits = asyncio.run(verify_storage())
            assert snapshot_count == 1
            assert len(audits) == 1
            assert audits[0].outcome == "ok"

            listed = client.get(f"/api/offers/{offer_id}/evidence-snapshots")
            assert listed.status_code == 200
            assert listed.json()["count"] == 1
            assert listed.json()["freshness"]["status"] == "fresh"
            assert listed.json()["data"][0]["source_url"] == url

            user["workspace_id"] = workspace_b
            isolated = client.get(f"/api/offers/{offer_id}/evidence-snapshots")
            assert isolated.status_code == 200
            assert isolated.json()["count"] == 0
            assert isolated.json()["freshness"]["status"] == "no_sources_supplied"

            user["workspace_id"] = str(workspace_b)
            user["workspace_role"] = "member"
            denied = client.post(
                f"/api/offers/{offer_id}/evidence-snapshots",
                json={"source_urls": [url]},
            )
            assert denied.status_code == 403
    finally:
        _close_evidence_client(engine, client)
