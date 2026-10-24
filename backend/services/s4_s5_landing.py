from __future__ import annotations
import html
from datetime import datetime,timezone
from typing import Any
import httpx
from backend.config import get_settings
from backend.core.errors import IntegrationNotConfiguredError
from backend.services.llm import llm_service
def _esc(x:Any)->str:return html.escape(str(x),quote=True)
async def grand_slam_offer_generator(product:dict[str,Any],audience:str,main_problem:str)->dict[str,Any]:
 if not product.get("name") or not audience.strip() or not main_problem.strip():raise ValueError("product.name, audience and main_problem required")
 prompt=("Create an ethical, deliverable Hormozi-inspired offer design using desired outcome, perceived likelihood, time, effort. Return positioning, value proposition, objections, bonus ideas explicitly marked unverified unless deliverables are supplied, proof required, guarantee boundaries, CTA, disclosure, and validation checklist. No fake scarcity/testimonials or ungrounded promises.\n"+f"Product facts: {product}\nAudience: {audience}\nProblem: {main_problem}")
 out=await llm_service.complete("You are a compliant direct-response offer strategist; truthfulness outranks persuasion.",prompt,temperature=.4,niche=audience)
 return {"offer":out["text"],"framework":"desired outcome / likelihood / time / effort trade-offs","rag_sources":out["sources"],"provider":out["provider"],"requires_review":True}
async def value_ladder_architect(audience:str,product:dict[str,Any],assets:list[dict[str,Any]]|None=None)->dict[str,Any]:
 prompt=f"Design FREE, optional starter, core affiliate recommendation and optional premium steps for {audience}. Do not invent prices or assets. State who should not buy and alternatives. Product facts={product}; assets available={assets or []}. Return JSON if possible."
 out=await llm_service.complete("You are a customer journey architect; do not promise resources that don't exist.",prompt,niche=audience)
 return {"ladder":out["text"],"rag_sources":out["sources"],"provider":out["provider"],"requires_review":True}
