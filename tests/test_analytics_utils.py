from __future__ import annotations

import pytest

from backend.services.analytics_utils import ab_test_generator


def test_ab_assignment_is_stable_for_visitor_even_when_aggregate_metrics_change():
    low_data = ab_test_generator(
        "Headline A", "Headline B", visitor_id="visitor-123", experiment_key="experiment-1"
    )
    high_data = ab_test_generator(
        "Headline A", "Headline B", visitor_id="visitor-123", experiment_key="experiment-1",
        conversions_a=60, impressions_a=100, conversions_b=10, impressions_b=100,
    )

    assert low_data["variant"] == high_data["variant"]
    assert low_data["assignment_method"] == "stable_hash_split"
    assert high_data["analysis"]["recommendation"] == "prefer_a"
    assert high_data["analysis"]["posterior_probability_a_better"] >= 0.95


def test_ab_analysis_prefers_b_when_b_has_strongly_better_conversion_rate():
    result = ab_test_generator(
        "Headline A", "Headline B", visitor_id="visitor-456", experiment_key="experiment-2",
        conversions_a=8, impressions_a=100, conversions_b=55, impressions_b=100,
    )

    assert result["analysis"]["recommendation"] == "prefer_b"
    assert result["analysis"]["posterior_probability_a_better"] <= 0.05
    assert result["analysis"]["minimum_sample_met"] is True


def test_ab_analysis_requests_more_data_below_minimum_sample():
    result = ab_test_generator(
        "Headline A", "Headline B", visitor_id="visitor-789", experiment_key="experiment-3",
        conversions_a=4, impressions_a=20, conversions_b=5, impressions_b=20,
    )

    assert result["analysis"]["posterior_probability_a_better"] is None
    assert result["analysis"]["recommendation"] == "collect_more_data"
    assert result["analysis"]["minimum_sample_met"] is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"visitor_id": "", "experiment_key": "exp"},
        {"visitor_id": "visitor", "experiment_key": ""},
        {"conversions_a": 5, "impressions_a": 4},
        {"conversions_b": -1, "impressions_b": 10},
    ],
)
def test_ab_generator_rejects_invalid_identity_or_metrics(kwargs):
    params = {
        "visitor_id": "visitor",
        "experiment_key": "exp",
        "conversions_a": 0,
        "impressions_a": 0,
        "conversions_b": 0,
        "impressions_b": 0,
    }
    params.update(kwargs)
    with pytest.raises(ValueError):
        ab_test_generator("Headline A", "Headline B", **params)


def test_ab_generator_requires_distinct_headlines():
    with pytest.raises(ValueError, match="different headlines"):
        ab_test_generator(
            "Same headline", "Same headline", visitor_id="visitor", experiment_key="exp"
        )
