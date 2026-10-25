from __future__ import annotations

import pytest

from backend.adapters.openaffiliate import OpenAffiliateAdapter


class FakeClient:
    async def fetch_programs(self, *, q=None, limit=100):
        return {"data": [{"id": "offer-1", "name": "Example"}], "count": 1}


def test_openaffiliate_adapter_normalizes_conversion_fields():
    adapter = OpenAffiliateAdapter(client=FakeClient())
    result = adapter.parse_conversion(
        {
            "transaction_id": " txn-1 ",
            "subid": " click-1 ",
            "commission": "1.25",
            "revenue": "9.50",
            "status": " APPROVED ",
        }
    )

    assert result["network"] == "openaffiliate"
    assert result["external_event_id"] == "txn-1"
    assert result["click_id"] == "click-1"
    assert result["commission"] == 1.25
    assert result["revenue"] == 9.5
    assert result["status"] == "approved"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("commission", "-0.01"),
        ("revenue", "-3"),
        ("commission", "NaN"),
        ("revenue", "Infinity"),
        ("commission", "not-a-number"),
        ("commission", "1000000000001"),
    ],
)
def test_openaffiliate_adapter_rejects_invalid_money(field, value):
    adapter = OpenAffiliateAdapter(client=FakeClient())
    with pytest.raises(ValueError, match=field):
        adapter.parse_conversion({"event_id": "evt-1", field: value})


def test_openaffiliate_adapter_requires_bounded_event_and_click_ids():
    adapter = OpenAffiliateAdapter(client=FakeClient())

    with pytest.raises(ValueError, match="event ID"):
        adapter.parse_conversion({"commission": 1})
    with pytest.raises(ValueError, match="255 characters"):
        adapter.parse_conversion({"event_id": "x" * 256})
    with pytest.raises(ValueError, match="80 characters"):
        adapter.parse_conversion({"event_id": "evt-1", "click_id": "x" * 81})


@pytest.mark.asyncio
async def test_openaffiliate_adapter_fetches_offers_through_client():
    adapter = OpenAffiliateAdapter(client=FakeClient())

    assert await adapter.fetch_offers(query="camera", limit=25) == [
        {"id": "offer-1", "name": "Example"}
    ]
