from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from backend.tools.affiliate_api import OpenAffiliateClient


@pytest.mark.asyncio
async def test_openaffiliate_client_uses_pinned_public_fetch_boundary(monkeypatch):
    calls: list[tuple[str, dict[str, Any]]] = []

    @asynccontextmanager
    async def reject_private(url: str, **kwargs):
        calls.append((url, kwargs))
        raise ValueError("Private, loopback, link-local, multicast or reserved destinations are blocked")
        yield  # pragma: no cover

    monkeypatch.setattr("backend.tools.affiliate_api.open_public_http_response", reject_private)
    client = OpenAffiliateClient(base_url="https://127.0.0.1/api")

    with pytest.raises(ValueError, match="Private"):
        await client.fetch_programs(q="creator tools", limit=10)

    assert calls == [(
        "https://127.0.0.1/api/programs",
        {
            "method": "GET",
            "params": {"limit": 10, "q": "creator tools"},
            "headers": {"Accept": "application/json", "User-Agent": "AffiliateOS/0.1"},
            "timeout": 10.0,
        },
    )]


@pytest.mark.asyncio
async def test_openaffiliate_client_caps_decoded_response_and_keeps_redirects_off(monkeypatch):
    calls = []

    class Response:
        status_code = 200
        headers = {
            "content-type": "application/json",
            "content-length": "51",
        }

        def raise_for_status(self):
            return None

    @asynccontextmanager
    async def fake_open(url: str, **kwargs):
        calls.append((url, kwargs))
        yield Response()

    async def fake_read(response, *, max_bytes, raw=False):
        assert max_bytes == 5 * 1024 * 1024
        assert raw is False
        return b'{"data":[{"id":"program-1","name":"Example program"}],"count":1}'

    monkeypatch.setattr("backend.tools.affiliate_api.open_public_http_response", fake_open)
    monkeypatch.setattr("backend.tools.affiliate_api.read_limited_response", fake_read)
    client = OpenAffiliateClient(base_url="https://provider.example/api")

    result = await client.fetch_programs(q="creator tools", limit=5)

    assert calls == [(
        "https://provider.example/api/programs",
        {
            "method": "GET",
            "params": {"limit": 5, "q": "creator tools"},
            "headers": {"Accept": "application/json", "User-Agent": "AffiliateOS/0.1"},
            "timeout": 10.0,
        },
    )]
    assert result["data"][0]["name"] == "Example program"



def test_openaffiliate_adapt_preserves_missing_offer_metrics_as_unknown():
    program = OpenAffiliateClient.adapt({"id": "offer-unknown", "name": "Unknown metrics"})

    assert program.cookie_days is None
    assert program.traffic_score is None
    assert program.stars_count is None
    assert program.verified is None


def test_openaffiliate_adapt_parses_only_typed_finite_non_negative_metrics():
    program = OpenAffiliateClient.adapt({
        "id": "offer-valid",
        "name": "Measured values",
        "cookieDays": "30 days",
        "traffic_score": "1,234.5",
        "stars_count": "4.25",
        "verified": True,
    })

    assert program.cookie_days == 30
    assert program.traffic_score == 1234.5
    assert program.stars_count == 4.25
    assert program.verified is True


@pytest.mark.parametrize(
    ("row", "expected_cookie", "expected_traffic", "expected_stars"),
    [
        ({"cookieDays": "-30", "traffic_score": "-12", "stars_count": "-2"}, None, None, None),
        ({"cookieDays": "30.5", "traffic_score": "NaN", "stars_count": "Infinity"}, None, None, None),
        ({"cookieDays": "999999999999", "traffic_score": "1e309", "stars_count": "not-a-number"}, None, None, None),
        ({"cookieDays": True, "traffic_score": True, "stars_count": False}, None, None, None),
        ({"cookieDays": "roughly 30 days", "traffic_score": "Traffic score: 73", "stars_count": None}, None, None, None),
        ({"stars_count": "5.01"}, None, None, None),
        ({"stars_count": 100}, None, None, None),
    ],
)
def test_openaffiliate_adapt_rejects_invalid_metrics_without_inventing_values(
    row: dict[str, Any],
    expected_cookie: int | None,
    expected_traffic: float | None,
    expected_stars: float | None,
):
    program = OpenAffiliateClient.adapt({"id": "offer-invalid", "name": "Invalid values", **row})

    assert program.cookie_days is expected_cookie
    assert program.traffic_score is expected_traffic
    assert program.stars_count is expected_stars


def test_openaffiliate_adapt_preserves_explicit_zero_metrics():
    program = OpenAffiliateClient.adapt({
        "id": "offer-zero",
        "name": "Explicit zeros",
        "cookie_days": 0,
        "traffic_score": 0,
        "stars_count": 0,
    })

    assert program.cookie_days == 0
    assert program.traffic_score == 0.0
    assert program.stars_count == 0.0


def test_openaffiliate_adapt_accepts_five_star_rating_boundary():
    program = OpenAffiliateClient.adapt({
        "id": "offer-five-stars",
        "name": "Maximum supported rating",
        "stars_count": "5.0",
    })

    assert program.stars_count == 5.0
