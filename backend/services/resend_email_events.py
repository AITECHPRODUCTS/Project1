from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditLog, EmailConsentConfirmation, EmailDeliveryEvent, Lead, LeadConsentEvent, ScheduledEmail
from backend.services.consent_ledger import EMAIL_MARKETING_CONSENT_PURPOSE, EMAIL_MARKETING_CONSENT_VERSION
from backend.tenancy import workspace_scope


SUPPORTED_RESEND_EMAIL_EVENTS = {
    "email.delivered", "email.delivery_delayed", "email.bounced",
    "email.complained", "email.failed", "email.suppressed",
}
_EVENT_ID = re.compile(r"[A-Za-z0-9._:-]{8,255}")
_MESSAGE_ID = re.compile(r"[A-Za-z0-9._:-]{1,255}")
_HARD_BOUNCE_TYPES = {"permanent", "hard", "hard_bounce", "permanent_bounce"}
_TERMINAL_STATUSES = {
    "bounced", "complained", "provider_suppressed", "suppressed",
    "delivery_failed", "failed_permanent",
}


class UnmatchedResendMessageError(ValueError):
    """Resend callback arrived before the provider message ID was committed locally."""


class AmbiguousResendMessageError(ValueError):
    """Provider message ID maps to more than one internal delivery."""


class ConflictingResendEventError(ValueError):
    """Provider event ID was reused with a different signed payload."""


def _secret_bytes(secret: str) -> bytes | None:
    if not isinstance(secret, str) or not secret.startswith("whsec_"):
        return None
    encoded = secret.removeprefix("whsec_").strip()
    if not encoded or len(encoded) > 512:
        return None
    try:
        key = base64.b64decode(encoded + ("=" * ((4 - len(encoded) % 4) % 4)), validate=True)
    except (binascii.Error, ValueError):
        return None
    return key if len(key) >= 32 else None


def is_resend_webhook_secret_configured(secret: str) -> bool:
    return _secret_bytes(secret) is not None


def verify_resend_webhook_signature(
    raw_body: bytes, *, secret: str, svix_id: str, svix_timestamp: str,
    svix_signature: str, now: int | None = None, tolerance_seconds: int = 300,
) -> bool:
    """Verify the exact raw request bytes with the signed Svix headers."""
    key = _secret_bytes(secret)
    if key is None or not isinstance(raw_body, bytes):
        return False
    if not isinstance(svix_id, str) or not _EVENT_ID.fullmatch(svix_id):
        return False
    if not isinstance(svix_timestamp, str) or not svix_timestamp.isdigit() or len(svix_timestamp) > 12:
        return False
    if not isinstance(svix_signature, str) or len(svix_signature) > 4096:
        return False
    timestamp = int(svix_timestamp)
    current = int(datetime.now(timezone.utc).timestamp()) if now is None else int(now)
    if tolerance_seconds < 0 or abs(current - timestamp) > tolerance_seconds:
        return False
    signed = svix_id.encode() + b"." + svix_timestamp.encode("ascii") + b"." + raw_body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode("ascii")
    return any(
        sep and version == "v1" and hmac.compare_digest(expected, signature)
        for version, sep, signature in (item.partition(",") for item in svix_signature.split())
    )


def _event_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _recipient(data: dict[str, Any]) -> str:
    to = data.get("to")
    if not isinstance(to, list) or len(to) != 1 or not isinstance(to[0], str):
        raise ValueError("Resend email event must identify exactly one recipient")
    address = parseaddr(to[0])[1].strip().lower()
    if len(address) > 320 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]{2,}", address):
        raise ValueError("Resend email event has an invalid recipient address")
    return address


def _hard_bounce(data: dict[str, Any]) -> bool:
    bounce = data.get("bounce")
    if not isinstance(bounce, dict):
        return True
    kind = str(bounce.get("type") or "").strip().lower()
    return not kind or kind in _HARD_BOUNCE_TYPES


def _suppression_reason(event_type: str, data: dict[str, Any]) -> str | None:
    if event_type == "email.complained":
        return "spam_complaint"
    if event_type == "email.bounced" and _hard_bounce(data):
        return "hard_bounce"
    if event_type == "email.suppressed":
        return "provider_suppressed"
    return None


def _reason_rank(reason: str | None) -> int:
    return {"spam_complaint": 3, "hard_bounce": 2, "provider_suppressed": 1}.get(reason or "", 0)


