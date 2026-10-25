from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any, Iterable, Mapping


def _network_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _amount_key(value: Any) -> Decimal | None:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not amount.is_finite():
        return None
    return amount.quantize(Decimal("0.01"))


def build_commission_reconciliation(
    mail_evidence: Iterable[Mapping[str, Any]],
    conversions: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Produce review candidates only; never assert that a payout was received.

    A possible match requires the same normalized network name, currency, and
    commission amount. Because email evidence may not contain a provider event
    ID, even a unique match remains unverified and must be reviewed by a human.
    """
    conversion_rows = list(conversions)
    evidence_rows = list(mail_evidence)
    indexed: dict[tuple[str, str, Decimal], list[Mapping[str, Any]]] = {}
    for conversion in conversion_rows:
        amount = _amount_key(conversion.get("commission"))
        network = _network_key(conversion.get("network"))
        currency = str(conversion.get("currency") or "USD").strip().upper()
        status = str(conversion.get("status") or "").strip().casefold()
        if amount is None or amount <= 0 or not network or status in {
            "reversed", "refunded", "chargeback", "clawback", "reversal",
            "commission_reversal",
        }:
            continue
        indexed.setdefault((network, currency, amount), []).append(conversion)

    results = []
    counts = {"possible_match": 0, "ambiguous": 0, "unmatched": 0, "already_reviewed": 0}
    for evidence in evidence_rows:
        evidence_status = str(evidence.get("status") or "pending_verification")
        if evidence_status not in {"pending_verification", "needs_review"}:
            counts["already_reviewed"] += 1
            results.append({
                "evidence_id": evidence.get("id"),
                "network": evidence.get("network"),
                "commission": evidence.get("commission"),
                "currency": str(evidence.get("currency") or "USD").upper(),
                "evidence_status": evidence_status,
                "reconciliation_status": "already_reviewed",
                "candidate_conversion_ids": [],
                "verified": False,
                "payout_confirmed": False,
            })
            continue
        amount = _amount_key(evidence.get("commission"))
        key = (
            _network_key(evidence.get("network")),
            str(evidence.get("currency") or "USD").strip().upper(),
            amount,
        ) if amount is not None else None
        candidates = indexed.get(key, []) if key else []
        state = "unmatched" if not candidates else "possible_match" if len(candidates) == 1 else "ambiguous"
        counts[state] += 1
        results.append({
            "evidence_id": evidence.get("id"),
            "network": evidence.get("network"),
            "commission": evidence.get("commission"),
            "currency": str(evidence.get("currency") or "USD").upper(),
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
            "Amount/network/currency similarity is a review lead, not proof of identity "
            "or payment. No evidence status was changed and no payout was confirmed."
        ),
    }
