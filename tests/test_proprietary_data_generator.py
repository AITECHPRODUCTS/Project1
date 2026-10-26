from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.services.proprietary_data_generator import build_proprietary_dataset


def assignment(key: str, variant: str, *, headline_a: str = "A headline", headline_b: str = "B headline"):
    return SimpleNamespace(
        id=f"{key}-{variant}",
        experiment_key=key,
        variant=variant,
        headline_a=headline_a,
        headline_b=headline_b,
        visitor_id=f"private-{key}-{variant}",
    )


def event(assignment_id: str, event_id: str, event_type: str):
    return SimpleNamespace(assignment_id=assignment_id, event_id=event_id, event_type=event_type)


def add_events(target, assignment_id: str, prefix: str, *, impressions: int, conversions: int):
    target.extend(event(assignment_id, f"{prefix}-imp-{i}", "impression") for i in range(impressions))
    target.extend(event(assignment_id, f"{prefix}-conv-{i}", "conversion") for i in range(conversions))


def test_generates_paired_aggregate_dataset_without_visitor_identifiers():
    assignments = [assignment("exp-1", "A"), assignment("exp-1", "B")]
    events = []
    add_events(events, "exp-1-A", "a", impressions=120, conversions=8)
    add_events(events, "exp-1-B", "b", impressions=110, conversions=6)

    result = build_proprietary_dataset(assignments, events, min_impressions=100, min_conversions=5)

    assert result["summary"]["paired_experiment_rows"] == 1
    assert result["summary"]["eligible_for_human_review"] == 1
    row = result["rows"][0]
    assert row["eligibility_status"] == "eligible_for_human_review"
    assert row["variant_a"]["observed_event_rate"] == round(8 / 120, 6)
    assert row["variant_b"]["recorded_conversion_events"] == 6
    assert row["provenance"]["visitor_identifiers_included"] is False
    assert "private-exp-1-A" not in repr(result)
    assert "private-exp-1-B" not in repr(result)
    assert result["provider_attested"] is False
    assert result["training_started"] is False
    assert result["model_updated"] is False


def test_low_sample_rows_are_not_review_eligible():
    assignments = [assignment("exp-low", "A"), assignment("exp-low", "B")]
    events = []
    add_events(events, "exp-low-A", "a", impressions=90, conversions=8)
    add_events(events, "exp-low-B", "b", impressions=120, conversions=4)
    result = build_proprietary_dataset(assignments, events, min_impressions=100, min_conversions=5)
    assert result["summary"]["eligible_for_human_review"] == 0
    assert result["summary"]["excluded_low_sample"] == 1
    assert result["rows"][0]["eligible_for_human_review"] is False
    assert "variant_A_below_min_impressions" in result["rows"][0]["review_reasons"]
    assert "variant_B_below_min_conversions" in result["rows"][0]["review_reasons"]


def test_missing_variant_and_changed_headline_snapshots_are_excluded():
    records = [
        assignment("exp-missing", "A"),
        assignment("exp-changed", "A"),
        assignment("exp-changed", "B", headline_a="Changed A", headline_b="Changed B"),
    ]
    result = build_proprietary_dataset(records, [])
    reasons = {item["experiment_key"]: item["reason"] for item in result["excluded_experiments"]}
    assert reasons["exp-missing"] == "both_variants_required"
    assert reasons["exp-changed"] == "inconsistent_headline_snapshot"
    assert result["rows"] == []


def test_duplicate_event_ids_are_counted_once_and_unknown_types_are_ignored():
    records = [assignment("exp-dedupe", "A"), assignment("exp-dedupe", "B")]
    events = [
        event("exp-dedupe-A", "same-event", "impression"),
        event("exp-dedupe-A", "same-event", "impression"),
        event("exp-dedupe-A", "unknown-event", "click"),
        event("exp-dedupe-B", "b-imp", "impression"),
    ]
    result = build_proprietary_dataset(records, events, min_impressions=1, min_conversions=1)
    assert result["summary"]["duplicate_event_ids_ignored"] == 1
    assert result["summary"]["ignored_event_types"] == 1
    assert result["rows"][0]["variant_a"]["impressions"] == 1
    assert result["rows"][0]["eligibility_status"] == "excluded_low_sample"


@pytest.mark.parametrize(
    "field,value",
    [("min_impressions", 0), ("min_conversions", 0), ("min_impressions", True)],
)
def test_sample_thresholds_must_be_positive_integers(field, value):
    with pytest.raises(ValueError):
        build_proprietary_dataset([], [], **{field: value})
