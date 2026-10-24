from __future__ import annotations
import hashlib
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import get_settings
from backend.database import SessionLocal
from backend.models import ClickEvent,Conversion
from ai_memory.rag_chain import rag
async def self_improver_loop(session:AsyncSession|None=None,*,lookback_days:int=30)->dict[str,Any]:
 s=get_settings();owns=session is None
 if owns:session=SessionLocal()
 assert session is not None;cutoff=datetime.now(timezone.utc)-timedelta(days=max(1,min(lookback_days,180)))
 try:
  conversions=list((await session.scalars(select(Conversion).where(Conversion.created_at>=cutoff,Conversion.hook.is_not(None),Conversion.status.in_(["approved","paid","complete","completed","confirmed"])))).all());clicks=list((await session.scalars(select(ClickEvent).where(ClickEvent.created_at>=cutoff))).all());counts=Counter()
  for click in clicks:
   meta=click.utm_json or {};hook=str(meta.get("utm_content") or meta.get("hook") or "").strip()
   if hook:counts[hook]+=1
  grouped=defaultdict(list)
  for row in conversions:
   hook=str(row.hook or row.utm_content or "").strip()
   if hook:grouped[hook].append(row)
  learned=[]
  for hook,rows in grouped.items():
   n=len(rows);click_count=counts.get(hook,0)
   if n<s.min_conversions_for_learning or click_count<=0:continue
   rate=n/max(n,click_count)
   if rate<s.min_hook_conversion_rate:continue
   commission=round(sum(max(0,float(x.commission or 0)) for x in rows),2);networks=sorted({x.network for x in rows});doc=f"Observed performance hypothesis, not a promise. Hook: {hook}. Approved conversions: {n}. Tracked clicks: {click_count}. Observed rate: {rate:.4f}. Commission recorded: {commission:.2f}. Networks: {', '.join(networks)}. Cutoff: {cutoff.isoformat()}. Validate in future controlled tests."
   learned.append({"id":hashlib.sha256(f"perf:{hook}:{cutoff.date()}".encode()).hexdigest(),"hook":hook,"conversions":n,"clicks":click_count,"rate":rate,"commission":commission,"source_networks":networks,"text":doc})
  if learned:
   try:from langchain_core.documents import Document
   except ImportError as exc:raise RuntimeError("Install RAG dependencies to store S8 performance memory") from exc
   store=await __import__("asyncio").to_thread(rag.vectorstore);docs=[Document(page_content=x["text"],metadata={"source":"performance_memory","document_kind":"observed_performance","hook":x["hook"],"conversion_count":x["conversions"],"click_count":x["clicks"],"conversion_rate":x["rate"],"observed_on":datetime.now(timezone.utc).isoformat()}) for x in learned]
   await __import__("asyncio").to_thread(store.add_documents,documents=docs,ids=[x["id"] for x in learned])
  return {"lookback_days":lookback_days,"conversions_scanned":len(conversions),"clicks_scanned":len(clicks),"hooks_added_to_chroma":len(learned),"learned_hooks":[{k:v for k,v in x.items() if k!="text"} for x in learned],"learning_mode":"RAG performance memory; weight fine-tuning is separate"}
 finally:
  if owns:await session.close()
