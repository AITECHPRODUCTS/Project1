from __future__ import annotations
import asyncio,hashlib,hmac,html,json,re,time
from datetime import datetime,timedelta,timezone
from typing import Any
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import get_settings
from backend.database import SessionLocal
from backend.models import Lead,ScheduledEmail
from backend.tenancy import get_workspace_id, workspace_scope
from backend.services.llm import llm_service
from backend.services.s4_s5_landing import email_drip_sequence
def _unsubscribe_url(lead_id:str,ts:int|None=None)->str:
 s=get_settings();ts=ts or int(time.time());secret=s.tracking_hmac_secret or s.app_session_secret;sig=hmac.new(secret.encode(),f"unsubscribe:{lead_id}:{ts}".encode(),hashlib.sha256).hexdigest();return f"{s.app_public_url.rstrip('/')}/unsubscribe/{lead_id}?ts={ts}&sig={sig}"
def _fallback(day:int,magnet:str,offer:dict[str,Any])->tuple[str,str]:
 name=str(offer.get("name") or "the recommended option");url=str(offer.get("affiliate_url") or offer.get("url") or "")
 texts={0:(f"Your {magnet} is ready",f"Thanks for signing up. Your resource is {magnet}. Start with one small step today.\n\nYou may receive related tips over the next few days. I may earn a commission if you purchase via an affiliate link."),1:("One practical improvement for today","Define the task, the time available and what success looks like. Apply that checklist to the resource you received. I may earn a commission from qualifying affiliate purchases."),2:("Compare the trade-offs before choosing","Check current pricing, limitations, privacy, support, cancellation terms and alternatives. The right choice depends on your actual workflow; no tool is right for everyone."),3:(f"An honest look at {name}",f"Review the latest features, price and terms directly with the provider. Consider limitations and alternatives before buying.\n\n{url}\n\nDisclosure: I may earn a commission if you purchase through this affiliate link."),4:("A simple decision checklist",f"Confirm current terms, test a key feature, compare alternatives and check privacy/cancellation. Do not buy if the product doesn't fit your needs.\n\n{url}\n\nDisclosure: I may earn a commission from a qualifying purchase.")}
 return texts[day]
def _resolve_workspace_id(workspace_id: str | None = None) -> str:
 active_workspace_id = get_workspace_id()
 requested_workspace_id = str(workspace_id).strip() if workspace_id else None
 if requested_workspace_id and active_workspace_id and requested_workspace_id != active_workspace_id:
  raise ValueError("Email workspace does not match the active workspace context")
 resolved_workspace_id = requested_workspace_id or active_workspace_id
 if not resolved_workspace_id:
  raise ValueError("Authorized workspace context required for email delivery operations")
 return resolved_workspace_id


async def capture_lead_and_schedule(
 session: AsyncSession,
 *,
 email_address: str,
 consent: bool,
 lead_magnet: str,
 audience: str,
 offer: dict[str, Any],
 consent_source: str = "website_form",
 workspace_id: str | None = None,
) -> dict[str, Any]:
 owner_workspace_id = _resolve_workspace_id(workspace_id)
 if consent is not True:
  raise ValueError("Explicit email consent is required")
 address = email_address.strip().lower()
 if len(address) > 320 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]{2,}", address):
  raise ValueError("A valid email address is required")

 with workspace_scope(owner_workspace_id):
  now = datetime.now(timezone.utc)
  lead = await session.scalar(
   select(Lead).where(
    Lead.workspace_id == owner_workspace_id,
    Lead.email == address,
   )
  )
  if lead and lead.unsubscribed_at:
   raise ValueError("Address previously unsubscribed; explicit resubscribe confirmation required")
  if lead:
   lead.consent_at = now
   lead.lead_magnet = lead_magnet[:300]
   lead.consent_source = consent_source[:180]
  else:
   lead = Lead(
    workspace_id=owner_workspace_id,
    email=address,
    consent_at=now,
    consent_source=consent_source[:180],
    lead_magnet=lead_magnet[:300],
   )
   session.add(lead)
   await session.flush()

  sequence = email_drip_sequence(
   audience=audience,
   lead_magnet=lead_magnet,
   affiliate_offer=offer,
   duration_days=5,
  )
  prompt = (
   "Write a JSON array of exactly five objects with day 0-4, subject and body_text. "
   "Keep messages accurate, short and useful. Don't invent claims or urgency. "
   "Put clear affiliate disclosure near affiliate links. End with an unsubscribe direction.\n"
   + json.dumps(
    {"audience": audience, "lead_magnet": lead_magnet, "offer": offer, "sequence": sequence},
    ensure_ascii=False,
   )
  )
  generated = await llm_service.complete(
   "You are an ethical lifecycle email writer. Respect consent, disclosures and unsubscribe controls.",
   prompt,
   temperature=.35,
   niche=audience,
  )
  rows: dict[int, dict[str, Any]] = {}
  try:
   parsed = json.loads(generated["text"])
   parsed = parsed.get("emails", []) if isinstance(parsed, dict) else parsed
   if isinstance(parsed, list):
    for item in parsed:
     if (
      isinstance(item, dict)
      and str(item.get("day")) in {"0", "1", "2", "3", "4"}
      and item.get("subject")
      and item.get("body_text")
     ):
      rows[int(item["day"])] = item
  except (json.JSONDecodeError, TypeError, ValueError):
   pass

  created = 0
  for item in sequence:
   day = item["day"]
   existing_email_id = await session.scalar(
    select(ScheduledEmail.id).where(
     ScheduledEmail.workspace_id == owner_workspace_id,
     ScheduledEmail.lead_id == lead.id,
     ScheduledEmail.sequence_day == day,
    )
   )
   if existing_email_id:
    continue
   generated_item = rows.get(day)
   subject = str(generated_item["subject"])[:500] if generated_item else item["subject"]
   body = str(generated_item["body_text"])[:20000] if generated_item else _fallback(day, lead_magnet, offer)[1]
   if day in (3, 4) and "affiliate" not in body.lower():
    body += "\n\nDisclosure: I may earn a commission from qualifying purchases through affiliate links."
   timestamp = int(time.time())
   unsubscribe_url = _unsubscribe_url(lead.id, timestamp)
   body += f"\n\nUnsubscribe: {unsubscribe_url}"
   body_html = (
    "<!doctype html><html><body>"
    + "".join(f"<p>{html.escape(line)}</p>" for line in body.splitlines() if line.strip())
    + f'<p><a href="{html.escape(unsubscribe_url, quote=True)}">Unsubscribe</a></p></body></html>'
   )
   session.add(
    ScheduledEmail(
     workspace_id=owner_workspace_id,
     lead_id=lead.id,
     sequence_day=day,
     subject=subject,
     body_html=body_html,
     body_text=body,
     condition_json={
      "requires_consent": True,
      "skip_if_unsubscribed": True,
      "skip_days_3_4_if_purchased": day >= 3,
      "condition": item["condition"],
     },
     send_at=now + timedelta(days=day),
     status="scheduled",
    )
   )
   created += 1
  await session.commit()
  return {
   "lead_id": lead.id,
   "workspace_id": owner_workspace_id,
   "emails_scheduled": created,
   "sequence_days": [item["day"] for item in sequence],
   "provider": generated["provider"],
   "delivery_configured": bool(get_settings().resend_api_key and get_settings().resend_from_email),
   "note": "5-day sequence queued; actual sending requires provider configuration and scheduled worker.",
  }