def _safe_metadata(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    # Persist no raw payload, recipient address, subject, headers, or message body.
    result: dict[str, Any] = {"recipient_count": 1}
    bounce = data.get("bounce")
    if event_type == "email.bounced" and isinstance(bounce, dict):
        kind = str(bounce.get("type") or "")[:40]
        subtype = str(bounce.get("subType") or bounce.get("subtype") or "")[:80]
        if kind:
            result["bounce_type"] = kind
        if subtype:
            result["bounce_subtype"] = subtype
    return result


async def process_resend_email_event(
    session: AsyncSession, *, provider_event_id: str, payload: dict[str, Any], payload_sha256: str,
) -> dict[str, Any]:
    if not isinstance(provider_event_id, str) or not _EVENT_ID.fullmatch(provider_event_id):
        raise ValueError("Resend event ID is missing or invalid")
    if not isinstance(payload_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", payload_sha256):
        raise ValueError("Resend payload checksum is invalid")
    if not isinstance(payload, dict):
        raise ValueError("Resend event must be a JSON object")
    kind = str(payload.get("type") or "").strip().lower()
    if kind not in SUPPORTED_RESEND_EMAIL_EVENTS:
        return {"status": "ignored_event_type"}
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Resend email event data must be a JSON object")
    message_id = str(data.get("email_id") or "").strip()
    if not _MESSAGE_ID.fullmatch(message_id):
        raise ValueError("Resend message ID is missing or invalid")
    recipient = _recipient(data)
    outcome = {
        "email.delivered": "delivered", "email.delivery_delayed": "delivery_delayed",
        "email.bounced": "bounced", "email.complained": "complained",
        "email.failed": "delivery_failed", "email.suppressed": "provider_suppressed",
    }[kind]

    with workspace_scope(None):
        prior = await session.scalar(select(EmailDeliveryEvent).where(
            EmailDeliveryEvent.provider_event_id == provider_event_id,
        ))
        if prior is not None:
            if prior.payload_sha256 != payload_sha256:
                raise ConflictingResendEventError("Resend event ID was reused with a different payload")
            return {"status": "duplicate_ignored", "outcome": prior.outcome}
        scheduled_matches = list((await session.scalars(select(ScheduledEmail).where(
            ScheduledEmail.provider_message_id == message_id,
        ))).all())
        confirmation_matches = list((await session.scalars(select(EmailConsentConfirmation).where(
            EmailConsentConfirmation.provider_message_id == message_id,
        ))).all())

    if not scheduled_matches and not confirmation_matches:
        raise UnmatchedResendMessageError("Resend message is not yet correlated; provider retry is required")
    if len(scheduled_matches) + len(confirmation_matches) != 1:
        raise AmbiguousResendMessageError("Resend message ID maps to multiple internal deliveries")
    scheduled_id = str(scheduled_matches[0].id) if scheduled_matches else None
    confirmation_id = str(confirmation_matches[0].id) if confirmation_matches else None
    workspace_id = str((scheduled_matches[0] if scheduled_matches else confirmation_matches[0]).workspace_id or "")
    if not workspace_id:
        raise UnmatchedResendMessageError("Matched provider message has no workspace")

    with workspace_scope(workspace_id):
        scheduled = await session.scalar(select(ScheduledEmail).where(
            ScheduledEmail.id == scheduled_id, ScheduledEmail.workspace_id == workspace_id,
        )) if scheduled_id else None
        confirmation = await session.scalar(select(EmailConsentConfirmation).where(
            EmailConsentConfirmation.id == confirmation_id,
            EmailConsentConfirmation.workspace_id == workspace_id,
        )) if confirmation_id else None
        if (scheduled is None) == (confirmation is None):
            raise UnmatchedResendMessageError("Could not reload the provider message in its workspace")
        internal_message = scheduled or confirmation
        lead = await session.scalar(select(Lead).where(
            Lead.id == internal_message.lead_id, Lead.workspace_id == workspace_id,
        ))
        if lead is None:
            raise UnmatchedResendMessageError("Correlated lead no longer exists in this workspace")
        if str(lead.email or "").strip().lower() != recipient:
            raise ValueError("Resend recipient does not match the correlated lead")

        event = EmailDeliveryEvent(
            workspace_id=workspace_id, provider="resend",
            provider_event_id=provider_event_id, provider_message_id=message_id,
            scheduled_email_id=scheduled_id, consent_confirmation_id=confirmation_id,
            lead_id=lead.id, event_type=kind, outcome=outcome,
            event_created_at=_event_time(payload.get("created_at") or data.get("created_at")),
            payload_sha256=payload_sha256, metadata_json=_safe_metadata(kind, data),
        )
        session.add(event)
        now = datetime.now(timezone.utc)
        if scheduled is not None:
            current = str(scheduled.status or "")
            if kind == "email.delivered" and current not in _TERMINAL_STATUSES:
                scheduled.status, scheduled.last_error, scheduled.claimed_at = "delivered", None, None
            elif kind == "email.delivery_delayed" and current in {"sent", "delivery_delayed"}:
                scheduled.status, scheduled.last_error, scheduled.claimed_at = "delivery_delayed", "Provider reports delivery is delayed.", None
            elif kind == "email.failed" and current not in (_TERMINAL_STATUSES | {"delivered"}):
                scheduled.status, scheduled.last_error, scheduled.claimed_at = "delivery_failed", "Provider reports delivery failed.", None
            elif kind == "email.bounced" and current not in {"complained", "provider_suppressed"}:
                scheduled.status, scheduled.last_error, scheduled.claimed_at = "bounced", "Provider reports a bounced email.", None
            elif kind == "email.complained":
                scheduled.status, scheduled.last_error, scheduled.claimed_at = "complained", "Provider reports an email complaint.", None
            elif kind == "email.suppressed" and current != "complained":
                scheduled.status, scheduled.last_error, scheduled.claimed_at = "provider_suppressed", "Provider suppressed delivery.", None

        # Never invalidate an already-confirmed token on a late callback.
        if confirmation is not None and kind in {
            "email.bounced", "email.complained", "email.failed", "email.suppressed",
        } and confirmation.status in {"pending_delivery", "sent", "delivery_failed"}:
            confirmation.status = {
                "email.bounced": "bounced", "email.complained": "complained",
                "email.failed": "delivery_failed", "email.suppressed": "provider_suppressed",
            }[kind]
            confirmation.last_error = "Provider delivery outcome: " + outcome

        reason = _suppression_reason(kind, data)
        if reason:
            previous_reason = str(lead.email_suppression_reason or "")
            if _reason_rank(reason) > _reason_rank(previous_reason):
                lead.email_suppression_reason = reason
            if lead.email_suppressed_at is None:
                lead.email_suppressed_at = now
            if kind == "email.complained":
                was_unsubscribed = lead.unsubscribed_at is not None
                if not was_unsubscribed:
                    lead.unsubscribed_at = now
                if not was_unsubscribed or previous_reason != "spam_complaint":
                    session.add(LeadConsentEvent(
                        workspace_id=workspace_id, lead_id=lead.id,
                        event_type="unsubscribed", purpose=EMAIL_MARKETING_CONSENT_PURPOSE,
                        consent_text=None, policy_version=EMAIL_MARKETING_CONSENT_VERSION,
                        source="resend_complaint_webhook", channel="email",
                        metadata_json={"provider_event_id": provider_event_id, "provider": "resend"},
                        observed_at=now,
                    ))
            await session.execute(update(ScheduledEmail).where(
                ScheduledEmail.workspace_id == workspace_id,
                ScheduledEmail.lead_id == lead.id,
                ScheduledEmail.status.in_(["scheduled", "retry", "sending", "delivery_delayed"]),
            ).values(
                status="suppressed", claimed_at=None,
                last_error="Provider delivery suppression is active; no message was sent.",
            ).execution_options(synchronize_session=False))
            await session.execute(update(EmailConsentConfirmation).where(
                EmailConsentConfirmation.workspace_id == workspace_id,
                EmailConsentConfirmation.lead_id == lead.id,
                EmailConsentConfirmation.status.in_(["pending_delivery", "sent", "delivery_failed"]),
            ).values(status="cancelled", superseded_at=now, last_error="Provider delivery suppression is active.")
             .execution_options(synchronize_session=False))
            session.add(AuditLog(
                workspace_id=workspace_id, actor="system", action="email_delivery.provider_suppression",
                resource_type="lead", resource_id=lead.id, outcome=reason,
                details_json={
                    "provider": "resend", "provider_event_id": provider_event_id,
                    "provider_message_id": message_id, "suppression_reason": reason,
                    "provider_called": False,
                },
            ))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            with workspace_scope(None):
                duplicate = await session.scalar(select(EmailDeliveryEvent).where(
                    EmailDeliveryEvent.provider_event_id == provider_event_id,
                ))
            if duplicate is not None:
                if duplicate.payload_sha256 != payload_sha256:
                    raise ConflictingResendEventError("Resend event ID was reused with a different payload")
                return {"status": "duplicate_ignored", "outcome": duplicate.outcome}
            raise

    return {"status": "processed", "outcome": outcome, "event_type": kind, "suppression_applied": reason is not None}
