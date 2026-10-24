from __future__ import annotations
from typing import Any
from backend.adapters.base import AffiliateNetworkAdapter
from backend.tools.affiliate_api import OpenAffiliateClient
class OpenAffiliateAdapter(AffiliateNetworkAdapter):
 network_name="openaffiliate"
 def __init__(self,client:OpenAffiliateClient|None=None):self.client=client or OpenAffiliateClient()
 async def fetch_offers(self,*,query:str|None=None,limit:int=100)->list[dict[str,Any]]:return (await self.client.fetch_programs(q=query,limit=limit))["data"]
 def parse_conversion(self,payload:dict[str,Any])->dict[str,Any]:
  eid=payload.get("event_id") or payload.get("transaction_id")
  if not eid:raise ValueError("OpenAffiliate conversion payload needs a unique event ID")
  return {"network":self.network_name,"external_event_id":str(eid),"commission":float(payload.get("commission",0) or 0),"revenue":float(payload.get("revenue",0) or 0),"click_id":payload.get("click_id") or payload.get("subid"),"status":str(payload.get("status") or "pending").lower(),"raw":payload}
