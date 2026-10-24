from __future__ import annotations
import os
from typing import Any
import httpx,yaml
from backend.adapters.base import AffiliateNetworkAdapter
from backend.adapters.openaffiliate import OpenAffiliateAdapter
from backend.core.errors import IntegrationNotConfiguredError
from backend.services.url_safety import validate_public_http_url
class ConfiguredJSONAdapter(AffiliateNetworkAdapter):
 def __init__(self,network_name:str,endpoint:str,token:str,items_path:str="data"):
  if not endpoint or not token:raise IntegrationNotConfiguredError(f"{network_name} API endpoint/token not configured")
  if not endpoint.startswith("https://"):raise ValueError("Provider endpoint must use HTTPS")
  self.network_name=network_name;self.endpoint=endpoint;self.token=token;self.items_path=items_path
 async def fetch_offers(self,*,query:str|None=None,limit:int=100)->list[dict[str,Any]]:
  normalized_limit=max(1,min(int(limit),200))
  # Configuration is not proof that a URL is safe. Validate before opening a
  # client so loopback, private, link-local and reserved destinations are blocked.
  endpoint=await validate_public_http_url(self.endpoint)
  async with httpx.AsyncClient(timeout=httpx.Timeout(20,connect=5),follow_redirects=False) as c:
   r=await c.get(endpoint,params={"q":query,"limit":normalized_limit},headers={"Authorization":f"Bearer {self.token}","Accept":"application/json"});r.raise_for_status();data=r.json()
  for part in self.items_path.split("."):data=data.get(part) if isinstance(data,dict) else None
  if not isinstance(data,list):raise ValueError(f"{self.network_name} response lacks configured list path {self.items_path}")
  return [x for x in data if isinstance(x,dict)][:normalized_limit]
 def parse_conversion(self,payload:dict[str,Any])->dict[str,Any]:
  event=payload.get("event_id") or payload.get("transaction_id")
  if not event:raise ValueError("event_id or transaction_id is required")
  return {"network":self.network_name,"external_event_id":str(event),"click_id":payload.get("click_id") or payload.get("subid"),"commission":float(payload.get("commission",0) or 0),"revenue":float(payload.get("revenue",0) or 0),"status":str(payload.get("status") or "pending").lower(),"raw":payload}
class AdapterFactory:
 def __init__(self,config_path:str="config.yaml"):self.config_path=config_path;self._registry={"openaffiliate":lambda cfg:OpenAffiliateAdapter()}
 def create(self,network:str)->AffiliateNetworkAdapter:
  try:
   with open(self.config_path,encoding="utf-8") as f:cfg=yaml.safe_load(f) or {}
   node=cfg.get("networks",{}).get(network,{})
  except (OSError,yaml.YAMLError) as exc:raise RuntimeError(f"Cannot read network config: {exc}") from exc
  if not node.get("enabled",False):raise IntegrationNotConfiguredError(f"Affiliate network {network!r} is disabled in config.yaml")
  adapter=node.get("adapter")
  if adapter in self._registry:return self._registry[adapter](node)
  if adapter=="generic_json":
   prefix=network.upper().replace("-","_").replace(".","_");return ConfiguredJSONAdapter(network,os.getenv(f"{prefix}_API_ENDPOINT", ""),os.getenv(f"{prefix}_API_TOKEN", ""),node.get("items_path","data"))
  if adapter=="clickbank":return ClickBankAdapter(items_path=node.get("items_path","data"))
  if adapter=="signed_proxy":return AmazonAssociatesAdapter(items_path=node.get("items_path","data"))
  raise IntegrationNotConfiguredError(f"No native adapter implemented for enabled network {network!r} (adapter={adapter})")
class ClickBankAdapter(ConfiguredJSONAdapter):
    """Configured adapter for an authorized ClickBank API proxy; endpoint/auth must be documented by operator."""
    def __init__(self, endpoint: str | None = None, token: str | None = None, items_path: str = "data"):
        super().__init__("clickbank", endpoint or os.getenv("CLICKBANK_API_ENDPOINT", ""), token or os.getenv("CLICKBANK_API_TOKEN", ""), items_path)
class AmazonAssociatesAdapter(ConfiguredJSONAdapter):
    """Uses only an operator-configured authorized signing proxy; PA-API signing isn't generic bearer auth."""
    def __init__(self, signed_proxy_endpoint: str | None = None, proxy_token: str | None = None, items_path: str = "data"):
        super().__init__("amazon_associates", signed_proxy_endpoint or os.getenv("AMAZON_ASSOCIATES_SIGNED_PROXY_ENDPOINT", ""), proxy_token or os.getenv("AMAZON_ASSOCIATES_PROXY_TOKEN", ""), items_path)
