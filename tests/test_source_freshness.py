from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.services.source_freshness import evaluate_source_freshness


NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def snapshot(fetched_at: str, *, status: str = "fetched", url: str = "https://vendor.example/product"):
    return {"source_id": "S01", "url": url, "status": status, "fetched_at": fetched_at}


def test_recent_source_is_reviewable_but_not_fact_verified():
    url = "https://vendor.example/product?token=not-returned"
    result = evaluate_source_freshness([snapshot((NOW - timedelta(hours=2)).isoformat(), url=url)], [url], now=NOW)
    assert result["status"] == "fresh"
    assert result["approval_allowed"] is True
    assert result["capture_window_satisfied"] is True
    assert result["source_count"] == result["fresh_count"] == 1
    assert result["items"][0]["host"] == "vendor.example"
    assert "token" not in str(result)
    assert "truth" in result["message"]


def test_stale_source_blocks_approval_after_capture_window():
    url = "https://vendor.example/product"
    result = evaluate_source_freshness([snapshot((NOW - timedelta(hours=24, seconds=1)).isoformat(), url=url)], [url], now=NOW)
    assert result["status"] == "stale"
    assert result["approval_allowed"] is False
    assert result["blocked_count"] == 1
    assert "new revision" in result["message"]


def test_materially_future_dated_source_blocks_approval_but_clock_skew_is_tolerated():
    url = "https://vendor.example/product"
    tolerated = evaluate_source_freshness([snapshot((NOW + timedelta(minutes=2)).isoformat(), url=url)], [url], now=NOW)
    assert tolerated["status"] == "fresh"
    assert tolerated["items"][0]["age_seconds"] == 0
    rejected = evaluate_source_freshness([snapshot((NOW + timedelta(minutes=6)).isoformat(), url=url)], [url], now=NOW)
    assert rejected["status"] == "future_dated"
    assert rejected["approval_allowed"] is False


@pytest.mark.parametrize("timestamp", ["", "not-a-timestamp", "2026-10-29T11:00:00"])
def test_invalid_or_timezone_naive_capture_timestamps_block_approval(timestamp: str):
    url = "https://vendor.example/product"
    result = evaluate_source_freshness([snapshot(timestamp, url=url)], [url], now=NOW)
    assert result["status"] == "invalid_timestamp"
    assert result["approval_allowed"] is False


def test_failed_fetch_and_missing_snapshot_inventory_block_approval():
    url = "https://vendor.example/product"
    failed = evaluate_source_freshness([snapshot(NOW.isoformat(), status="fetch_failed", url=url)], [url], now=NOW)
    assert failed["status"] == "source_fetch_failed"
    assert failed["approval_allowed"] is False
    missing = evaluate_source_freshness([], [url], now=NOW)
    assert missing["status"] == "source_inventory_mismatch"
    assert missing["approval_allowed"] is False


def test_no_sources_keeps_human_review_possible_without_claiming_freshness():
    result = evaluate_source_freshness([], [], now=NOW)
    assert result["status"] == "no_sources_supplied"
    assert result["approval_allowed"] is True
    assert result["capture_window_satisfied"] is False
    assert "remain unverified" in result["message"]


def test_mismatched_snapshot_inventory_fails_closed():
    result = evaluate_source_freshness(
        [snapshot(NOW.isoformat(), url="https://vendor.example/other")],
        ["https://vendor.example/product"], now=NOW,
    )
    assert result["status"] == "source_inventory_mismatch"
    assert result["approval_allowed"] is False


def test_freshness_evaluation_rejects_invalid_policy_arguments():
    with pytest.raises(ValueError):
        evaluate_source_freshness([], [], now=NOW, max_age_hours=0)
    with pytest.raises(ValueError):
        evaluate_source_freshness([], [], now=NOW, future_tolerance_seconds=-1)
