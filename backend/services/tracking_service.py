from __future__ import annotations
import hashlib,hmac,time
from datetime import datetime,timezone
from typing import Any
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import get_settings
from backend.models import Campaign,ClickEvent
from backend.services.url_safety import validate_public_http_url
def sign_click(click_id:str,timestamp:int)->str:
 secret=get_settings().tracking_hmac_secret
 if len(secret)<32:raise RuntimeError("TRACKING_HMAC_SECRET must be a fresh 32+ char value")
 return hmac.new(secret.encode(),f"{click_id}:{timestamp}".encode(),hashlib.sha256).hexdigest()
def verify_click_signature(click_id:str,timestamp:int,signature:str,max_age_seconds:int=86400)->bool:
 if abs(int(time.time())-timestamp)>max_age_seconds:return False
 try:return hmac.compare_digest(sign_click(click_id,timestamp),signature)
 except (ValueError,RuntimeError):return False
async def destination_healthy(url:str,timeout:float=4.0)->tuple[bool,int|None,str|None]:
 try:
  await validate_public_http_url(url)
  async with httpx.AsyncClient(timeout=httpx.Timeout(timeout,connect=2),follow_redirects=False,headers={"User-Agent":"AffiliateOSLinkHealth/0.1"}) as c:
   r=await c.head(url)
   if r.status_code in (405,501):r=await c.get(url,headers={"Range":"bytes=0-0"})
   return r.status_code<500 and r.status_code!=404,r.status_code,None
 except Exception as exc:return False,None,f"{type(exc).__name__}: {str(exc)[:150]}"
async def choose_destination(campaign:Campaign)->dict[str,Any]:
 ok,code,error=await destination_healthy(campaign.primary_destination)
 if ok:return {"destination":campaign.primary_destination,"route":"primary","status_code":code,"primary_healthy":True,"fallback_healthy":None,"health_error":None}
 if campaign.fallback_destination:
  f_ok,f_code,f_err=await destination_healthy(campaign.fallback_destination)
  if f_ok:return {"destination":campaign.fallback_destination,"route":"fallback","status_code":f_code,"primary_healthy":False,"fallback_healthy":True,"health_error":error or f"primary returned {code}"}
  return {"destination":None,"route":"blocked","status_code":f_code,"primary_healthy":False,"fallback_healthy":False,"health_error":f"primary unavailable ({error or code}); fallback unavailable ({f_err or f_code})"}
 return {"destination":None,"route":"blocked","status_code":code,"primary_healthy":False,"fallback_healthy":None,"health_error":error or f"primary returned {code}; no fallback configured"}
async def record_click_and_resolve(session:AsyncSession,campaign:Campaign,*,user_agent:str="",utm:dict[str,Any]|None=None)->dict[str,Any]:
 result=await choose_destination(campaign);campaign.primary_healthy=result.get("primary_healthy")
 if result.get("fallback_healthy") is not None:campaign.fallback_healthy=result["fallback_healthy"]
 campaign.health_last_checked_at=datetime.now(timezone.utc);campaign.health_last_error=str(result.get("health_error") or "")[:1000] or None
 click=ClickEvent(campaign_id=campaign.id,destination_url=campaign.primary_destination,chosen_destination=result.get("destination") or "",status_code=result.get("status_code"),user_agent_hash=hashlib.sha256(user_agent.encode()).hexdigest() if user_agent else None,utm_json=utm or {})
 session.add(click);await session.flush();return {**result,"click_id":click.click_id,"campaign_id":campaign.id}
