from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal

import pytest

from backend.adapters.webhook import AggregatorWebhookAdapter


SECRET = "test-webhook-secret-that-is-at-least-32-bytes"
BODY = b'{"event_id":"evt-123","commission":"1.25","revenue":"9.50"}'


def signature(body: bytes = BODY, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_verifies_exact_raw_body_and_prefixed_signature():
    adapter = AggregatorWebhookAdapter("example-network", SECRET)
    assert adapter.verify(BODY, signature())
    assert adapter.verify(BODY, "sha256=" + signature())
    assert not adapter.verify(BODY + b" ", signature())
    assert not adapter.verify(BODY, "")
    assert not adapter.verify(BODY, "sha256=not-hex")
    assert not adapter.verify(BODY, "0" * 63)


def test_webhook_secret_must_be_long_enough():
    with pytest.raises(ValueError, match="32\\+ characters"):
        AggregatorWebhookAdapter("example-network", "short")


def test_conversion_normalizes_ids_and_keeps_money_values_non_negative():
    adapter = AggregatorWebhookAdapter("example-network", SECRET)
    result = adapter.parse_conversion({"transaction_id": "  txn-456 ", "subid": "click-1", "commission": "1.20", "revenue": "10.00", "status": " APPROVED "})
    assert result["external_event_id"] == "txn-456"
    assert result["click_id"] == "click-1"
    assert result["commission"] == Decimal("1.20")
    assert result["revenue"] == Decimal("10.00")
    assert result["status"] == "approved"
    assert result["raw"]["transaction_id"] == "  txn-456 "


@pytest.mark.parametrize("field,value", [("commission", "-0.01"), ("revenue", "-3"), ("commission", "NaN"), ("revenue", "Infinity"), ("commission", "not-a-number")])
def test_conversion_rejects_invalid_or_negative_money(field: str, value: str):
    adapter = AggregatorWebhookAdapter("example-network", SECRET)
    with pytest.raises(ValueError, match="non-negative amount"):
        adapter.parse_conversion({"event_id": "evt-1", field: value})


def test_conversion_requires_bounded_unique_event_id():
    adapter = AggregatorWebhookAdapter("example-network", SECRET)
    with pytest.raises(ValueError, match="event_id"):
        adapter.parse_conversion({"commission": 1})
    with pytest.raises(ValueError, match="255 characters"):
        adapter.parse_conversion({"event_id": "x" * 256})



def test_conversion_preserves_exact_decimal_precision_for_ledger():
    adapter = AggregatorWebhookAdapter("example-network", SECRET)
    result = adapter.parse_conversion(
        {"event_id": "evt-precision", "commission": "0.123456", "revenue": "100.000001"}
    )
    assert result["commission"] == Decimal("0.123456")
    assert result["revenue"] == Decimal("100.000001")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("commission", "0.1234567"),
        ("revenue", "1000000000000"),
    ],
)
def test_conversion_rejects_amounts_not_representable_by_ledger_numeric(field: str, value: str):
    adapter = AggregatorWebhookAdapter("example-network", SECRET)
    with pytest.raises(ValueError):
        adapter.parse_conversion({"event_id": "evt-overflow", field: value})
