from __future__ import annotations
import asyncio
from datetime import datetime,time,timezone
from sqlalchemy import func,select
from backend.config import get_settings
from backend.core.errors import ResourceBudgetExceeded
from backend.database import SessionLocal
from backend.models import ResourceUsage
_lock=asyncio.Lock()
def estimate_cost(input_tokens:int,output_tokens:int,local:bool=False)->float:
 s=get_settings();ir=s.local_input_cost_per_million_usd if local else s.llm_input_cost_per_million_usd;orate=s.local_output_cost_per_million_usd if local else s.llm_output_cost_per_million_usd
 return max(0,input_tokens)*max(0,ir)/1e6+max(0,output_tokens)*max(0,orate)/1e6
async def reserve(niche:str,provider:str,model:str,input_tokens:int,output_tokens:int)->str:
 s=get_settings();now=datetime.now(timezone.utc);start=datetime.combine(now.date(),time.min,tzinfo=timezone.utc);niche=" ".join(niche.lower().split())[:200] or "general";estimate=estimate_cost(input_tokens,output_tokens,provider.startswith("local"))
 async with _lock,SessionLocal() as db:
  total=float(await db.scalar(select(func.coalesce(func.sum(ResourceUsage.estimated_cost_usd),0.0)).where(ResourceUsage.created_at>=start)) or 0);used=float(await db.scalar(select(func.coalesce(func.sum(ResourceUsage.estimated_cost_usd),0.0)).where(ResourceUsage.created_at>=start,ResourceUsage.niche==niche)) or 0)
  if total+estimate>s.resource_budget_usd_per_day+1e-9:raise ResourceBudgetExceeded(f"Daily model budget exceeded: ${total+estimate:.4f} > ${s.resource_budget_usd_per_day:.2f}")
  if used+estimate>s.resource_budget_usd_per_niche+1e-9:raise ResourceBudgetExceeded(f"Per-niche model budget exceeded for {niche!r}")
  row=ResourceUsage(niche=niche,provider=provider,model=model[:300],prompt_tokens_estimated=input_tokens,output_tokens_reserved=output_tokens,estimated_cost_usd=estimate,status="reserved");db.add(row);await db.commit();return row.id
async def finalize(reservation_id:str,input_tokens:int,output_tokens:int,status:str="completed")->None:
 async with SessionLocal() as db:
  row=await db.get(ResourceUsage,reservation_id)
  if not row:return
  row.input_tokens_actual=max(0,input_tokens);row.output_tokens_actual=max(0,output_tokens)
  if status=="completed":row.estimated_cost_usd=max(row.estimated_cost_usd,estimate_cost(input_tokens,output_tokens,row.provider.startswith("local")))
  row.status=status[:40];row.completed_at=datetime.now(timezone.utc);await db.commit()
async def status()->dict:
 s=get_settings();now=datetime.now(timezone.utc);start=datetime.combine(now.date(),time.min,tzinfo=timezone.utc)
 async with SessionLocal() as db:
  total=float(await db.scalar(select(func.coalesce(func.sum(ResourceUsage.estimated_cost_usd),0.0)).where(ResourceUsage.created_at>=start)) or 0);rows=(await db.execute(select(ResourceUsage.niche,func.sum(ResourceUsage.estimated_cost_usd)).where(ResourceUsage.created_at>=start).group_by(ResourceUsage.niche))).all()
 return {"date_utc":now.date().isoformat(),"daily_budget_usd":s.resource_budget_usd_per_day,"daily_estimated_used_usd":round(total,6),"daily_estimated_remaining_usd":round(max(0,s.resource_budget_usd_per_day-total),6),"niche_budget_usd":s.resource_budget_usd_per_niche,"niche_estimated_used_usd":{k:round(float(v or 0),6) for k,v in rows},"note":"Configured-token-rate estimate; not a provider invoice. Reservation lock is process-local; use a distributed lock before multi-replica workers."}
