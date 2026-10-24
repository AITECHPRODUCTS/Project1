from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import SessionLocal
from backend.models import ClickEvent, Conversion, PerformanceMemory


async def self_improver_loop(
    session: AsyncSession | None = None,
    *,
    lookback_days: int = 30,
) -> dict[str, Any]:
    settings = get_settings()
    owns_session = session is None
    if owns_session:
        session = SessionLocal()
    assert session is not None
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, min(lookback_days, 180)))
    try:
        conversions = list(
            (
                await session.scalars(
                    select(Conversion).where(
                        Conversion.created_at >= cutoff,
                        Conversion.hook.is_not(None),
                        Conversion.status.in_(["approved", "paid", "complete", "completed", "confirmed"]),
                    )
                )
            ).all()
        )
        clicks = list((await session.scalars(select(ClickEvent).where(ClickEvent.created_at >= cutoff))).all())
        click_counts: Counter[str] = Counter()
        for click in clicks:
            metadata = click.utm_json or {}
            hook = str(metadata.get("utm_content") or metadata.get("hook") or "").strip()
            if hook:
                click_counts[hook] += 1

        grouped: dict[str, list[Conversion]] = defaultdict(list)
        for conversion in conversions:
            hook = str(conversion.hook or conversion.utm_content or "").strip()
            if hook:
                grouped[hook].append(conversion)

        learned: list[dict[str, Any]] = []
        for hook, rows in grouped.items():
            conversion_count = len(rows)
            click_count = click_counts.get(hook, 0)
            if conversion_count < settings.min_conversions_for_learning or click_count <= 0:
                continue
            rate = conversion_count / max(conversion_count, click_count)
            if rate < settings.min_hook_conversion_rate:
                continue
            commission = round(sum(max(0.0, float(row.commission or 0)) for row in rows), 2)
            networks = sorted({row.network for row in rows})
            key = hashlib.sha256(f"perf:{hook}:{cutoff.date()}".encode()).hexdigest()
            learned.append(
                {
                    "memory_key": key,
                    "hook": hook,
                    "conversions": conversion_count,
                    "clicks": click_count,
                    "rate": rate,
                    "commission": commission,
                    "source_networks": networks,
                }
            )

        saved = 0
        for item in learned:
            row = await session.scalar(
                select(PerformanceMemory).where(PerformanceMemory.memory_key == item["memory_key"])
            )
            if row is None:
                row = PerformanceMemory(
                    memory_key=item["memory_key"],
                    hook=item["hook"],
                    conversion_count=item["conversions"],
                    click_count=item["clicks"],
                    conversion_rate=item["rate"],
                    commission_recorded=item["commission"],
                    source_networks=item["source_networks"],
                    status="candidate",
                    review_note="Not promoted to model behavior; review data quality, sample size and reversals.",
                )
                session.add(row)
            else:
                row.conversion_count = item["conversions"]
                row.click_count = item["clicks"]
                row.conversion_rate = item["rate"]
                row.commission_recorded = item["commission"]
                row.source_networks = item["source_networks"]
                row.status = "candidate"
            saved += 1
        if saved:
            # Tenant performance observations stay in the tenant database, never the shared doctrine index.
            await session.commit()

        return {
            "lookback_days": lookback_days,
            "conversions_scanned": len(conversions),
            "clicks_scanned": len(clicks),
            "performance_memory_candidates_saved": saved,
            "learned_hooks": learned,
            "learning_mode": "workspace-scoped performance memory; weight fine-tuning is separate",
            "promotion_status": "review_required",
        }
    finally:
        if owns_session:
            await session.close()
