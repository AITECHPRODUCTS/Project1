from __future__ import annotations

from backend.services.commission_reconciliation import build_commission_reconciliation


def test_reconciliation_reports_unique_candidate_without_confirming_payment():
    report = build_commission_reconciliation(
        [{"id": "mail-1", "network": "Acme Network", "commission": 12.5, "currency": "USD"}],
        [{"id": "conv-1", "network": "acme-network", "commission": 12.50, "currency": "usd", "status": "approved"}],
    )

    item = report["data"][0]
    assert item["reconciliation_status"] == "possible_match"
    assert item["candidate_conversion_ids"] == ["conv-1"]
    assert item["verified"] is False
    assert item["payout_confirmed"] is False
    assert report["counts"]["possible_match"] == 1


def test_reconciliation_marks_multiple_equal_candidates_ambiguous():
    report = build_commission_reconciliation(
        [{"id": "mail-1", "network": "acme", "commission": "12.50", "currency": "USD"}],
        [
            {"id": "conv-1", "network": "acme", "commission": 12.5, "currency": "USD", "status": "approved"},
            {"id": "conv-2", "network": "acme", "commission": 12.5, "currency": "USD", "status": "pending"},
        ],
    )

    assert report["data"][0]["reconciliation_status"] == "ambiguous"
    assert report["data"][0]["candidate_conversion_ids"] == ["conv-1", "conv-2"]


def test_reconciliation_requires_network_currency_and_amount_to_match():
    report = build_commission_reconciliation(
        [{"id": "mail-1", "network": "acme", "commission": "12.50", "currency": "EUR"}],
        [
            {"id": "wrong-network", "network": "other", "commission": 12.5, "currency": "EUR", "status": "approved"},
            {"id": "wrong-currency", "network": "acme", "commission": 12.5, "currency": "USD", "status": "approved"},
            {"id": "wrong-amount", "network": "acme", "commission": 12.51, "currency": "EUR", "status": "approved"},
        ],
    )

    assert report["data"][0]["reconciliation_status"] == "unmatched"
    assert report["data"][0]["candidate_conversion_ids"] == []


def test_reconciliation_excludes_reversed_conversions_and_already_reviewed_evidence():
    report = build_commission_reconciliation(
        [
            {"id": "mail-1", "network": "acme", "commission": 12.5, "currency": "USD", "status": "pending_verification"},
            {"id": "mail-2", "network": "acme", "commission": 12.5, "currency": "USD", "status": "confirmed_by_operator"},
        ],
        [{"id": "conv-1", "network": "acme", "commission": 12.5, "currency": "USD", "status": "reversed"}],
    )

    assert report["data"][0]["reconciliation_status"] == "unmatched"
    assert report["data"][1]["reconciliation_status"] == "already_reviewed"
    assert report["data"][1]["payout_confirmed"] is False
    assert report["counts"]["already_reviewed"] == 1
