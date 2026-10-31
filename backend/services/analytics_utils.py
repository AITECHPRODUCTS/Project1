from __future__ import annotations

import hashlib
import random
from typing import Any
from urllib.parse import parse_qs, urlparse


def conversion_tracker(url_or_query: str) -> dict[str, Any]:
    parsed = urlparse(
        url_or_query if "://" in url_or_query else "https://local.invalid/?" + url_or_query.lstrip("?")
    )
    params = parse_qs(parsed.query)

    def first(key: str):
        values = params.get(key)
        return values[0][:500] if values else None

    return {
        "utm_source": first("utm_source"),
        "utm_medium": first("utm_medium"),
        "utm_campaign": first("utm_campaign"),
        "utm_term": first("utm_term"),
        "utm_content": first("utm_content"),
        "click_id": first("click_id") or first("subid") or first("aff_sub"),
        "gclid": first("gclid"),
        "fbclid": first("fbclid"),
        "landing_path": parsed.path if parsed.hostname != "local.invalid" else None,
    }


def _posterior_probability_a_better(
    conversions_a: int,
    impressions_a: int,
    conversions_b: int,
    impressions_b: int,
    experiment_key: str,
    *,
    samples: int = 4000,
) -> float | None:
    """Estimate P(rate A > rate B) under independent Beta(1, 1) priors.

    The Monte Carlo seed is derived from the experiment data so the same
    aggregate counts always produce the same estimate. This is a decision aid,
    not a frequentist p-value or proof of causation.
    """
    if impressions_a < 30 or impressions_b < 30 or impressions_a + impressions_b < 100:
        return None
    seed_material = (
        f"{experiment_key}:{conversions_a}:{impressions_a}:"
        f"{conversions_b}:{impressions_b}"
    )
    seed = int.from_bytes(hashlib.sha256(seed_material.encode()).digest()[:8], "big")
    rng = random.Random(seed)
    a_wins = 0
    for _ in range(samples):
        rate_a = rng.betavariate(conversions_a + 1, impressions_a - conversions_a + 1)
        rate_b = rng.betavariate(conversions_b + 1, impressions_b - conversions_b + 1)
        if rate_a > rate_b:
            a_wins += 1
    return a_wins / samples


def ab_test_generator(
    headline_a: str,
    headline_b: str,
    *,
    visitor_id: str,
    experiment_key: str,
    conversions_a: int = 0,
    impressions_a: int = 0,
    conversions_b: int = 0,
    impressions_b: int = 0,
) -> dict[str, Any]:
    if not headline_a.strip() or not headline_b.strip() or headline_a.strip() == headline_b.strip():
        raise ValueError("Two different headlines required")
    if not visitor_id.strip():
        raise ValueError("A stable visitor_id is required for repeatable variant assignment")
    if not experiment_key.strip():
        raise ValueError("A non-empty experiment_key is required")
    for name, conversions, impressions in [
        ("A", conversions_a, impressions_a),
        ("B", conversions_b, impressions_b),
    ]:
        if min(conversions, impressions) < 0 or conversions > impressions:
            raise ValueError(f"Variant {name} requires 0 <= conversions <= impressions")

    # Assignment is always deterministic for a visitor and experiment. Historical
    # metrics inform a recommendation, never the current visitor's assignment.
    digest = hashlib.sha256(f"{experiment_key}:{visitor_id}".encode()).digest()
    variant = "A" if int.from_bytes(digest[:4], "big") % 2 == 0 else "B"
    minimum_sample_met = (
        impressions_a >= 30 and impressions_b >= 30 and impressions_a + impressions_b >= 100
    )
    probability_a_better = _posterior_probability_a_better(
        conversions_a,
        impressions_a,
        conversions_b,
        impressions_b,
        experiment_key,
    )
    if probability_a_better is None:
        recommendation = "collect_more_data"
    elif probability_a_better >= 0.95:
        recommendation = "prefer_a"
    elif probability_a_better <= 0.05:
        recommendation = "prefer_b"
    else:
        recommendation = "continue_test"

    return {
        "experiment_key": experiment_key,
        "variant": variant,
        "headline": headline_a if variant == "A" else headline_b,
        "assignment_method": "stable_hash_split",
        "stats": {
            "A": {
                "impressions": impressions_a,
                "conversions": conversions_a,
                "rate": conversions_a / impressions_a if impressions_a else None,
            },
            "B": {
                "impressions": impressions_b,
                "conversions": conversions_b,
                "rate": conversions_b / impressions_b if impressions_b else None,
            },
        },
        "analysis": {
            "method": "beta_binomial_posterior_monte_carlo",
            "posterior_probability_a_better": probability_a_better,
            "minimum_sample_met": minimum_sample_met,
            "decision_threshold": 0.95,
            "recommendation": recommendation,
            "sample_count": 4000 if minimum_sample_met else 0,
        },
        "warning": (
            "Assignments are stable hash splits. Posterior recommendations are decision support, "
            "not proof of causation, statistical certainty, or guaranteed performance."
        ),
    }
