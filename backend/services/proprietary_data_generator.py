from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def build_proprietary_dataset(
    assignments: Iterable[Any],
    events: Iterable[Any],
    *,
    min_impressions: int = 100,
    min_conversions: int = 5,
) -> dict[str, Any]:
    """Build aggregate, review-only candidates from the persisted experiment ledger.

    Visitor IDs are never exported. App-recorded events are not represented as
    provider-attested ground truth, and this function does not train any model.
    """
    for name, value in (("min_impressions", min_impressions), ("min_conversions", min_conversions)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")

    assignment_rows, event_rows = list(assignments), list(events)
    assignment_index: dict[str, tuple[str, str]] = {}
    experiments: dict[str, dict[str, Any]] = {}
    ignored_assignments = 0

    for item in assignment_rows:
        assignment_id = str(getattr(item, "id", "") or "").strip()
        key = str(getattr(item, "experiment_key", "") or "").strip()
        variant = str(getattr(item, "variant", "") or "").strip().upper()
        headline_a = str(getattr(item, "headline_a", "") or "").strip()
        headline_b = str(getattr(item, "headline_b", "") or "").strip()
        if not assignment_id or not key or variant not in {"A", "B"}:
            ignored_assignments += 1
            continue
        group = experiments.setdefault(key, {
            "snapshots": set(),
            "variants": set(),
            "arms": {
                "A": {"assigned_visitors": 0, "impressions": 0, "conversions": 0},
                "B": {"assigned_visitors": 0, "impressions": 0, "conversions": 0},
            },
        })
        group["snapshots"].add((headline_a, headline_b))
        group["variants"].add(variant)
        group["arms"][variant]["assigned_visitors"] += 1
        assignment_index[assignment_id] = (key, variant)

    seen_ids: set[str] = set()
    duplicates = ignored_types = unmapped = 0
    for item in event_rows:
        event_id = str(getattr(item, "event_id", "") or "").strip()
        if event_id and event_id in seen_ids:
            duplicates += 1
            continue
        if event_id:
            seen_ids.add(event_id)
        event_type = str(getattr(item, "event_type", "") or "").strip().lower()
        if event_type not in {"impression", "conversion"}:
            ignored_types += 1
            continue
        mapping = assignment_index.get(str(getattr(item, "assignment_id", "") or "").strip())
        if mapping is None:
            unmapped += 1
            continue
        key, variant = mapping
        bucket = experiments[key]["arms"][variant]
        bucket["impressions" if event_type == "impression" else "conversions"] += 1

    rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, str]] = []
    low_sample = 0
    for key in sorted(experiments):
        group = experiments[key]
        if len(group["snapshots"]) != 1:
            exclusions.append({"experiment_key": key, "reason": "inconsistent_headline_snapshot"})
            continue
        if group["variants"] != {"A", "B"}:
            exclusions.append({"experiment_key": key, "reason": "both_variants_required"})
            continue
        headline_a, headline_b = next(iter(group["snapshots"]))
        a, b = group["arms"]["A"], group["arms"]["B"]
        rate_a = a["conversions"] / a["impressions"] if a["impressions"] else None
        rate_b = b["conversions"] / b["impressions"] if b["impressions"] else None
        reasons = []
        for label, arm in (("A", a), ("B", b)):
            if arm["impressions"] < min_impressions:
                reasons.append(f"variant_{label}_below_min_impressions")
            if arm["conversions"] < min_conversions:
                reasons.append(f"variant_{label}_below_min_conversions")
        eligible = not reasons
        if not eligible:
            low_sample += 1
        relative_label = (
            "not_comparable_no_impression_data" if rate_a is None or rate_b is None
            else "A_higher_observed_rate" if rate_a > rate_b
            else "B_higher_observed_rate" if rate_b > rate_a
            else "equal_observed_rate"
        )
        rows.append({
            "dataset_version": "1.0",
            "experiment_key": key,
            "variant_a": {
                "headline": headline_a,
                "assigned_visitors": a["assigned_visitors"],
                "impressions": a["impressions"],
                "recorded_conversion_events": a["conversions"],
                "observed_event_rate": round(rate_a, 6) if rate_a is not None else None,
            },
            "variant_b": {
                "headline": headline_b,
                "assigned_visitors": b["assigned_visitors"],
                "impressions": b["impressions"],
                "recorded_conversion_events": b["conversions"],
                "observed_event_rate": round(rate_b, 6) if rate_b is not None else None,
            },
            "observed_rate_delta_b_minus_a": round(rate_b - rate_a, 6)
            if rate_a is not None and rate_b is not None else None,
            "observed_relative_rate_label": relative_label,
            "eligibility_status": "eligible_for_human_review" if eligible else "excluded_low_sample",
            "eligible_for_human_review": eligible,
            "review_reasons": reasons,
            "provenance": {
                "source": "workspace_experiment_event_ledger",
                "evidence_status": "internal_events_not_provider_attested",
                "visitor_identifiers_included": False,
                "causal_winner_claimed": False,
            },
        })

    eligible_count = sum(row["eligible_for_human_review"] for row in rows)
    return {
        "dataset_version": "1.0",
        "dataset_format": "jsonl",
        "summary": {
            "assignment_records_read": len(assignment_rows),
            "event_records_read": len(event_rows),
            "experiment_keys_seen": len(experiments),
            "paired_experiment_rows": len(rows),
            "eligible_for_human_review": eligible_count,
            "excluded_low_sample": low_sample,
            "excluded_data_quality": len(exclusions),
            "ignored_assignments": ignored_assignments,
            "ignored_event_types": ignored_types,
            "duplicate_event_ids_ignored": duplicates,
            "unmapped_events_ignored": unmapped,
        },
        "thresholds": {
            "min_impressions_per_variant": min_impressions,
            "min_recorded_conversions_per_variant": min_conversions,
        },
        "rows": rows,
        "excluded_experiments": exclusions[:100],
        "excluded_experiments_truncated": len(exclusions) > 100,
        "visitor_identifiers_included": False,
        "provider_attested": False,
        "training_ready": False,
        "training_started": False,
        "model_updated": False,
        "requires_human_review": True,
        "note": (
            "Aggregate candidates are derived from workspace-recorded events. "
            "Events are not provider-attested, observed rates are not causal proof, "
            "and no model training or promotion was performed."
        ),
    }
