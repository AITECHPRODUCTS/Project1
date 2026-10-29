from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ExternalAction, PlatformExecutionControl
from backend.tenancy import workspace_scope


EXTERNAL_IDEMPOTENCY_KEY_RE = re.compile(r"[A-Za-z0-9._:-]{8,255}")


def external_action_fingerprint(action_type: str, provider: str, request_payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"action_type": action_type, "provider": provider, "request": request_payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def external_action_failure_status(exc: Exception) -> str:
    import httpx

    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(exc, (TimeoutError, ConnectionError, httpx.TransportError)):
        return "unknown"
    if isinstance(status_code, int) and status_code >= 500:
        return "unknown"
    return "failed"


def derive_workflow_action_key(base_key: str, index: int) -> str:
    """Produce a stable, bounded per-item key from the caller's workflow key."""
    key = (base_key or "").strip()
    if not EXTERNAL_IDEMPOTENCY_KEY_RE.fullmatch(key):
        raise HTTPException(428, "A valid Idempotency-Key header is required for live workflow publishing")
    if index < 0 or index >= 10:
        raise ValueError("Workflow publication index is outside the accepted range")
    digest = hashlib.sha256(f"workflow-s5:{key}:{index}".encode("utf-8")).hexdigest()
    return f"workflow-{digest}"


async def _require_platform_outbound_actions_unpaused(db: AsyncSession) -> None:
    """Fail closed unless the singleton control exists and new provider writes are permitted."""
    with workspace_scope(None):
        control = await db.scalar(
            select(PlatformExecutionControl)
            .where(PlatformExecutionControl.id == 1)
            .with_for_update()
        )
    if control is None:
        raise HTTPException(503, detail={
            "code": "PLATFORM_EXECUTION_CONTROL_UNAVAILABLE",
            "message": "Global provider-write control is unavailable; no new provider action was started.",
        })
    if control.outbound_actions_paused:
        raise HTTPException(423, detail={
            "code": "PLATFORM_OUTBOUND_ACTIONS_PAUSED",
            "message": "Platform Super Admin has paused new registry-gated provider writes.",
        })


async def claim_external_action(
    db: AsyncSession,
    *,
    workspace_id: str,
    action_type: str,
    provider: str,
    idempotency_key: str | None,
    request_payload: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    key = (idempotency_key or "").strip()
    if not EXTERNAL_IDEMPOTENCY_KEY_RE.fullmatch(key):
        raise HTTPException(428, "A valid Idempotency-Key header (8-255 letters, digits, period, underscore, colon or hyphen) is required for provider writes")
    request_hash = external_action_fingerprint(action_type, provider, request_payload)
    with workspace_scope(workspace_id):
        existing = await db.scalar(
            select(ExternalAction).where(
                ExternalAction.workspace_id == workspace_id,
                ExternalAction.action_type == action_type,
                ExternalAction.idempotency_key == key,
            )
        )
        if existing is None:
            unresolved = await db.scalar(
                select(ExternalAction).where(
                    ExternalAction.workspace_id == workspace_id,
                    ExternalAction.action_type == action_type,
                    ExternalAction.request_hash == request_hash,
                    ExternalAction.status.in_(["in_progress", "unknown"]),
                ).order_by(ExternalAction.created_at.desc())
            )
            if unresolved is not None:
                if unresolved.status == "in_progress":
                    created = unresolved.created_at
                    if created is not None and created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    if created is not None and datetime.now(timezone.utc) - created > timedelta(minutes=15):
                        unresolved.status = "unknown"
                        unresolved.error_type = "StaleInProgress"
                        await db.commit()
                raise HTTPException(409, "An earlier matching provider action is in progress or has an unknown outcome; reconcile it before retrying")
            await _require_platform_outbound_actions_unpaused(db)
            record = ExternalAction(
                workspace_id=workspace_id,
                action_type=action_type,
                idempotency_key=key,
                request_hash=request_hash,
                provider=provider[:80],
                status="in_progress",
                result_json={},
            )
            db.add(record)
            try:
                await db.commit()
                return record.id, None
            except IntegrityError:
                await db.rollback()
                existing = await db.scalar(
                    select(ExternalAction).where(
                        ExternalAction.workspace_id == workspace_id,
                        ExternalAction.action_type == action_type,
                        ExternalAction.idempotency_key == key,
                    )
                )
                if existing is None:
                    raise HTTPException(409, "Could not claim provider action; retry with the same Idempotency-Key")
        if existing.request_hash != request_hash:
            raise HTTPException(409, "Idempotency-Key was already used for a different request")
        if existing.status == "completed":
            return None, dict(existing.result_json or {})
        if existing.status == "in_progress":
            created = existing.created_at
            if created is not None and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created is not None and datetime.now(timezone.utc) - created > timedelta(minutes=15):
                existing.status = "unknown"
                existing.error_type = "StaleInProgress"
                await db.commit()
                raise HTTPException(409, "Previous provider action may have completed; reconcile before submitting again")
            raise HTTPException(409, "Provider action is still in progress; repeat the same Idempotency-Key after it finishes")
        if existing.status == "unknown":
            raise HTTPException(409, "Provider outcome is unknown; reconcile the provider before submitting another request")
        raise HTTPException(409, "Previous provider action failed; resolve it and use a new Idempotency-Key")


async def finish_external_action(
    db: AsyncSession,
    *,
    workspace_id: str,
    action_id: str,
    status: str,
    result: dict[str, Any] | None = None,
    error_type: str | None = None,
) -> None:
    with workspace_scope(workspace_id):
        record = await db.scalar(
            select(ExternalAction).where(
                ExternalAction.id == action_id,
                ExternalAction.workspace_id == workspace_id,
            )
        )
        if record is None:
            raise RuntimeError("External action idempotency record disappeared during provider execution")
        record.status = status
        record.error_type = error_type[:120] if error_type else None
        if result is not None:
            record.result_json = result
            remote_id = result.get("remote_id")
            record.remote_id = str(remote_id)[:255] if remote_id is not None else None
        await db.commit()
