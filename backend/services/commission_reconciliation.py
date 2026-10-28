from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any, Iterable, Mapping


_MAX_AMOUNT = Decimal("999999999999.999999")
_MAX_SCALE = Decimal("0.000001")


def _network_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _status_key(value: Any, default: str = "") -> str:
    """Normalize provider/operator status spelling without guessing semantics."""
    status = str(value or default).strip().casefold()
    return re.sub(r"[^a-z0-9]+", "_", status).strip("_")


def _currency_key(value: Any) -> str | None:
    """Return an explicit three-letter currency code; never infer USD."""
    currency = str(value or "").strip().upper()
    return currency if re.fullmatch(r"[A-Z]{3}", currency) else None


def _amount_key(value: Any) -> Decimal | None:
    """Parse exact Numeric(18, 6)-representable money without rounding."""
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not amount.is_finite() or amount < 0 or amount > _MAX_AMOUNT:
        return None
    try:
        if amount != amount.quantize(_MAX_SCALE):
            return None
    except InvalidOperation:
        return None
    return amount


def build_commission_reconciliation(
    mail_evidence: Iterable[Mapping[str, Any]],
    conversions: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Produce review candidates only; never assert that a payout was received.

    A possible match requires the same normalized network name, explicit
    currency code, and exact representable commission amount. Amounts are
    never rounded to cents: doing so can match distinct ledger transactions.
    Because email evidence may not contain a provider event ID, even a unique
    match remains unverified and must be reviewed by a human.
    """
    conversion_rows = list(conversions)
    evidence_rows = list(mail_evidence)
    indexed: dict[tuple[str, str, Decimal], list[Mapping[str, Any]]] = {}
    for conversion in conversion_rows:
        amount = _amount_key(conversion.get("commission"))
        network = _network_key(conversion.get("network"))
        currency = _currency_key(conversion.get("currency"))
        status = _status_key(conversion.get("status"))
        if amount is None or amount <= 0 or not network or currency is None or status in {
            "reversed", "refunded", "chargeback", "clawback", "reversal",
            "commission_reversal",
        }:
            continue
        indexed.setdefault((network, currency, amount), []).append(conversion)

    results = []
    counts = {"possible_match": 0, "ambiguous": 0, "unmatched": 0, "already_reviewed": 0}
    for evidence in evidence_rows:
        evidence_status = _status_key(evidence.get("status"), "pending_verification")
        currency = _currency_key(evidence.get("currency"))
        if evidence_status not in {"pending_verification", "needs_review"}:
            counts["already_reviewed"] += 1
            results.append({
                "evidence_id": evidence.get("id"),
                "network": evidence.get("network"),
                "commission": evidence.get("commission"),
                "currency": currency,
                "evidence_status": evidence_status,
                "reconciliation_status": "already_reviewed",
                "candidate_conversion_ids": [],
                "verified": False,
                "payout_confirmed": False,
            })
            continue
        amount = _amount_key(evidence.get("commission"))
        network = _network_key(evidence.get("network"))
        key = (network, currency, amount) if amount is not None and network and currency else None
        candidates = indexed.get(key, []) if key else []
        state = "unmatched" if not candidates else "possible_match" if len(candidates) == 1 else "ambiguous"
        counts[state] += 1
        results.append({
            "evidence_id": evidence.get("id"),
            "network": evidence.get("network"),
            "commission": evidence.get("commission"),
            "currency": currency,
            "evidence_status": evidence_status,
            "reconciliation_status": state,
            "candidate_conversion_ids": [str(item.get("id")) for item in candidates if item.get("id")],
            "verified": False,
            "payout_confirmed": False,
        })

    return {
        "count": len(results),
        "counts": counts,
        "data": results,
        "policy": (
            "Exact amount/network/currency similarity is a review lead, not proof of identity "
            "or payment. No evidence status was changed and no payout was confirmed."
        ),
    }
