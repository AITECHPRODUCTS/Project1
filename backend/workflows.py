from __future__ import annotations
from typing import Any
from sqlalchemy import select
from backend.core.errors import VerificationRequiredError
from backend.core.state_machine import WorkflowStep
from backend.database import SessionLocal
from backend.models import Conversion
from backend.services.s1_research import monopoly_niche_finder,competitor_spy,trending_content_scout
from backend.services.s2_s3_content import affiliate_blog_builder,content_research_brief,keyword_cluster_architect,viral_post_writer,tiktok_script_writer
from backend.services.s4_s5_landing import grand_slam_offer_generator,social_media_scheduler,value_ladder_architect
from backend.services.analytics_utils import conversion_tracker
from backend.services.ad_manager import evaluate_roas
from backend.services.s6_s8_analytics import self_improver_loop

LABELS={"S1":"Research & Opportunity Intelligence","S2":"Content & Creative Studio","S3":"SEO & Affiliate Blog Engine","S4":"Offer & Landing Experience","S5":"Distribution & Publishing","S6":"Measurement & Experimentation","S7":"Automation & Resource Control","S8":"Performance Memory & Meta-Learning"}
async def s1(state:dict[str,Any])->dict[str,Any]:
 out={"status":"completed"}
 if state.get("niche_candidates"):out["niches"]=monopoly_niche_finder(state["niche_candidates"],top_n=int(state.get("top_n",10)))
 if state.get("competitor_urls"):out["competitors"]=await competitor_spy(state["competitor_urls"][:10])
 query=state.get("trend_query") or state.get("topic")
 if query and state.get("scout_trends",True):out["trends"]=await trending_content_scout(str(query),limit=int(state.get("trend_limit",10)));state["hooks"]=out["trends"].get("results",[])
 if len(out)==1:return {"s1_result":{"status":"skipped","reason":"Provide niche_candidates, competitor_urls or trend_query."}}
 return {"s1_result":out}
async def s2(state:dict[str,Any])->dict[str,Any]:
 topic=str(state.get("topic") or "");hooks=state.get("hooks") or state.get("observed_hooks") or []
 if not topic or not hooks:return {"s2_result":{"status":"skipped","reason":"Topic and observed hooks required."}}
 out={"status":"completed"}
 if state.get("create_social_post",True):out["social_post"]=await viral_post_writer(topic,hooks,str(state.get("social_platform") or "x"))
 if state.get("create_tiktok_script",True):out["tiktok_script"]=await tiktok_script_writer(topic,hooks,int(state.get("video_duration_seconds",35)))
 return {"s2_result":out}
async def s3(state:dict[str,Any])->dict[str,Any]:
 if not state.get("topic") or not state.get("build_blog",True):return {"s3_result":{"status":"skipped","reason":"Topic missing or build_blog=false."}}
 research={}
 source_urls=state.get("source_urls") or []
 if source_urls:
  research=await content_research_brief(str(state["topic"]),source_urls[:10]);state["research_brief"]=research
 blog=await affiliate_blog_builder(str(state["topic"]),product=state.get("product"),canonical_url=state.get("canonical_url"),minimum_words=int(state.get("minimum_words",1500)),research_context=str(research.get("brief") or ""))
 out={"blog":blog,"research_brief":research if research else None}
 if state.get("keywords"):out["keyword_cluster"]=keyword_cluster_architect(state["keywords"])
 return {"s3_result":{"status":"completed",**out}}
async def s4(state:dict[str,Any])->dict[str,Any]:
 product=state.get("product");audience=str(state.get("audience") or "")
 if not isinstance(product,dict) or not product.get("name") or not audience:return {"s4_result":{"status":"skipped","reason":"Verified product facts and audience are required."}}
 out={"status":"completed"}
 if state.get("create_offer",True):out["offer"]=await grand_slam_offer_generator(product,audience,str(state.get("main_problem") or "the supplied audience problem"))
 if state.get("create_value_ladder",True):out["value_ladder"]=await value_ladder_architect(audience,product,state.get("deliverable_assets"))
 return {"s4_result":out}
