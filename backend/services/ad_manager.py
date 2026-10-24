from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from backend.config import get_settings
from backend.core.errors import IntegrationNotConfiguredError
import httpx
@dataclass(frozen=True)
class ROASDecision:
 campaign_id:str;spend:float;commission:float;roas:float|None;threshold:float;pause_recommended:bool;executed:bool;reason:str
def evaluate_roas(campaign_id:str,spend:float,commission:float,threshold:float=1.2)->ROASDecision:
 spend=max(0,float(spend));commission=max(0,float(commission));threshold=max(0,float(threshold));roas=commission/spend if spend>0 else None;should=spend>0 and roas is not None and roas<threshold
 return ROASDecision(campaign_id,spend,commission,roas,threshold,should,False,"Stop-loss recommendation only; no remote campaign state was changed." if should else "ROAS is above threshold or there is no spend data.")
async def pause_meta_campaign(campaign_id:str,access_token:str)->dict[str,Any]:
 if not get_settings().ad_automation_execute:return {"executed":False,"reason":"AD_AUTOMATION_EXECUTE=false"}
 if not campaign_id or not access_token:raise IntegrationNotConfiguredError("Meta campaign id and authorized access token required")
 async with httpx.AsyncClient(timeout=15,follow_redirects=False) as c:
  r=await c.post(f"https://graph.facebook.com/v23.0/{campaign_id}",data={"status":"PAUSED","access_token":access_token});r.raise_for_status();data=r.json()
 return {"executed":bool(data.get("success")),"provider":"meta","response":data}
