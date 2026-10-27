from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, SkillPackage, Workspace
from backend.services.skill_packager import build_skill_package
from backend.tenancy import workspace_scope


SCHEMA_IN = {
    "type": "object",
    "properties": {"topic": {"type": "string", "minLength": 3}},
    "required": ["topic"],
    "additionalProperties": False,
}
SCHEMA_OUT = {
    "type": "object",
    "properties": {"summary": {"type": "string", "minLength": 3}},
    "required": ["summary"],
    "additionalProperties": False,
}


def package_payload(**overrides):
    payload = {
        "skill_id": "content/summary-draft",
        "display_name": "Summary draft helper",
        "version": "1.0.0",
        "description": "Create a concise summary draft from a supplied topic and facts.",
        "stage": "S2",
        "capabilities": ["content.draft", "research.read"],
        "input_schema": SCHEMA_IN,
        "output_schema": SCHEMA_OUT,
        "instructions_markdown": "# Task\nProduce a concise summary from the user-provided topic. Do not invent claims.",
        "test_cases": [
            {
                "name": "basic topic",
                "input": {"topic": "affordable analytics"},
                "expected_output": {"summary": "Compare product analytics choices."},
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_skill_package_checksum_is_stable_and_contract_report_does_not_claim_execution():
    payload = package_payload()
    first = build_skill_package(payload)
    second = build_skill_package(payload)
    assert first["package_sha256"] == second["package_sha256"]
    assert len(first["package_sha256"]) == 64
    report = first["validation_report"]
    assert report["all_fixtures_passed"] is True
    assert report["fixtures_passed"] == 1
    assert report["skill_instructions_executed"] is False
    assert report["runtime_execution_tested"] is False


def test_skill_package_reports_fixture_type_and_required_field_failures():
    payload = package_payload(test_cases=[{
        "name": "missing topic",
        "input": {"extra": "not allowed"},
        "expected_output": {"summary": ""},
    }])
    result = build_skill_package(payload)
    report = result["validation_report"]
    assert report["all_fixtures_passed"] is False
    assert report["fixtures_failed"] == 1
    assert report["cases"][0]["input_errors"]
    assert report["cases"][0]["expected_output_errors"]


def test_invalid_or_unsupported_json_schema_is_rejected():
    payload = package_payload(input_schema={"$ref": "https://evil.example/schema.json"})
    with pytest.raises(ValueError, match="unsupported schema keywords"):
        build_skill_package(payload)


def test_risky_capabilities_are_flagged_without_executing_them():
    result = build_skill_package(package_payload(capabilities=["content.draft", "publisher.write", "ads.spend"]))
    assert result["validation_report"]["capabilities_requiring_human_review"] == ["ads.spend", "publisher.write"]
    assert result["validation_report"]["declarative_only"] is True


def _setup(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    active = {"workspace_id": "skill-workspace-a"}

    async def override_session():
        async with sessions() as session:
            yield session

    async def platform_admin():
        return {
            "email": "skill-admin@example.invalid",
            "user_id": "skill-admin-1",
            "workspace_id": active["workspace_id"],
            "workspace_role": "owner",
            "is_admin": False,
        }

    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, platform_admin)

    async def create_workspaces():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            db.add_all([
                Workspace(id="skill-workspace-a", name="Skill workspace A", slug="skill-workspace-a"),
                Workspace(id="skill-workspace-b", name="Skill workspace B", slug="skill-workspace-b"),
            ])
            await db.commit()

    asyncio.run(create_workspaces())
    return engine, sessions, active


def test_skill_package_api_persists_audits_reviews_and_prevents_duplicate_versions(tmp_path, monkeypatch):
    del tmp_path
    engine, sessions, active = _setup(monkeypatch)
    try:
        with TestClient(main.app) as client:
            created = client.post("/api/skills/packages", json=package_payload())
            assert created.status_code == 201, created.text
            body = created.json()
            assert body["status"] == "review_required"
            assert body["validation_report"]["all_fixtures_passed"] is True
            assert body["execution_boundary"].startswith("Declarative package only")
            assert body["package_sha256"]

            duplicate = client.post("/api/skills/packages", json=package_payload())
            assert duplicate.status_code == 409, duplicate.text

            listing = client.get("/api/skills/packages")
            assert listing.status_code == 200
            assert listing.json()["count"] == 1
            assert "instructions_markdown" not in listing.json()["data"][0]

            missing_confirmation = client.post(f"/api/skills/packages/{body['id']}/review", json={
                "decision": "approve", "confirm_contract_reviewed": False,
            })
            assert missing_confirmation.status_code == 409

            approved = client.post(f"/api/skills/packages/{body['id']}/review", json={
                "decision": "approve", "confirm_contract_reviewed": True,
                "reviewer_notes": "Reviewed contract and capability list.",
            })
            assert approved.status_code == 200, approved.text
            assert approved.json()["status"] == "approved"
            assert approved.json()["reviewed_by"] == "skill-admin@example.invalid"

            immutable = client.post(f"/api/skills/packages/{body['id']}/review", json={
                "decision": "reject", "reviewer_notes": "Cannot revise an approved version.",
            })
            assert immutable.status_code == 409

            async def rows():
                async with sessions() as db:
                    packages = list((await db.scalars(select(SkillPackage))).all())
                    events = list((await db.scalars(select(AuditLog).where(
                        AuditLog.workspace_id == "skill-workspace-a",
                        AuditLog.action.in_(["skill_package.created", "skill_package.reviewed"]),
                    ))).all())
                    return packages, events
            packages, events = asyncio.run(rows())
            assert len(packages) == 1 and packages[0].status == "approved"
            assert len(events) == 2
            assert all(event.details_json["declarative_only"] is True for event in events)
    finally:
        asyncio.run(engine.dispose())


def test_skill_package_api_keeps_versions_tenant_scoped(monkeypatch):
    engine, _, active = _setup(monkeypatch)
    try:
        with TestClient(main.app) as client:
            created = client.post("/api/skills/packages", json=package_payload())
            assert created.status_code == 201, created.text
            package_id = created.json()["id"]
            active["workspace_id"] = "skill-workspace-b"
            listing = client.get("/api/skills/packages")
            assert listing.status_code == 200 and listing.json()["count"] == 0
            hidden = client.get(f"/api/skills/packages/{package_id}")
            assert hidden.status_code == 404
            # The same skill id/version is independently available in another workspace.
            other = client.post("/api/skills/packages", json=package_payload())
            assert other.status_code == 201, other.text
    finally:
        asyncio.run(engine.dispose())


def test_failed_fixture_is_stored_as_draft_and_cannot_be_approved(monkeypatch):
    engine, _, _ = _setup(monkeypatch)
    broken = package_payload(test_cases=[{
        "name": "invalid fixture",
        "input": {"topic": "x", "surprise": True},
        "expected_output": {"summary": ""},
    }])
    try:
        with TestClient(main.app) as client:
            created = client.post("/api/skills/packages", json=broken)
            assert created.status_code == 201, created.text
            body = created.json()
            assert body["status"] == "draft"
            review = client.post(f"/api/skills/packages/{body['id']}/review", json={
                "decision": "approve", "confirm_contract_reviewed": True,
            })
            assert review.status_code == 409
            assert review.json()["detail"]["code"] == "SKILL_CONTRACT_FIXTURES_FAILED"
    finally:
        asyncio.run(engine.dispose())
