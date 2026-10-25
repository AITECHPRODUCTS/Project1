from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import app


def test_ab_test_assignment_persists_and_uses_idempotent_event_counts():
    experiment_key = f"ci-experiment-{uuid4()}"
    visitor_id = f"visitor-{uuid4()}"
    payload = {
        "experiment_key": experiment_key,
        "visitor_id": visitor_id,
        "headline_a": "A clear value proposition",
        "headline_b": "A proof-led value proposition",
    }

    with TestClient(app) as client:
        first = client.post("/api/analytics/ab-test", json=payload)
        assert first.status_code == 200, first.text
        assigned = first.json()
        assert assigned["assignment_id"]
        assert assigned["counts_source"] == "persisted_experiment_events"
        assert assigned["analysis"]["recommendation"] == "collect_more_data"

        repeated = client.post("/api/analytics/ab-test", json=payload)
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["assignment_id"] == assigned["assignment_id"]
        assert repeated.json()["variant"] == assigned["variant"]

        changed_headline = {**payload, "headline_a": "A different headline"}
        conflict = client.post("/api/analytics/ab-test", json=changed_headline)
        assert conflict.status_code == 409

        impression_event = {
            "experiment_key": experiment_key,
            "visitor_id": visitor_id,
            "event_id": f"event-{uuid4()}",
            "event_type": "impression",
        }
        first_event = client.post("/api/analytics/ab-test/event", json=impression_event)
        assert first_event.status_code == 201, first_event.text
        assert first_event.json()["duplicate"] is False
        duplicate_event = client.post("/api/analytics/ab-test/event", json=impression_event)
        assert duplicate_event.status_code == 200, duplicate_event.text
        assert duplicate_event.json()["duplicate"] is True

        conversion_event = {
            **impression_event,
            "event_id": f"event-{uuid4()}",
            "event_type": "conversion",
        }
        conversion_response = client.post("/api/analytics/ab-test/event", json=conversion_event)
        assert conversion_response.status_code == 201, conversion_response.text

        updated = client.post("/api/analytics/ab-test", json=payload)
        assert updated.status_code == 200, updated.text
        stats = updated.json()["stats"]
        assert stats["A"]["impressions"] + stats["B"]["impressions"] == 1
        assert stats["A"]["conversions"] + stats["B"]["conversions"] == 1


def test_ab_test_assignment_requires_visitor_and_experiment_keys():
    with TestClient(app) as client:
        response = client.post(
            "/api/analytics/ab-test",
            json={
                "experiment_key": " ",
                "visitor_id": " ",
                "headline_a": "A",
                "headline_b": "B",
            },
        )
    assert response.status_code == 422


def test_ab_test_event_requires_an_existing_assignment():
    with TestClient(app) as client:
        response = client.post(
            "/api/analytics/ab-test/event",
            json={
                "experiment_key": f"missing-{uuid4()}",
                "visitor_id": f"visitor-{uuid4()}",
                "event_id": f"event-{uuid4()}",
                "event_type": "impression",
            },
        )
    assert response.status_code == 404
