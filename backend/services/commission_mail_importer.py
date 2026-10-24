from __future__ import annotations
import email,re,ssl,imaplib,os,asyncio
from email.utils import parsedate_to_datetime,parseaddr
from email.header import decode_header,make_header
from email.message import Message
from typing import Any
from bs4 import BeautifulSoup
from backend.config import get_settings
from backend.core.errors import IntegrationNotConfiguredError
from backend.database import SessionLocal
from backend.models import MailCommission
PATTERNS=[re.compile(r"commission(?:\s+earned|\s+of|\s+amount)?\s*[:=-]?\s*(?:USD\s*)?\$?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",re.I),re.compile(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s+(?:commission|earned)",re.I)]
def _decode(value:str|None)->str:
 if not value:return ""
 try:return str(make_header(decode_header(value)))
 except Exception:return value
def _body(msg:Message)->str:
 parts=[]
 if msg.is_multipart():
  for part in msg.walk():
   if part.get_content_type() not in {"text/plain","text/html"} or part.get_content_disposition()=="attachment":continue
   raw=part.get_payload(decode=True) or b"";parts.append(raw.decode(part.get_content_charset() or "utf-8",errors="replace"))
 else:
  raw=msg.get_payload(decode=True)
  if isinstance(raw,bytes):parts.append(raw.decode(msg.get_content_charset() or "utf-8",errors="replace"))
  elif isinstance(raw,str):parts.append(raw)
 return "\n".join(BeautifulSoup(x,"html.parser").get_text(" ",strip=True) if "<" in x else x for x in parts)
def parse_commission_message(raw:bytes)->dict[str,Any]|None:
 msg=email.message_from_bytes(raw);sender=parseaddr(msg.get("From",""))[1].lower();subject=_decode(msg.get("Subject"));text=_body(msg);hit=None
 for pattern in PATTERNS:
  match=pattern.search(text)
  if match:hit=match;break
 if not hit:return None
 amount=float(hit.group(1).replace(",",""));currency="USD"
 if re.search(r"\bEUR\b|€",text,re.I):currency="EUR"
 elif re.search(r"\bGBP\b|£",text,re.I):currency="GBP"
 nm=re.search(r"(?:on|from|via)\s+([A-Za-z0-9 ._-]{2,100}?)(?:\s+affiliate|\s+program|[.!\n]|$)",text,re.I)
 try:date=parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else None
 except (TypeError,ValueError):date=None
 mid=msg.get("Message-ID") or f"fallback-{__import__('hashlib').sha256((sender+subject+text[:200]).encode()).hexdigest()}"
 return {"message_id":mid.strip("<>"),"sender":sender,"subject":subject[:500],"network":nm.group(1).strip() if nm else "unclassified","commission":amount,"currency":currency,"email_date":date,"body_excerpt":text[:1500]}
async def import_commission_emails(*,mailbox:str="INBOX",limit:int=100)->dict[str,Any]:
 s=get_settings();allow={x.strip().lower() for x in os.getenv("MAIL_SENDER_ALLOWLIST","").split(",") if x.strip()}
 if not (s.mail_imap_host and s.mail_imap_user and s.mail_imap_password):raise IntegrationNotConfiguredError("Configure IMAP host/user/password")
 if not allow:raise IntegrationNotConfiguredError("MAIL_SENDER_ALLOWLIST must list approved sender addresses/domains")
 def fetch_sync():
  with imaplib.IMAP4_SSL(s.mail_imap_host,s.mail_imap_port,ssl_context=ssl.create_default_context(),timeout=20) as imap:
   imap.login(s.mail_imap_user,s.mail_imap_password);code,_=imap.select(mailbox,readonly=True)
   if code!="OK":raise RuntimeError("IMAP mailbox selection failed")
   code,data=imap.search(None,"UNSEEN")
   if code!="OK":raise RuntimeError("IMAP search failed")
   ids=(data[0].split() if data and data[0] else [])[-max(1,min(limit,500)):];items=[]
   for mid in ids:
    code,parts=imap.fetch(mid,"(RFC822)")
    if code!="OK":continue
    raw=next((x[1] for x in parts if isinstance(x,tuple) and isinstance(x[1],bytes)),None)
    if raw:
     item=parse_commission_message(raw)
     if item and any(item["sender"]==a or item["sender"].endswith("@"+a.lstrip("@")) for a in allow):items.append(item)
   return items
 try:items=await asyncio.to_thread(fetch_sync)
 except Exception as exc:raise RuntimeError(f"Mailbox read failed: {type(exc).__name__}") from exc
 from sqlalchemy import select
 async with SessionLocal() as db:
  created=0
  for item in items:
   if await db.scalar(select(MailCommission.id).where(MailCommission.message_id==item["message_id"])):continue
   db.add(MailCommission(message_id=item["message_id"],network=item["network"],commission=item["commission"],currency=item["currency"],status="pending_verification",email_date=item["email_date"],parsed_subject=item["subject"],evidence_json={k:v for k,v in item.items() if k!="body_excerpt"}));created+=1
  await db.commit()
 return {"messages_matched":len(items),"rows_created":created,"note":"Parsed mail records remain pending verification and are not confirmed cash receipts."}
