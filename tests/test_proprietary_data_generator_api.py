from __future__ import annotations

from fastapi.testclient import TestClient

from backend import main


def test_proprietary_dataset_endpoint_persists_review_required_snapshot(monkeypatch):
    def fake_builder(assignments, events, *, min_impressions, min_conversions):
        assert min_impressions == 100
        assert min_conversions == 5
        return {
            "dataset_version": "1.0",
            "dataset_format": "jsonl",
            "summary": {
                "assignment_records_read": len(assignments),
                "event_records_read": len(events),
                "paired_experiment_rows": 1,
                "eligible_for_human_review": 1,
                "excluded_low_sample": 0,
                "excluded_data_quality": 0,
            },
            "thresholds": {
                "min_impressions_per_variant": min_impressions,
                "min_recorded_conversions_per_variant": min_conversions,
            },
            "rows": [{
                "experiment_key": "api-test",
                "eligible_for_human_review": True,
                "provenance": {"visitor_identifiers_included": False},
            }],
            "excluded_experiments": [],
            "visitor_identifiers_included": False,
            "provider_attested": False,
            "training_ready": False,
            "training_started": False,
            "model_updated": False,
            "requires_human_review": True,
            "note": "Review required; no training executed.",
        }

    monkeypatch.setattr(main, "build_proprietary_dataset_service", fake_builder)
    with TestClient(main.app) as client:
        response = client.post("/api/learning/proprietary-dataset", json={})

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["asset_id"]
    assert payload["asset_status"] == "review_required"
    assert payload["eligible_rows_persisted"] == 1
    assert payload["publishing_started"] is False
    assert payload["training_started"] is False
    assert payload["model_updated"] is False
    assert payload["provider_attested"] is False
