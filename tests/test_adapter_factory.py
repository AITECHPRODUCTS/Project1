from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from backend.adapters.factory import ConfiguredJSONAdapter


@pytest.mark.asyncio
async def test_configured_json_adapter_rejects_private_endpoint_before_network_io():
    adapter = ConfiguredJSONAdapter(
        "test-network",
        "https://127.0.0.1/private",
        "test-token",
    )

    # The real pinned helper rejects loopback while resolving the destination,
    # before it constructs or opens an HTTP client.
    with pytest.raises(ValueError, match="Private"):
        await adapter.fetch_offers(query="tools", limit=10)


@pytest.mark.asyncio
async def test_configured_json_adapter_uses_pinned_helper_and_normalizes_items(monkeypatch):
    endpoint = "https://partner.example/api/offers"
    captured: dict[str, Any] = {}

    async def fake_request_public_json(url: str, **kwargs: Any) -> dict[str, Any]:
        captured.update({"url": url, **kwargs})
        return {"data": [{"id": str(i)} for i in range(5)] + ["not-an-object"]}

    monkeypatch.setattr(
        "backend.adapters.factory.request_public_json",
        fake_request_public_json,
    )
    adapter = ConfiguredJSONAdapter("test-network", endpoint, "test-token")
    result = await adapter.fetch_offers(query="creator tools", limit=-10)

    assert captured == {
        "url": endpoint,
        "method": "GET",
        "params": {"q": "creator tools", "limit": 1},
        "headers": {
            "Authorization": "Bearer test-token",
            "Accept": "application/json",
        },
        "timeout": 20,
        "max_bytes": 2_000_000,
    }
    assert result == [{"id": "0"}]



def test_configured_json_adapter_parses_conversion_with_exact_ledger_precision():
    adapter = ConfiguredJSONAdapter("test-network", "https://partner.example/api", "test-token")
    payload = {
        "event_id": "  evt-123 ",
        "click_id": " click-42 ",
        "commission": "0.123456",
        "revenue": "100.000001",
        "status": " APPROVED ",
    }

    result = adapter.parse_conversion(payload)

    assert result["network"] == "test-network"
    assert result["external_event_id"] == "evt-123"
    assert result["click_id"] == "click-42"
    assert result["commission"] == Decimal("0.123456")
    assert result["revenue"] == Decimal("100.000001")
    assert result["status"] == "approved"
    assert result["raw"] is payload


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("commission", "-0.01"),
        ("revenue", "-3"),
        ("commission", "NaN"),
        ("revenue", "Infinity"),
        ("commission", "not-a-number"),
        ("commission", "0.1234567"),
        ("revenue", "1000000000000"),
        ("commission", True),
    ],
)
def test_configured_json_adapter_rejects_invalid_or_unrepresentable_money(field: str, value: Any):
    adapter = ConfiguredJSONAdapter("test-network", "https://partner.example/api", "test-token")
    with pytest.raises(ValueError):
        adapter.parse_conversion({"event_id": "evt-invalid", field: value})


def test_configured_json_adapter_rejects_non_object_and_unbounded_identifiers():
    adapter = ConfiguredJSONAdapter("test-network", "https://partner.example/api", "test-token")
    with pytest.raises(ValueError, match="object"):
        adapter.parse_conversion([])
    with pytest.raises(ValueError, match="event_id"):
        adapter.parse_conversion({"commission": "1"})
    with pytest.raises(ValueError, match="255"):
        adapter.parse_conversion({"event_id": "x" * 256})
    with pytest.raises(ValueError, match="80"):
        adapter.parse_conversion({"event_id": "evt-id", "click_id": "x" * 81})


def test_configured_json_adapter_defaults_missing_amounts_and_status_safely():
    adapter = ConfiguredJSONAdapter("test-network", "https://partner.example/api", "test-token")
    result = adapter.parse_conversion({"transaction_id": 123})

    assert result["external_event_id"] == "123"
    assert result["click_id"] is None
    assert result["commission"] == Decimal("0")
    assert result["revenue"] == Decimal("0")
    assert result["status"] == "pending"