def squeeze_page_builder(*,headline:str,subheadline:str,benefit_bullets:list[str],form_action:str="/api/public/leads/capture",privacy_url:str,affiliate_disclosure:str|None=None,lead_magnet:str="Free resource",audience:str="website subscriber",workspace_token:str|None=None)->str:
 if not headline.strip() or not form_action.startswith("/") or form_action.startswith("//"):raise ValueError("headline required and form_action must be same-origin path")
 if not privacy_url.startswith(("https://","http://")):raise ValueError("privacy_url must be absolute HTTP(S)")
 bullets="".join(f'<li class="flex gap-3"><span aria-hidden="true">✓</span><span>{_esc(x)}</span></li>' for x in benefit_bullets[:8]);disclosure=affiliate_disclosure or "Disclosure: I may earn a commission from qualifying purchases through affiliate links."
 return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>{_esc(headline)}</title><script src="https://cdn.tailwindcss.com"></script><style>body{{background:#f8fafc;color:#1e293b}}.card{{box-shadow:8px 8px 16px #d1d9e6,-8px -8px 16px #fff}}.glass{{backdrop-filter:blur(16px);background:rgba(255,255,255,.78)}}</style></head><body><main class="min-h-screen p-4 py-12 flex items-center justify-center"><section class="card glass max-w-2xl w-full rounded-3xl p-8 sm:p-12"><p class="text-sm uppercase tracking-widest font-semibold text-indigo-600">A practical resource</p><h1 class="text-3xl sm:text-5xl font-bold mt-4">{_esc(headline)}</h1><p class="mt-5 text-lg text-slate-600">{_esc(subheadline)}</p><ul class="mt-8 space-y-3">{bullets}</ul><form class="mt-8 grid gap-4" action="{_esc(form_action)}" method="post"><input type="hidden" name="lead_magnet" value="{_esc(lead_magnet)}"><input type="hidden" name="audience" value="{_esc(audience)}"><input type="hidden" name="consent_source" value="squeeze_page">{f'<input type="hidden" name="workspace_token" value="{_esc(workspace_token)}">' if workspace_token else ""}<label for="email">Email address</label><input id="email" name="email" type="email" autocomplete="email" required maxlength="254" class="rounded-xl border border-slate-300 bg-white px-4 py-3"><label class="flex items-start gap-3 text-sm text-slate-600"><input type="checkbox" name="consent" value="yes" required class="mt-1"><span>I agree to receive this resource and related emails. I can unsubscribe at any time.</span></label><button class="rounded-xl bg-indigo-600 px-6 py-3 font-semibold text-white hover:bg-indigo-700 transition-all duration-300" type="submit">Send me the resource</button></form><p class="mt-5 text-xs text-slate-500">By submitting, you agree to our <a class="underline" href="{_esc(privacy_url)}">Privacy Policy</a>.</p><p class="mt-5 text-xs text-slate-500">{_esc(disclosure)}</p></section></main></body></html>'''
def email_drip_sequence(*,audience:str,lead_magnet:str,affiliate_offer:dict[str,Any],duration_days:int=5)->list[dict[str,Any]]:
 duration_days=max(5,min(int(duration_days),7))
 if not audience.strip() or not lead_magnet.strip():raise ValueError("audience and lead_magnet are required")
 offer_name=str(affiliate_offer.get("name") or "the recommended tool")
 messages=[{"goal":"deliver_resource","subject":f"Your {lead_magnet} is here","condition":"consent=true","content_brief":f"Deliver {lead_magnet}, set expectations, and ask the reader's main challenge. Do not lead with a hard sell."},{"goal":"quick_win","subject":"A quick win you can use today","condition":"consent=true AND not_unsubscribed","content_brief":f"Teach one practical step for {audience}. Link to a useful tutorial; no unsupported outcome promise."},{"goal":"problem_education","subject":"Why this problem keeps happening","condition":"engaged OR day_elapsed","content_brief":f"Explain common causes, trade-offs, and a simple checklist relevant to {audience}."},{"goal":"solution_comparison","subject":f"How to evaluate {offer_name}","condition":"clicked_resource OR day_elapsed","content_brief":f"Present an honest evaluation framework for {offer_name}, mention drawbacks and alternatives, and disclose affiliate links."},{"goal":"decision_support","subject":"A simple decision checklist","condition":"not_unsubscribed AND not_purchased","content_brief":"Give a concise decision checklist; never invent urgency or promise results. Include disclosure and unsubscribe controls."},{"goal":"follow_up","subject":"What would make this easier?","condition":"engaged AND not_purchased AND not_unsubscribed","content_brief":"Ask a helpful, non-manipulative question and offer a useful reply path."},{"goal":"recap","subject":"Your resources in one place","condition":"not_unsubscribed","content_brief":"Recap the free resources, clarify the affiliate relationship, and provide unsubscribe and preference links."}]
 offer_url=str(affiliate_offer.get("affiliate_url") or affiliate_offer.get("url") or "")
 result=[]
 for day,item in enumerate(messages[:duration_days]):
  content=item["content_brief"]
  if item["goal"]=="solution_comparison" and offer_url:content+=f" Verified product link: {offer_url}"
  result.append({"day":day,**item,"condition":item["condition"],"content_brief":content})
 return result
async def social_media_scheduler(platform:str,post:dict[str,Any],*,publish_at:datetime|None=None)->dict[str,Any]:
 s=get_settings();platform=platform.lower().strip()
 if publish_at and publish_at>datetime.now(timezone.utc):return {"status":"queue_required","platform":platform,"publish_at":publish_at.isoformat(),"published":False}
 if s.publishing_dry_run:return {"status":"dry_run","platform":platform,"payload":post,"published":False}
 async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
  if platform=="pinterest":
   if not s.pinterest_access_token:raise IntegrationNotConfiguredError("PINTEREST_ACCESS_TOKEN is required with pins:write authorization")
   required=(post.get("board_id"),post.get("title"),post.get("image_url"))
   if not all(required) or not str(post["image_url"]).startswith("https://"):raise ValueError("Pinterest needs board_id, title and HTTPS image_url")
   payload={"board_id":str(post["board_id"]),"title":str(post["title"])[:100],"description":str(post.get("description",""))[:800],"media_source":{"source_type":"image_url","url":post["image_url"]}}
   if post.get("link"):payload["link"]=post["link"]
   resp=await client.post("https://api.pinterest.com/v5/pins",json=payload,headers={"Authorization":f"Bearer {s.pinterest_access_token}"});resp.raise_for_status();data=resp.json();return {"status":"published","platform":platform,"remote_id":data.get("id"),"response":data}
  if platform=="reddit":
   if not s.reddit_access_token:raise IntegrationNotConfiguredError("REDDIT_ACCESS_TOKEN must come from authorized user OAuth with submit scope")
   if not all(post.get(k) for k in ("subreddit","title","text")):raise ValueError("Reddit needs subreddit, title and text")
   resp=await client.post("https://oauth.reddit.com/api/submit",data={"sr":str(post["subreddit"]).removeprefix("r/"),"kind":"self","title":str(post["title"])[:300],"text":str(post["text"])[:40000],"resubmit":"true"},headers={"Authorization":f"Bearer {s.reddit_access_token}","User-Agent":s.reddit_user_agent});resp.raise_for_status();data=resp.json();errors=data.get("json",{}).get("errors",[])
   if errors:raise RuntimeError(f"Reddit rejected post: {errors}")
   return {"status":"published","platform":platform,"response":data}
 raise ValueError("Supported platforms: reddit, pinterest")
