from __future__ import annotations

import asyncio
import email
import hashlib
import imaplib
import os
import re
import ssl
from decimal import Decimal, InvalidOperation
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any

from bs4 import BeautifulSoup

from backend.config import get_settings
from backend.core.errors import IntegrationNotConfiguredError
from backend.database import SessionLocal
from backend.models import MailCommission

# Grouping separators must be valid; otherwise a malformed value such as 1,2,3
# can be silently misread as a financial amount.
_AMOUNT = r"(?<![\d,.])((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)(?![\d,.])"
MAX_REPORTED_COMMISSION = Decimal("1000000000000.00")
PATTERNS = [
    re.compile(
        rf"commission(?:\s+earned|\s+of|\s+amount)?\s*[:=]?\s*(?:USD\s*)?\$?\s*{_AMOUNT}",
        re.I,
    ),
    re.compile(rf"(?:\$|€|£)\s*{_AMOUNT}\s+(?:commission|earned)", re.I),
]


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _body(msg: Message) -> str:
    parts = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() not in {"text/plain", "text/html"} or part.get_content_disposition() == "attachment":
                continue
            raw = part.get_payload(decode=True) or b""
            parts.append(raw.decode(part.get_content_charset() or "utf-8", errors="replace"))
    else:
        raw = msg.get_payload(decode=True)
        if isinstance(raw, bytes):
            parts.append(raw.decode(msg.get_content_charset() or "utf-8", errors="replace"))
        elif isinstance(raw, str):
            parts.append(raw)
    return "\n".join(
        BeautifulSoup(part, "html.parser").get_text(" ", strip=True) if "<" in part else part
        for part in parts
    )


def parse_commission_message(raw: bytes) -> dict[str, Any] | None:
    """Extract a candidate commission observation; never treat mail as payment proof."""
    msg = email.message_from_bytes(raw)
    sender = parseaddr(msg.get("From", ""))[1].lower()
    subject = _decode(msg.get("Subject"))
    text = _body(msg)
    hit = None
    for pattern in PATTERNS:
        match = pattern.search(text)
        if match:
            hit = match
            break
    if not hit:
        return None

    try:
        amount = Decimal(hit.group(1).replace(",", ""))
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount <= 0 or amount > MAX_REPORTED_COMMISSION:
        return None

    currency = "USD"
    if re.search(r"\bEUR\b|€", text, re.I):
        currency = "EUR"
    elif re.search(r"\bGBP\b|£", text, re.I):
        currency = "GBP"
    network_match = re.search(
        r"(?:on|from|via)\s+([A-Za-z0-9 ._-]{2,100}?)(?:\s+affiliate|\s+program|[.!\n]|$)",
        text,
        re.I,
    )
    try:
        date = parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else None
    except (TypeError, ValueError, OverflowError):
        date = None
    message_id = msg.get("Message-ID") or (
        "fallback-" + hashlib.sha256((sender + subject + text[:200]).encode()).hexdigest()
    )
    return {
        "message_id": message_id.strip("<>"),
        "sender": sender,
        "subject": subject[:500],
        "network": network_match.group(1).strip() if network_match else "unclassified",
        "commission": float(amount),
        "currency": currency,
        "email_date": date,
        "body_excerpt": text[:1500],
    }


async def import_commission_emails(*, mailbox: str = "INBOX", limit: int = 100) -> dict[str, Any]:
    settings = get_settings()
    allowlist = {
        value.strip().lower()
        for value in os.getenv("MAIL_SENDER_ALLOWLIST", "").split(",")
        if value.strip()
    }
    if not (settings.mail_imap_host and settings.mail_imap_user and settings.mail_imap_password):
        raise IntegrationNotConfiguredError("Configure IMAP host/user/password")
    if not allowlist:
        raise IntegrationNotConfiguredError("MAIL_SENDER_ALLOWLIST must list approved sender addresses/domains")

    def fetch_sync():
        with imaplib.IMAP4_SSL(
            settings.mail_imap_host,
            settings.mail_imap_port,
            ssl_context=ssl.create_default_context(),
            timeout=20,
        ) as imap:
            imap.login(settings.mail_imap_user, settings.mail_imap_password)
            code, _ = imap.select(mailbox, readonly=True)
            if code != "OK":
                raise RuntimeError("IMAP mailbox selection failed")
            code, data = imap.search(None, "UNSEEN")
            if code != "OK":
                raise RuntimeError("IMAP search failed")
            message_ids = (data[0].split() if data and data[0] else [])[-max(1, min(limit, 500)):]
            items = []
            for message_id in message_ids:
                code, parts = imap.fetch(message_id, "(RFC822)")
                if code != "OK":
                    continue
                raw = next(
                    (part[1] for part in parts if isinstance(part, tuple) and isinstance(part[1], bytes)),
                    None,
                )
                if not raw:
                    continue
                item = parse_commission_message(raw)
                if item and any(
                    item["sender"] == approved
                    or item["sender"].endswith("@" + approved.lstrip("@"))
                    for approved in allowlist
                ):
                    items.append(item)
            return items

    try:
        items = await asyncio.to_thread(fetch_sync)
    except Exception as exc:
        raise RuntimeError(f"Mailbox read failed: {type(exc).__name__}") from exc

    from sqlalchemy import select

    async with SessionLocal() as db:
        created = 0
        for item in items:
            existing = await db.scalar(
                select(MailCommission.id).where(MailCommission.message_id == item["message_id"])
            )
            if existing:
                continue
            db.add(
                MailCommission(
                    message_id=item["message_id"],
                    network=item["network"],
                    commission=item["commission"],
                    currency=item["currency"],
                    status="pending_verification",
                    email_date=item["email_date"],
                    parsed_subject=item["subject"],
                    evidence_json={key: value for key, value in item.items() if key != "body_excerpt"},
                )
            )
            created += 1
        await db.commit()
    return {
        "messages_matched": len(items),
        "rows_created": created,
        "note": "Parsed mail records remain pending verification and are not confirmed cash receipts.",
    }
