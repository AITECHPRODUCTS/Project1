from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.adapters.base import AffiliateNetworkAdapter


class AggregatorWebhookAdapter(AffiliateNetworkAdapter):
    """Verify provider webhook signatures and normalize conversion events.

    The caller must pass the exact raw HTTP request bytes to verify() before
    parsing or persisting the event. This adapter does not persist events or
    claim that a provider account is connected.
    """

    def __init__(self, network_name: str, secret: str):
        if len(secret) < 32:
            raise ValueError("Webhook signing secret must have 32+ characters")
        self.network_name = network_name
        self.secret = secret.encode("utf-8")

    def verify(self, raw_body: bytes, signature: str) -> bool:
        """Verify a hex SHA-256 HMAC, accepting common sha256= prefixes."""
        if not isinstance(raw_body, bytes) or not isinstance(signature, str):
            return False
        candidate = signature.strip()
        if candidate.startswith("sha256="):
            candidate = candidate[len("sha256="):]
        if len(candidate) != hashlib.sha256().digest_size * 2:
            return False
        try:
            bytes.fromhex(candidate)
        except ValueError:
            return False
        expected = hmac.new(self.secret, raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, candidate.lower())

    @staticmethod
    def _non_negative_amount(payload: dict[str, Any], field: str) -> float:
        raw = payload.get(field, 0)
        if raw is None or raw == "":
            raw = 0
        try:
            amount = Decimal(str(raw))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(f"{field} must be a valid non-negative amount") from exc
        if not amount.is_finite() or amount < 0:
            raise ValueError(f"{field} must be a valid non-negative amount")
        return float(amount)

    async def fetch_offers(self, *, query: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        # This webhook-only adapter has no offer-discovery API.
        return []

    def parse_conversion(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Conversion payload must be an object")
        raw_event_id = payload.get("event_id") or payload.get("transaction_id")
        event_id = str(raw_event_id or "").strip()
        if not event_id:
            raise ValueError("Unique external event_id required")
        if len(event_id) > 255:
            raise ValueError("External event_id must be 255 characters or fewer")
        status = str(payload.get("status") or "pending").strip().lower() or "pending"
        return {
            "network": self.network_name,
            "external_event_id": event_id,
            "click_id": payload.get("click_id") or payload.get("subid"),
            "commission": self._non_negative_amount(payload, "commission"),
            "revenue": self._non_negative_amount(payload, "revenue"),
            "status": status,
            "raw": payload,
        }
