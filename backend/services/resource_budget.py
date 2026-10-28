from __future__ import annotations

import asyncio
from datetime import datetime, time, timezone

from sqlalchemy import func, select

from backend.config import get_settings
from backend.core.errors import ResourceBudgetExceeded
from backend.database import SessionLocal
from backend.models import ResourceUsage
from backend.tenancy import get_workspace_id, workspace_scope

_lock = asyncio.Lock()


async def _acquire_workspace_budget_lock(db, workspace_id: str) -> None:
    """Serialize budget check-and-reserve across replicas on PostgreSQL.

    The lock is transaction-scoped, so it remains held through both cap checks
    and the reservation commit. SQLite/development retains the process-local
    asyncio lock in reserve(); production deployments should use PostgreSQL.
    """
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    await db.execute(
        select(
            func.pg_advisory_xact_lock(
                func.hashtext("omni-affiliate-os/resource-budget/v1"),
                func.hashtext(workspace_id),
            )
        )
    )


def _resolve_workspace_id(workspace_id: str | None = None) -> str:
    active = get_workspace_id()
    requested = str(workspace_id).strip() if workspace_id else None
    if requested and active and requested != active:
        raise ValueError("Resource budget workspace does not match the active workspace context")
    resolved = requested or active
    if not resolved:
        raise ValueError("Authorized workspace context required for resource budget operations")
    return resolved


def estimate_cost(input_tokens: int, output_tokens: int, local: bool = False) -> float:
    settings = get_settings()
    input_rate = settings.local_input_cost_per_million_usd if local else settings.llm_input_cost_per_million_usd
    output_rate = settings.local_output_cost_per_million_usd if local else settings.llm_output_cost_per_million_usd
    return max(0, input_tokens) * max(0, input_rate) / 1e6 + max(0, output_tokens) * max(0, output_rate) / 1e6


async def reserve(
    niche: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    *,
    workspace_id: str | None = None,
) -> str:
    owner_workspace_id = _resolve_workspace_id(workspace_id)
    settings = get_settings()
    now = datetime.now(timezone.utc)
    day_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    normalized_niche = " ".join(niche.lower().split())[:200] or "general"
    estimate = estimate_cost(input_tokens, output_tokens, provider.startswith("local"))

    # ResourceUsage is tenant-scoped, so both the daily cap and per-niche cap
    # are calculated inside the same authorized workspace context.
    # PostgreSQL's transaction-scoped advisory lock closes the cross-process
    # race between checking usage and inserting a new reservation.
    with workspace_scope(owner_workspace_id):
        async with _lock, SessionLocal() as db:
            await _acquire_workspace_budget_lock(db, owner_workspace_id)
            total = float(
                await db.scalar(
                    select(func.coalesce(func.sum(ResourceUsage.estimated_cost_usd), 0.0)).where(
                        ResourceUsage.created_at >= day_start
                    )
                )
                or 0
            )
            niche_used = float(
                await db.scalar(
                    select(func.coalesce(func.sum(ResourceUsage.estimated_cost_usd), 0.0)).where(
                        ResourceUsage.created_at >= day_start,
                        ResourceUsage.niche == normalized_niche,
                    )
                )
                or 0
            )
            if total + estimate > settings.resource_budget_usd_per_day + 1e-9:
                raise ResourceBudgetExceeded(
                    f"Daily model budget exceeded: ${total + estimate:.4f} > "
                    f"${settings.resource_budget_usd_per_day:.2f}"
                )
            if niche_used + estimate > settings.resource_budget_usd_per_niche + 1e-9:
                raise ResourceBudgetExceeded(f"Per-niche model budget exceeded for {normalized_niche!r}")
            row = ResourceUsage(
                niche=normalized_niche,
                provider=provider,
                model=model[:300],
                prompt_tokens_estimated=input_tokens,
                output_tokens_reserved=output_tokens,
                estimated_cost_usd=estimate,
                status="reserved",
            )
            db.add(row)
            await db.commit()
            return row.id


async def finalize(
    reservation_id: str,
    input_tokens: int,
    output_tokens: int,
    status: str = "completed",
    *,
    workspace_id: str | None = None,
) -> None:
    owner_workspace_id = _resolve_workspace_id(workspace_id)
    with workspace_scope(owner_workspace_id):
        async with SessionLocal() as db:
            row = await db.get(ResourceUsage, reservation_id)
            if not row:
                return
            row.input_tokens_actual = max(0, input_tokens)
            row.output_tokens_actual = max(0, output_tokens)
            if status == "completed":
                row.estimated_cost_usd = max(
                    row.estimated_cost_usd,
                    estimate_cost(input_tokens, output_tokens, row.provider.startswith("local")),
                )
            row.status = status[:40]
            row.completed_at = datetime.now(timezone.utc)
            await db.commit()


async def status(workspace_id: str | None = None) -> dict:
    owner_workspace_id = _resolve_workspace_id(workspace_id)
    settings = get_settings()
    now = datetime.now(timezone.utc)
    day_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    with workspace_scope(owner_workspace_id):
        async with SessionLocal() as db:
            total = float(
                await db.scalar(
                    select(func.coalesce(func.sum(ResourceUsage.estimated_cost_usd), 0.0)).where(
                        ResourceUsage.created_at >= day_start
                    )
                )
                or 0
            )
            rows = (
                await db.execute(
                    select(ResourceUsage.niche, func.sum(ResourceUsage.estimated_cost_usd))
                    .where(ResourceUsage.created_at >= day_start)
                    .group_by(ResourceUsage.niche)
                )
            ).all()
    return {
        "workspace_id": owner_workspace_id,
        "date_utc": now.date().isoformat(),
        "daily_budget_usd": settings.resource_budget_usd_per_day,
        "daily_estimated_used_usd": round(total, 6),
        "daily_estimated_remaining_usd": round(max(0, settings.resource_budget_usd_per_day - total), 6),
        "niche_budget_usd": settings.resource_budget_usd_per_niche,
        "niche_estimated_used_usd": {name: round(float(value or 0), 6) for name, value in rows},
        "note": "Configured-token-rate estimate; not a provider invoice. Reservation lock is process-local; use a distributed lock before multi-replica workers.",
    }
