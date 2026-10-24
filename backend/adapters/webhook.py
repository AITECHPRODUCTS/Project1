from __future__ import annotations
import hashlib,hmac
from typing import Any
from backend.adapters.base import AffiliateNetworkAdapter
class AggregatorWebhookAdapter(AffiliateNetworkAdapter):
 def __init__(self,network_name:str,secret:str):
  if len(secret)<32:raise ValueError("Webhook signing secret must have 32+ characters")
  self.network_name=network_name;self.secret=secret.encode()
 def verify(self,raw_body:bytes,signature:str)->bool:return hmac.compare_digest(hmac.new(self.secret,raw_body,hashlib.sha256).hexdigest(),signature)
 async def fetch_offers(self,*,query:str|None=None,limit:int=100)->list[dict[str,Any]]:return []
 def parse_conversion(self,payload:dict[str,Any])->dict[str,Any]:
  event=str(payload.get("event_id") or payload.get("transaction_id") or "")
  if not event:raise ValueError("Unique external event_id required")
  return {"network":self.network_name,"external_event_id":event,"click_id":payload.get("click_id") or payload.get("subid"),"commission":float(payload.get("commission",0) or 0),"revenue":float(payload.get("revenue",0) or 0),"status":str(payload.get("status") or "pending").lower(),"raw":payload}