async def send_due_emails(
 session: AsyncSession | None = None,
 *,
 limit: int = 50,
 workspace_id: str | None = None,
) -> dict[str, Any]:
 owner_workspace_id = _resolve_workspace_id(workspace_id)
 settings = get_settings()
 with workspace_scope(owner_workspace_id):
  if not (settings.resend_api_key and settings.resend_from_email):
   return {
    "sent": 0,
    "attempted": 0,
    "provider_configured": False,
    "reason": "Configure RESEND_API_KEY and RESEND_FROM_EMAIL",
   }
  owns_session = session is None
  if owns_session:
   session = SessionLocal()
  assert session is not None
  sent = skipped = 0
  now = datetime.now(timezone.utc)
  try:
   statement = select(ScheduledEmail).where(
    ScheduledEmail.workspace_id == owner_workspace_id,
    ScheduledEmail.status.in_(["scheduled", "retry"]),
    ScheduledEmail.send_at <= now,
   )
   messages = list((
    await session.scalars(
     statement.order_by(ScheduledEmail.send_at).limit(max(1, min(limit, 200)))
    )
   ).all())
   async with httpx.AsyncClient(timeout=20) as client:
    for message in messages:
     lead = await session.scalar(
      select(Lead).where(
       Lead.id == message.lead_id,
       Lead.workspace_id == owner_workspace_id,
      )
     )
     if not lead or lead.unsubscribed_at:
      message.status = "suppressed"
      skipped += 1
      continue
     if message.condition_json.get("skip_days_3_4_if_purchased") and lead.purchased_at:
      message.status = "suppressed_purchased"
      skipped += 1
      continue
     message.attempts += 1
     if message.attempts > 4:
      message.status = "failed_permanent"
      skipped += 1
      continue
     unsubscribe_url = _unsubscribe_url(lead.id)
     try:
      response = await client.post(
       "https://api.resend.com/emails",
       json={
        "from": settings.resend_from_email,
        "to": [lead.email],
        "subject": message.subject,
        "html": message.body_html,
        "text": message.body_text,
        "headers": {"List-Unsubscribe": f"<{unsubscribe_url}>"},
       },
       headers={"Authorization": f"Bearer {settings.resend_api_key}"},
      )
      response.raise_for_status()
      message.status = "sent"
      message.provider_message_id = response.json().get("id")
      message.last_error = None
      sent += 1
     except Exception as exc:
      message.status = "retry" if message.attempts < 4 else "failed_permanent"
      message.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
      message.send_at = now + timedelta(minutes=min(2 ** message.attempts * 5, 180))
   await session.commit()
   return {
    "sent": sent,
    "skipped": skipped,
    "attempted": len(messages),
    "provider_configured": True,
    "workspace_id": owner_workspace_id,
   }
  finally:
   if owns_session:
    await session.close()


async def unsubscribe_lead(session:AsyncSession,lead_id:str)->bool:
 lead=await session.get(Lead,lead_id)
 if lead is None:return False
 lead.unsubscribed_at=datetime.now(timezone.utc);await session.commit();return True
