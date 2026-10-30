from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

POLICY_VERSION = 1
MAX_SOURCE_AGE_HOURS = 24
MAX_FUTURE_SKEW_SECONDS = 300


def _utc_now(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("freshness evaluation time must be timezone-aware")
    return result.astimezone(timezone.utc)


def _source_host(value: Any) -> str | None:
    try:
        host = urlparse(str(value or "")).hostname
    except (TypeError, ValueError):
        return None
    return host[:253].lower() if host else None


def evaluate_source_freshness(
    source_snapshots: Any,
    source_urls: Any = None,
    *,
    now: datetime | None = None,
    max_age_hours: int = MAX_SOURCE_AGE_HOURS,
    future_tolerance_seconds: int = MAX_FUTURE_SKEW_SECONDS,
) -> dict[str, Any]:
    """Check capture timestamp policy, not source-page truth, publication date, or currentness."""
    if isinstance(max_age_hours, bool) or not isinstance(max_age_hours, int) or not 1 <= max_age_hours <= 720:
        raise ValueError("max_age_hours must be an integer between 1 and 720")
    if isinstance(future_tolerance_seconds, bool) or not isinstance(future_tolerance_seconds, int) or not 0 <= future_tolerance_seconds <= 3600:
        raise ValueError("future_tolerance_seconds must be an integer between 0 and 3600")

    checked_at = _utc_now(now)
    max_age_seconds = max_age_hours * 3600
    raw_urls = source_urls if isinstance(source_urls, list) else []
    supplied_urls = list(dict.fromkeys(value.strip() for value in raw_urls if isinstance(value, str) and value.strip()))[:10]
    snapshots = source_snapshots if isinstance(source_snapshots, list) else []
    snapshot_urls = list(dict.fromkeys(
        str(item.get("url") or "").strip()
        for item in snapshots if isinstance(item, dict) and str(item.get("url") or "").strip()
    ))[:10]

    def result_without_items(status: str, allowed: bool, message: str) -> dict[str, Any]:
        return {
            "policy_version": POLICY_VERSION,
            "checked_at": checked_at.isoformat(),
            "max_age_hours": max_age_hours,
            "future_tolerance_seconds": future_tolerance_seconds,
            "status": status,
            "source_count": 0,
            "fresh_count": 0,
            "blocked_count": 0 if allowed else 1,
            "approval_allowed": allowed,
            "capture_window_satisfied": False,
            "message": message,
            "items": [],
        }

    if not supplied_urls and not snapshot_urls:
        return result_without_items(
            "no_sources_supplied", True,
            "No sources were supplied. Editorial review may proceed, but product facts and currentness remain unverified.",
        )
    if set(supplied_urls) != set(snapshot_urls):
        return result_without_items(
            "source_inventory_mismatch", False,
            "The supplied source URL inventory does not match stored snapshots. Create a new revision and recapture the evidence before approving.",
        )

    items: list[dict[str, Any]] = []
    issues: list[str] = []
    for snapshot in snapshots[:10]:
        if not isinstance(snapshot, dict):
            items.append({
                "source_id": None,
                "host": None,
                "fetch_status": "invalid_snapshot",
                "status": "invalid_snapshot_status",
                "fetched_at": None,
                "age_seconds": None,
            })
            issues.append("invalid_snapshot_status")
            continue

        source_id = str(snapshot.get("source_id") or "")[:16] or None
        host = _source_host(snapshot.get("url"))
        fetch_status = str(snapshot.get("status") or "missing_status")[:40]
        captured_at = snapshot.get("fetched_at")
        freshness_status = "fresh"
        age_seconds: int | None = None

        if fetch_status == "fetch_failed":
            freshness_status = "source_fetch_failed"
        elif fetch_status != "fetched":
            freshness_status = "invalid_snapshot_status"
        elif not isinstance(captured_at, str) or not captured_at.strip():
            freshness_status = "invalid_timestamp"
        else:
            try:
                parsed = datetime.fromisoformat(captured_at.strip().replace("Z", "+00:00"))
            except (TypeError, ValueError, OverflowError):
                parsed = None
            if parsed is None or parsed.tzinfo is None or parsed.utcoffset() is None:
                freshness_status = "invalid_timestamp"
            else:
                age = (checked_at - parsed.astimezone(timezone.utc)).total_seconds()
                if age < -future_tolerance_seconds:
                    freshness_status = "future_dated"
                    age_seconds = int(round(age))
                elif age > max_age_seconds:
                    freshness_status = "stale"
                    age_seconds = int(round(age))
                else:
                    freshness_status = "fresh"
                    age_seconds = max(0, int(round(age)))

        items.append({
            "source_id": source_id,
            "host": host,
            "fetch_status": fetch_status,
            "status": freshness_status,
            "fetched_at": str(captured_at)[:80] if isinstance(captured_at, str) else None,
            "age_seconds": age_seconds,
        })
        if freshness_status != "fresh":
            issues.append(freshness_status)

    priorities = ("invalid_timestamp", "future_dated", "stale", "source_fetch_failed", "invalid_snapshot_status")
    status = next((issue for issue in priorities if issue in issues), "fresh")
    allowed = status == "fresh"
    messages = {
        "fresh": (
            f"All {len(items)} captured source snapshot(s) are within the {max_age_hours}-hour capture-time window. "
            "This does not verify source-page truth, publication date, completeness, price validity, or eligibility."
        ),
        "invalid_timestamp": "A source snapshot has a missing, naive, or invalid capture timestamp. Create a new revision before approving.",
        "future_dated": "A source snapshot is materially future-dated. Create a new revision to recapture evidence before approving.",
        "stale": f"At least one source snapshot is older than {max_age_hours} hours. Create a new revision to recapture evidence before approving.",
        "source_fetch_failed": "At least one supplied source failed to fetch. Correct its reachability or remove that source in a new revision before approving.",
        "invalid_snapshot_status": "A source snapshot has an unsupported status. Rebuild the evidence in a new revision before approving.",
    }
    return {
        "policy_version": POLICY_VERSION,
        "checked_at": checked_at.isoformat(),
        "max_age_hours": max_age_hours,
        "future_tolerance_seconds": future_tolerance_seconds,
        "status": status,
        "source_count": len(items),
        "fresh_count": sum(1 for item in items if item["status"] == "fresh"),
        "blocked_count": sum(1 for item in items if item["status"] != "fresh"),
        "approval_allowed": allowed,
        "capture_window_satisfied": allowed and status == "fresh",
        "message": messages[status],
        "items": items,
    }
