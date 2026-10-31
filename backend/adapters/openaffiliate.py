from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from backend.adapters.base import AffiliateNetworkAdapter
from backend.tools.affiliate_api import OpenAffiliateClient


MAX_AMOUNT = Decimal("999999999999.999999")
LEDGER_SCALE = Decimal("0.000001")


def _money(value: Any, field: str) -> Decimal:
    # Keep affiliate amounts compatible with the immutable Numeric(18, 6)
    # commission ledger; a float conversion would lose precision on valid events.
    if value is None:
        value = 0
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError(f"{field} must be a finite non-negative amount")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field} must be a finite non-negative amount") from exc
    if not amount.is_finite() or amount < 0 or amount > MAX_AMOUNT:
        raise ValueError(f"{field} must be a finite non-negative amount within Numeric(18, 6)")
    try:
        normalized = amount.quantize(LEDGER_SCALE)
    except InvalidOperation as exc:
        raise ValueError(f"{field} must fit Numeric(18, 6)") from exc
    if normalized != amount:
        raise ValueError(f"{field} must have no more than 6 decimal places")
    return amount


class OpenAffiliateAdapter(AffiliateNetworkAdapter):
    network_name = "openaffiliate"

    def __init__(self, client: OpenAffiliateClient | None = None):
        self.client = client or OpenAffiliateClient()

    async def fetch_offers(
        self, *, query: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        return (await self.client.fetch_programs(q=query, limit=limit))["data"]

    def parse_conversion(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("OpenAffiliate conversion payload must be an object")
        event_id = payload.get("event_id") or payload.get("transaction_id")
        if event_id is None or not str(event_id).strip():
            raise ValueError("OpenAffiliate conversion payload needs a unique event ID")
        external_event_id = str(event_id).strip()
        if len(external_event_id) > 255:
            raise ValueError("OpenAffiliate event ID must be 255 characters or fewer")

        click_value = payload.get("click_id") or payload.get("subid")
        click_id = str(click_value).strip() if click_value is not None else None
        if click_id == "":
            click_id = None
        if click_id is not None and len(click_id) > 80:
            raise ValueError("OpenAffiliate click ID must be 80 characters or fewer")

        status = str(payload.get("status") or "pending").strip().lower()
        if not status or len(status) > 60:
            raise ValueError("OpenAffiliate conversion status must contain 1-60 characters")

        return {
            "network": self.network_name,
            "external_event_id": external_event_id,
            "commission": _money(payload.get("commission", 0), "commission"),
            "revenue": _money(payload.get("revenue", 0), "revenue"),
            "click_id": click_id,
            "status": status,
            "raw": payload,
        }
