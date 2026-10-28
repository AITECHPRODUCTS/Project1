from __future__ import annotations
import asyncio,hashlib,hmac,html,json,re,time
from datetime import datetime,timedelta,timezone
from typing import Any
from backend.services.url_safety import request_public_json
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import get_settings
from backend.database import SessionLocal
from backend.models import AuditLog,ContentAsset,Lead,ScheduledEmail
from backend.tenancy import get_workspace_id, workspace_scope
from backend.services.llm import llm_service
from backend.services.s4_s5_landing import email_drip_sequence
from backend.services.email_automation_builder import build_email_automation, resolve_next_email_step
from backend.services.jurisdiction_compliance import find_current_assessment
from backend.services.utm_attribution import merge_lead_attribution_metadata, normalize_utm_attribution
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
 resubscribe_confirmed: bool = False,
 email_automation_id: str | None = None,
 workspace_id: str | None = None,
 utm_attribution: dict[str, Any] | None = None,
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
  was_resubscribed = bool(lead and lead.unsubscribed_at)
  if was_resubscribed and resubscribe_confirmed is not True:
   raise ValueError("Address previously unsubscribed; explicit resubscribe confirmation required")
  if was_resubscribed:
   previous_unsubscribed_at = lead.unsubscribed_at
   lead.unsubscribed_at = None
   session.add(AuditLog(
    workspace_id=owner_workspace_id,
    actor="recipient",
    action="email.consent.resubscribed",
    resource_type="lead",
    resource_id=lead.id,
    outcome="confirmed",
    details_json={
     "source": consent_source[:180],
     "explicit_confirmation": True,
     "fresh_consent_at": now.isoformat(),
     "prior_unsubscribed_at": previous_unsubscribed_at.isoformat() if previous_unsubscribed_at else None,
     "pending_email_delivery_suppression_lifted": True,
    },
   ))
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

  if normalize_utm_attribution(utm_attribution):
   lead.metadata_json = merge_lead_attribution_metadata(
    lead.metadata_json, utm_attribution, observed_at=now
   )

  if email_automation_id:
   automation_id = str(email_automation_id).strip()
   asset = await session.scalar(select(ContentAsset).where(
    ContentAsset.id == automation_id,
    ContentAsset.workspace_id == owner_workspace_id,
    ContentAsset.asset_type == "email_automation",
   ))
   if asset is None or asset.status != "approved":
    raise ValueError("Select an approved email automation in the active workspace")
   try:
    graph = json.loads(asset.body)
    built = build_email_automation(graph)
   except (json.JSONDecodeError, ValueError) as exc:
    raise ValueError("The selected email automation graph is invalid; create and review a new version") from exc
   metadata = dict(asset.metadata_json or {})
   if built["sha256"] != metadata.get("graph_sha256"):
    raise ValueError("The selected email automation checksum does not match its reviewed version")
   targets = list(built["graph"].get("target_jurisdictions") or [])
   if not targets:
    raise ValueError("The approved email automation must declare at least one target jurisdiction")
   existing_messages = list((await session.scalars(select(ScheduledEmail).where(
    ScheduledEmail.workspace_id == owner_workspace_id,
    ScheduledEmail.lead_id == lead.id,
   ))).all())
   matching_messages = [
    item for item in existing_messages
    if (item.condition_json or {}).get("automation_id") == automation_id
   ]
   if matching_messages and not was_resubscribed:
    # Idempotent repeated form submissions must not restart an already-entered path.
    await session.commit()
    return {
     "lead_id": lead.id, "workspace_id": owner_workspace_id,
     "emails_scheduled": 0, "sequence_days": [],
     "automation_id": automation_id, "provider": "automation_graph",
     "delivery_configured": bool(get_settings().resend_api_key and get_settings().resend_from_email),
     "note": "This lead already has messages for the selected automation; no duplicate path was scheduled.",
    }
   # Explicit selection of a reviewed plan supersedes pending legacy sequence messages for this lead.
   for pending in existing_messages:
    if pending.status in {"scheduled", "retry"}:
     pending.status = "suppressed"
     pending.claimed_at = None
     pending.last_error = "Superseded by explicitly selected approved email automation."
   resolved = resolve_next_email_step(
    built["graph"], purchased=lead.purchased_at is not None, engaged=bool(lead.engaged)
   )
   max_sequence_day = max((int(item.sequence_day) for item in existing_messages), default=-1)
   sequence_day = max_sequence_day + 1
   now = datetime.now(timezone.utc)
   if resolved is None:
    session.add(AuditLog(
     workspace_id=owner_workspace_id, actor="system",
     action="email_automation.entry_stopped", resource_type="content_asset",
     resource_id=asset.id, outcome="no_email_step",
     details_json={"lead_id": lead.id, "graph_sha256": built["sha256"], "side_effects_performed": False},
    ))
    await session.commit()
    return {
     "lead_id": lead.id, "workspace_id": owner_workspace_id,
     "emails_scheduled": 0, "sequence_days": [],
     "automation_id": automation_id, "provider": "automation_graph",
     "delivery_configured": bool(get_settings().resend_api_key and get_settings().resend_from_email),
     "note": "The reviewed branch graph reaches a stop node before any email step.",
    }
   step = resolved["step"]
   body_text = str(step["body_text"]).strip()
   if step.get("has_affiliate_links") and step.get("affiliate_disclosure") and step["affiliate_disclosure"] not in body_text:
    body_text += "\n\n" + str(step["affiliate_disclosure"]).strip()
   unsubscribe_url = _unsubscribe_url(lead.id, int(time.time()))
   body_text += f"\n\nUnsubscribe: {unsubscribe_url}"
   body_html = (
    "<!doctype html><html><body>"
    + "".join(f"<p>{html.escape(line)}</p>" for line in body_text.splitlines() if line.strip())
    + f'<p><a href="{html.escape(unsubscribe_url, quote=True)}">Unsubscribe</a></p></body></html>'
   )
   session.add(ScheduledEmail(
    workspace_id=owner_workspace_id,
    lead_id=lead.id,
    sequence_day=sequence_day,
    subject=str(step["subject"])[:500],
    body_html=body_html,
    body_text=body_text,
    condition_json={
     "requires_consent": True,
     "skip_if_unsubscribed": True,
     "automation_id": automation_id,
     "automation_step_id": step["id"],
     "automation_graph_sha256": built["sha256"],
     "automation_branch_path": resolved["branch_path"],
     "automation_target_jurisdictions": targets,
    },
    send_at=now + timedelta(days=int(step.get("delay_days", 0))),
    status="scheduled",
   ))
   session.add(AuditLog(
    workspace_id=owner_workspace_id, actor="system",
    action="email_automation.entered", resource_type="content_asset",
    resource_id=asset.id, outcome="first_step_scheduled",
    details_json={
     "lead_id": lead.id, "step_id": step["id"], "sequence_day": sequence_day,
     "graph_sha256": built["sha256"], "branch_path": resolved["branch_path"],
     "target_jurisdictions": targets, "provider_send_deferred_to_worker": True,
    },
   ))
   await session.commit()
   return {
    "lead_id": lead.id, "workspace_id": owner_workspace_id,
    "emails_scheduled": 1, "sequence_days": [sequence_day],
    "automation_id": automation_id, "provider": "automation_graph",
    "delivery_configured": bool(get_settings().resend_api_key and get_settings().resend_from_email),
    "note": "One first-step email queued. The worker rechecks current email-marketing compliance and recipient suppression before sending, then evaluates the next branch after a successful delivery.",
   }

  existing_messages = list((await session.scalars(select(ScheduledEmail).where(
   ScheduledEmail.workspace_id == owner_workspace_id,
   ScheduledEmail.lead_id == lead.id,
  ))).all())
  sequence_offset = (
   max((int(item.sequence_day) for item in existing_messages), default=-1) + 1
   if was_resubscribed else 0
  )
  if was_resubscribed:
   for pending in existing_messages:
    if pending.status in {"scheduled", "retry"}:
     pending.status = "suppressed"
     pending.claimed_at = None
     pending.last_error = "Superseded by explicit recipient re-consent."

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
   sequence_day = sequence_offset + day
   existing_email_id = await session.scalar(
    select(ScheduledEmail.id).where(
     ScheduledEmail.workspace_id == owner_workspace_id,
     ScheduledEmail.lead_id == lead.id,
     ScheduledEmail.sequence_day == sequence_day,
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
     sequence_day=sequence_day,
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
   "sequence_days": [sequence_offset + item["day"] for item in sequence],
   "provider": generated["provider"],
   "delivery_configured": bool(get_settings().resend_api_key and get_settings().resend_from_email),
   "note": "5-day sequence queued; actual sending requires provider configuration and scheduled worker.",
  }


async def _load_approved_automation_graph(
 session: AsyncSession,
 *,
 workspace_id: str,
 automation_id: str,
 expected_sha256: str | None = None,
) -> tuple[ContentAsset, dict[str, Any], str]:
 with workspace_scope(workspace_id):
  asset = await session.scalar(select(ContentAsset).where(
   ContentAsset.id == automation_id,
   ContentAsset.workspace_id == workspace_id,
   ContentAsset.asset_type == "email_automation",
  ))
 if asset is None or asset.status != "approved":
  raise ValueError("Automation is missing or no longer approved")
 try:
  graph = json.loads(asset.body)
  built = build_email_automation(graph)
 except (json.JSONDecodeError, ValueError) as exc:
  raise ValueError("Stored automation graph failed validation") from exc
 metadata = dict(asset.metadata_json or {})
 if built["sha256"] != metadata.get("graph_sha256"):
  raise ValueError("Stored automation graph checksum does not match reviewed metadata")
 if expected_sha256 and built["sha256"] != expected_sha256:
  raise ValueError("Queued email belongs to a different automation graph version")
 if not built["graph"].get("target_jurisdictions"):
  raise ValueError("Automation has no target jurisdiction scope")
 return asset, built["graph"], built["sha256"]


async def _queue_next_automation_step(
 session: AsyncSession,
 *,
 workspace_id: str,
 lead: Lead,
 sent_message: ScheduledEmail,
 now: datetime,
) -> None:
 condition = dict(sent_message.condition_json or {})
 automation_id = str(condition.get("automation_id") or "")
 current_step_id = str(condition.get("automation_step_id") or "")
 if not automation_id or not current_step_id:
  return
 try:
  asset, graph, graph_sha = await _load_approved_automation_graph(
   session, workspace_id=workspace_id, automation_id=automation_id,
   expected_sha256=str(condition.get("automation_graph_sha256") or ""),
  )
  resolved = resolve_next_email_step(
   graph, current_step_id=current_step_id,
   purchased=lead.purchased_at is not None, engaged=bool(lead.engaged),
  )
 except ValueError as exc:
  session.add(AuditLog(
   workspace_id=workspace_id, actor="system",
   action="email_automation.progress_blocked", resource_type="content_asset",
   resource_id=automation_id, outcome="graph_invalid",
   details_json={"lead_id": lead.id, "sent_step_id": current_step_id, "reason": str(exc)[:300], "provider_already_sent_previous_step": True},
  ))
  return
 if resolved is None:
  session.add(AuditLog(
   workspace_id=workspace_id, actor="system",
   action="email_automation.completed", resource_type="content_asset",
   resource_id=asset.id, outcome="terminal_branch_reached",
   details_json={"lead_id": lead.id, "last_step_id": current_step_id, "graph_sha256": graph_sha},
  ))
  return
 step = resolved["step"]
 max_sequence = await session.scalar(select(func.max(ScheduledEmail.sequence_day)).where(
  ScheduledEmail.workspace_id == workspace_id, ScheduledEmail.lead_id == lead.id,
 ))
 sequence_day = int(max_sequence if max_sequence is not None else sent_message.sequence_day) + 1
 body_text = str(step["body_text"]).strip()
 if step.get("has_affiliate_links") and step.get("affiliate_disclosure") and step["affiliate_disclosure"] not in body_text:
  body_text += "\n\n" + str(step["affiliate_disclosure"]).strip()
 unsubscribe_url = _unsubscribe_url(lead.id, int(time.time()))
 body_text += f"\n\nUnsubscribe: {unsubscribe_url}"
 body_html = (
  "<!doctype html><html><body>"
  + "".join(f"<p>{html.escape(line)}</p>" for line in body_text.splitlines() if line.strip())
  + f'<p><a href="{html.escape(unsubscribe_url, quote=True)}">Unsubscribe</a></p></body></html>'
 )
 session.add(ScheduledEmail(
  workspace_id=workspace_id, lead_id=lead.id, sequence_day=sequence_day,
  subject=str(step["subject"])[:500], body_html=body_html, body_text=body_text,
  condition_json={
   "requires_consent": True, "skip_if_unsubscribed": True,
   "automation_id": automation_id, "automation_step_id": step["id"],
   "automation_graph_sha256": graph_sha, "automation_branch_path": resolved["branch_path"],
   "automation_target_jurisdictions": list(graph["target_jurisdictions"]),
  },
  send_at=now + timedelta(days=int(step.get("delay_days", 0))), status="scheduled",
 ))
 session.add(AuditLog(
  workspace_id=workspace_id, actor="system",
  action="email_automation.step_scheduled", resource_type="content_asset",
  resource_id=asset.id, outcome="next_step_queued",
  details_json={
   "lead_id": lead.id, "previous_step_id": current_step_id,
   "next_step_id": step["id"], "sequence_day": sequence_day,
   "branch_path": resolved["branch_path"], "graph_sha256": graph_sha,
  },
 ))


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
    "skipped": 0,
    "provider_configured": False,
    "reason": "Configure RESEND_API_KEY and RESEND_FROM_EMAIL",
   }
  owns_session = session is None
  if owns_session:
   session = SessionLocal()
  assert session is not None
  sent = skipped = attempted = 0
  now = datetime.now(timezone.utc)
  stale_lease_before = now - timedelta(minutes=15)
  safe_retry_before = now - timedelta(hours=23)
  try:
   # Recover interrupted claims while the provider's 24-hour idempotency window
   # is still open. Older ambiguous sends need manual reconciliation, not a
   # potentially duplicate automatic delivery.
   await session.execute(
    update(ScheduledEmail)
    .where(
     ScheduledEmail.workspace_id == owner_workspace_id,
     ScheduledEmail.status == "sending",
     ScheduledEmail.claimed_at.is_not(None),
     ScheduledEmail.claimed_at < safe_retry_before,
    )
    .values(
     status="delivery_unknown",
     claimed_at=None,
     last_error="Delivery claim exceeded the safe provider idempotency retry window; manual reconciliation required.",
    )
    .execution_options(synchronize_session=False)
   )
   await session.execute(
    update(ScheduledEmail)
    .where(
     ScheduledEmail.workspace_id == owner_workspace_id,
     ScheduledEmail.status == "sending",
     ScheduledEmail.claimed_at.is_not(None),
     ScheduledEmail.claimed_at < stale_lease_before,
     ScheduledEmail.claimed_at >= safe_retry_before,
    )
    .values(
     status="retry",
     claimed_at=None,
     send_at=now,
     last_error="Recovered stale delivery claim; retry will reuse the stable provider idempotency key.",
    )
    .execution_options(synchronize_session=False)
   )
   await session.commit()

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
   # End the read transaction before the conditional claim UPDATE. That lets
   # parallel workers race on one atomic status transition rather than holding
   # stale read snapshots while attempting to write.
   await session.commit()

   for message in messages:
    claim = await session.execute(
     update(ScheduledEmail)
     .where(
      ScheduledEmail.id == message.id,
      ScheduledEmail.workspace_id == owner_workspace_id,
      ScheduledEmail.status.in_(["scheduled", "retry"]),
      ScheduledEmail.send_at <= now,
     )
     .values(
      status="sending",
      attempts=ScheduledEmail.attempts + 1,
      claimed_at=now,
      last_error="Delivery claim active",
     )
     .execution_options(synchronize_session=False)
    )
    if claim.rowcount != 1:
     skipped += 1
     continue
    await session.commit()
    await session.refresh(message)
    attempted += 1

    lead = await session.scalar(
     select(Lead).where(
      Lead.id == message.lead_id,
      Lead.workspace_id == owner_workspace_id,
     )
    )
    if not lead or lead.unsubscribed_at:
     message.status = "suppressed"
     message.claimed_at = None
     message.last_error = "Lead is missing or has unsubscribed"
     skipped += 1
     continue
    if message.condition_json.get("skip_days_3_4_if_purchased") and lead.purchased_at:
     message.status = "suppressed_purchased"
     message.claimed_at = None
     message.last_error = "Lead purchased before the scheduled email was sent"
     skipped += 1
     continue
    automation_id = str((message.condition_json or {}).get("automation_id") or "").strip()
    if automation_id:
     expected_sha = str((message.condition_json or {}).get("automation_graph_sha256") or "")
     try:
      _asset, automation_graph, _graph_sha = await _load_approved_automation_graph(
       session, workspace_id=owner_workspace_id, automation_id=automation_id, expected_sha256=expected_sha
      )
     except ValueError as exc:
      message.status = "suppressed"
      message.claimed_at = None
      message.last_error = f"Automation review/checksum failure: {str(exc)[:250]}"
      session.add(AuditLog(
       workspace_id=owner_workspace_id, actor="system",
       action="email_automation.delivery_blocked", resource_type="scheduled_email",
       resource_id=message.id, outcome="automation_invalid",
       details_json={"automation_id": automation_id, "lead_id": message.lead_id, "provider_called": False},
      ))
      skipped += 1
      continue
     assessment = await find_current_assessment(
      session, workspace_id=owner_workspace_id, activity="email_marketing",
      jurisdictions=list(automation_graph.get("target_jurisdictions") or []), channel="email",
     )
     if assessment is None:
      prior_error = str(message.last_error or "")
      message.status = "scheduled"
      message.claimed_at = None
      message.attempts = max(0, int(message.attempts or 0) - 1)
      message.send_at = now + timedelta(hours=6)
      message.last_error = "Current approved email-marketing compliance assessment required for target jurisdictions; provider was not called."
      if "Current approved email-marketing compliance assessment required" not in prior_error:
       session.add(AuditLog(
        workspace_id=owner_workspace_id, actor="system",
        action="compliance.live_action.blocked", resource_type="scheduled_email",
        resource_id=message.id, outcome="email_marketing_approval_required",
        details_json={
         "automation_id": automation_id, "activity": "email_marketing",
         "target_jurisdictions": list(automation_graph.get("target_jurisdictions") or []),
         "channel": "email", "provider_called": False,
        },
       ))
      skipped += 1
      continue
    if message.attempts > 4:
     message.status = "failed_permanent"
     message.claimed_at = None
     message.last_error = "Maximum delivery attempts exceeded"
     skipped += 1
     continue

    # Keep the RFC List-Unsubscribe target stable across retries so Resend sees
    # the same request payload for the same Idempotency-Key.
    unsubscribe_match = re.search(r"Unsubscribe:\s*(https?://\S+)", message.body_text)
    if unsubscribe_match:
     unsubscribe_url = unsubscribe_match.group(1).rstrip(".,)")
    else:
     created_at = message.created_at
     if created_at is not None and created_at.tzinfo is None:
      created_at = created_at.replace(tzinfo=timezone.utc)
     unsubscribe_url = _unsubscribe_url(lead.id, int(created_at.timestamp()) if created_at else int(now.timestamp()))
    try:
     response = await request_public_json(
      "https://api.resend.com/emails",
      method="POST",
      json_body={
       "from": settings.resend_from_email,
       "to": [lead.email],
       "subject": message.subject,
       "html": message.body_html,
       "text": message.body_text,
       "headers": {
        "List-Unsubscribe": f"<{unsubscribe_url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
       },
      },
      headers={
       "Authorization": f"Bearer {settings.resend_api_key}",
       "Idempotency-Key": f"scheduled-email/{owner_workspace_id}/{message.id}",
      },
      timeout=20,
      max_bytes=1_000_000,
     )
     message.status = "sent"
     message.claimed_at = None
     message.provider_message_id = response.get("id")
     message.last_error = None
     sent += 1
     if automation_id:
      await _queue_next_automation_step(
       session, workspace_id=owner_workspace_id, lead=lead, sent_message=message, now=now
      )
    except Exception as exc:
     message.status = "retry" if message.attempts < 4 else "failed_permanent"
     message.claimed_at = None
     message.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
     message.send_at = now + timedelta(minutes=min(2 ** message.attempts * 5, 180))
   await session.commit()
   return {
    "sent": sent,
    "skipped": skipped,
    "attempted": attempted,
    "provider_configured": True,
    "workspace_id": owner_workspace_id,
   }
  finally:
   if owns_session:
    await session.close()


