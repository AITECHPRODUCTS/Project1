from __future__ import annotations
import os,re
from collections import Counter
from typing import Any, Mapping
VALID_STATES={"catalogued_disabled","not_configured","configured_not_health_checked","contract_tested","sandbox_verified","production_verified","not_implemented"}
_DISPLAY_NAMES={"amazon_associates":"Amazon Associates","cj_affiliate":"CJ Affiliate","openaffiliate":"OpenAffiliate","clickbank":"ClickBank","digistore24":"Digistore24","warriorplus":"WarriorPlus","jvzoo":"JVZoo","flipkart":"Flipkart","impact":"Impact","shareasale":"ShareASale"}
def _display_name(provider_id:str)->str:return _DISPLAY_NAMES.get(provider_id,re.sub(r"[_\-.]+"," ",provider_id).strip().title())
def _required_environment(provider_id:str,adapter:str)->tuple[str,...]:
 prefix=provider_id.upper().replace("-","_").replace(".","_")
 if adapter=="clickbank":return ("CLICKBANK_API_ENDPOINT","CLICKBANK_API_TOKEN")
 if adapter=="signed_proxy":return ("AMAZON_ASSOCIATES_SIGNED_PROXY_ENDPOINT","AMAZON_ASSOCIATES_PROXY_TOKEN")
 if adapter=="generic_json":return (f"{prefix}_API_ENDPOINT",f"{prefix}_API_TOKEN")
 if adapter=="webhook":return ("AFFILIATE_WEBHOOK_SECRET",)
 if adapter=="openaffiliate":return ()
 if adapter=="workspace_read_only":return ()
 return ()
def _coverage(adapter:str,enabled:bool)->str:
 if not enabled:return "catalog_only"
 if adapter=="workspace_read_only":return "workspace_credentialed_read_only"
 if adapter=="openaffiliate":return "read_only_directory_adapter"
 if adapter in {"clickbank","signed_proxy"}:return "operator_configured_proxy_boundary"
 if adapter=="generic_json":return "generic_contract_boundary"
 if adapter=="webhook":return "conversion_webhook_boundary"
 return "no_adapter"
def build_network_registry(config:Mapping[str,Any],environ:Mapping[str,str]|None=None)->dict[str,Any]:
 """Expose provider capability without treating config as authorization or connectivity evidence."""
 env=os.environ if environ is None else environ; config_networks=config.get("networks",{}); networks=config_networks if isinstance(config_networks,Mapping) else {};items=[]
 for provider_id,raw_node in networks.items():
  if not isinstance(provider_id,str) or not isinstance(raw_node,Mapping):continue
  adapter=str(raw_node.get("adapter") or "unknown");enabled=raw_node.get("enabled") is True;required_env=_required_environment(provider_id,adapter);missing_env=[name for name in required_env if not str(env.get(name,"")).strip()];coverage=_coverage(adapter,enabled)
  if not enabled:status="catalogued_disabled";reason="Catalog entry only; this provider is disabled in configuration."
  elif adapter not in {"openaffiliate","clickbank","signed_proxy","generic_json","webhook","workspace_read_only"}:status="not_implemented";reason="No supported adapter boundary is registered for this provider."
  elif adapter=="workspace_read_only":status="not_configured";reason="The connector is implemented, but each workspace owner must connect an active read-only API key before marketplace access is available."
  elif missing_env:status="not_configured";reason="Required environment configuration is missing: "+", ".join(missing_env)
  else:
   status="configured_not_health_checked";reason=("Read-only directory adapter exists; live contract and health have not been verified in this deployment." if adapter=="openaffiliate" else "Configuration is present; harmless provider call and authorization evidence are still required.")
  if status not in VALID_STATES:raise AssertionError(f"Invalid provider state: {status}")
  items.append({"provider_id":provider_id,"display_name":_display_name(provider_id),"adapter":adapter,"enabled":enabled,"status":status,"adapter_coverage":coverage,"required_configuration_present":enabled and adapter!="workspace_read_only" and not missing_env,"missing_configuration":missing_env,"credential_scope":"workspace" if adapter=="workspace_read_only" else "deployment","offer_discovery":adapter in {"openaffiliate","clickbank","signed_proxy","generic_json","workspace_read_only"} and enabled,"commission_reporting":False,"publish_content":False,"write_access_verified":False,"last_checked_at":None,"evidence_url":None,"reason":reason})
 rank={"configured_not_health_checked":0,"not_configured":1,"not_implemented":2,"catalogued_disabled":3};items.sort(key=lambda item:(rank.get(item["status"],4),item["provider_id"]));counts=Counter(item["status"] for item in items)
 return {"total":len(items),"counts":{state:counts.get(state,0) for state in sorted(VALID_STATES)},"items":items,"verification_policy":"No provider is marked connected, contract-tested, sandbox-verified, or production-verified from configuration alone. No network request was made by this endpoint."}
