from __future__ import annotations

from backend.services.commission_mail_importer import parse_commission_message


def make_message(body: str, *, sender: str = "reports@example.test", subject: str = "Commission report") -> bytes:
    return (
        f"From: {sender}\r\n"
        f"Subject: {subject}\r\n"
        "Date: Sat, 24 Oct 2026 12:00:00 +0000\r\n"
        "Message-ID: <report-123@example.test>\r\n"
        "MIME-Version: 1.0\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        f"{body}"
    ).encode("utf-8")


def test_parse_commission_message_extracts_amount_currency_and_identity():
    result = parse_commission_message(
        make_message("Commission earned: USD $1,234.56 from Acme affiliate program")
    )

    assert result is not None
    assert result["message_id"] == "report-123@example.test"
    assert result["sender"] == "reports@example.test"
    assert result["network"] == "Acme"
    assert result["commission"] == 1234.56
    assert result["currency"] == "USD"
    assert result["email_date"].isoformat() == "2026-10-24T12:00:00+00:00"


def test_parse_commission_message_detects_euro_and_gbp_currency():
    euro = parse_commission_message(make_message("Commission amount: 12.50 EUR"))
    gbp = parse_commission_message(make_message("£8.25 earned"))

    assert euro is not None and euro["currency"] == "EUR"
    assert gbp is not None and gbp["currency"] == "GBP"


def test_parse_commission_message_ignores_unrelated_messages():
    assert parse_commission_message(make_message("Your monthly product newsletter is ready")) is None


def test_parse_commission_message_rejects_zero_negative_and_unreasonable_amounts():
    assert parse_commission_message(make_message("Commission: $0.00")) is None
    assert parse_commission_message(make_message("Commission: -$12.00")) is None
    assert parse_commission_message(make_message("Commission: $1000000000001.00")) is None


def test_parse_commission_message_does_not_misread_malformed_grouping():
    assert parse_commission_message(make_message("Commission: $1,2,3.00")) is None


def test_parse_commission_message_uses_stable_fallback_id_when_message_id_missing():
    raw = make_message("Commission earned $10.00").replace(
        b"Message-ID: <report-123@example.test>\r\n", b""
    )

    first = parse_commission_message(raw)
    second = parse_commission_message(raw)

    assert first is not None and second is not None
    assert first["message_id"].startswith("fallback-")
    assert first["message_id"] == second["message_id"]