async def unsubscribe_lead(session: AsyncSession, lead_id: str) -> bool:
 """Record a signed recipient opt-out and immediately suppress pending sequence mail."""
 lead = await session.scalar(select(Lead).where(Lead.id == str(lead_id)))
 if lead is None:
  return False

 workspace_id = str(lead.workspace_id)
 with workspace_scope(workspace_id):
  previously_unsubscribed = lead.unsubscribed_at is not None
  if not previously_unsubscribed:
   lead.unsubscribed_at = datetime.now(timezone.utc)

  # Cancel pending/retry items in the same transaction as the suppression record.
  # Items already in "sending" have been claimed by an active worker and are
  # checked against the current Lead opt-out before the provider request.
  result = await session.execute(
   update(ScheduledEmail)
   .where(
    ScheduledEmail.workspace_id == workspace_id,
    ScheduledEmail.lead_id == lead.id,
    ScheduledEmail.status.in_(["scheduled", "retry"]),
   )
   .values(
    status="suppressed",
    claimed_at=None,
    last_error="Recipient unsubscribed; pending delivery canceled.",
   )
   .execution_options(synchronize_session=False)
  )
  cancelled = int(result.rowcount or 0)
  if not previously_unsubscribed or cancelled:
   session.add(AuditLog(
    workspace_id=workspace_id,
    actor="recipient",
    action="email.consent.unsubscribed",
    resource_type="lead",
    resource_id=lead.id,
    outcome="suppressed",
    details_json={
     "source": "signed_unsubscribe_link",
     "pending_messages_cancelled": cancelled,
     "repeat_opt_out": previously_unsubscribed,
     "email_delivery_suppressed": True,
    },
   ))
  await session.commit()
 return True