async def s5(state:dict[str,Any])->dict[str,Any]:
 requests=state.get("publish_requests") or []
 if not requests:return {"s5_result":{"status":"skipped","reason":"No publish request supplied; outputs remain drafts."}}
 results=[]
 for item in requests[:10]:
  if item.get("require_verification") and not state.get("_verification_response"):
   raise VerificationRequiredError("Provider requires human verification before continuing.",action=str(item.get("verification_action") or "verification"))
  # Credentials/dry-run flags are checked by the provider adapter; the OTP is never logged or persisted.
  result=await social_media_scheduler(str(item.get("platform") or ""),dict(item.get("post") or {}));results.append(result)
 state.pop("_verification_response",None)
 return {"s5_result":{"status":"completed","publish_results":results}}
async def s6(state:dict[str,Any])->dict[str,Any]:
 url=state.get("tracking_url");out={"status":"completed","utm":conversion_tracker(str(url)) if url else None,"conversion_events_saved":0}
 for event in (state.get("conversion_events") or [])[:100]:
  network=str(event.get("network") or "manual_import").lower()[:100];external=str(event.get("external_event_id") or event.get("transaction_id") or "")[:255]
  if not external:continue
  async with SessionLocal() as db:
   if await db.scalar(select(Conversion.id).where(Conversion.network==network,Conversion.external_event_id==external)):continue
   parsed=conversion_tracker(str(event.get("url") or ""));commission=max(0,float(event.get("commission",0) or 0));revenue=max(0,float(event.get("revenue",0) or 0))
   db.add(Conversion(network=network,external_event_id=external,click_id=event.get("click_id") or parsed.get("click_id"),utm_source=event.get("utm_source") or parsed.get("utm_source"),utm_medium=event.get("utm_medium") or parsed.get("utm_medium"),utm_campaign=event.get("utm_campaign") or parsed.get("utm_campaign"),utm_content=event.get("utm_content") or parsed.get("utm_content"),hook=event.get("hook") or event.get("utm_content") or parsed.get("utm_content"),commission=commission,revenue=revenue,currency=str(event.get("currency") or "USD")[:3].upper(),status=str(event.get("status") or "pending").lower(),event_json=event));await db.commit();out["conversion_events_saved"]+=1
 return {"s6_result":out}
async def s7(state:dict[str,Any])->dict[str,Any]:
 metrics=state.get("campaign_metrics") or []
 if not metrics:return {"s7_result":{"status":"skipped","reason":"No campaign metrics provided; no ad changes performed."}}
 decisions=[]
 for row in metrics[:100]:
  d=evaluate_roas(str(row.get("campaign_id") or "unknown"),float(row.get("spend",0) or 0),float(row.get("commission",0) or 0),float(row.get("threshold",1.2) or 1.2));decisions.append({"campaign_id":d.campaign_id,"roas":d.roas,"threshold":d.threshold,"pause_recommended":d.pause_recommended,"executed":False,"reason":d.reason})
 return {"s7_result":{"status":"completed","decisions":decisions}}
async def s8(state:dict[str,Any])->dict[str,Any]:
 if not state.get("run_learning",True):return {"s8_result":{"status":"skipped","reason":"run_learning=false"}}
 return {"s8_result":await self_improver_loop(lookback_days=int(state.get("learning_lookback_days",30)))}
STEPS=[WorkflowStep(key,LABELS[key],fn) for key,fn in [("S1",s1),("S2",s2),("S3",s3),("S4",s4),("S5",s5),("S6",s6),("S7",s7),("S8",s8)]]
def resolve_steps(name:str)->list[WorkflowStep]:
 norm=name.lower().replace("-","_")
 if norm in {"full_flywheel","affiliate_flywheel","all"}:return list(STEPS)
 for step in STEPS:
  if step.key==name.upper():return [step]
 raise ValueError("Choose full_flywheel or S1 through S8")
