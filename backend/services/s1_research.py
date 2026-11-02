from __future__ import annotations
import asyncio,base64,math,re
from typing import Any
from bs4 import BeautifulSoup
from backend.config import get_settings
from backend.services.url_safety import fetch_public_page, request_public_json
def monopoly_niche_finder(candidates:list[dict[str,Any]],*,top_n:int=10)->list[dict[str,Any]]:
 """Score supplied, measured keyword demand/competition. Never manufacture search volumes."""
 if not candidates:raise ValueError("Provide measured niche candidates")
 out=[]
 for row in candidates:
  niche=str(row.get("niche","")).strip()
  if not niche:continue
  try:volume=max(0,float(row["search_volume"]));competition=min(100,max(0,float(row["competition"])));monetization=min(100,max(0,float(row.get("monetization_score",50))))
  except (KeyError,TypeError,ValueError) as exc:raise ValueError(f"{niche or 'Candidate'} requires numeric search_volume and competition") from exc
  score=(math.log10(volume+1)/6)*(1-competition/100)*(.5+monetization/100)
  out.append({"niche":niche,"search_volume":volume,"competition":competition,"monetization_score":monetization,"opportunity_score":round(score,4),"evidence_sources":row.get("evidence_sources",[]),"confidence":"measured" if row.get("evidence_sources") else "unverified_input"})
 return sorted(out,key=lambda x:x["opportunity_score"],reverse=True)[:max(1,min(top_n,50))]
def extract_hook(text:str)->str:
 clean=re.sub(r"\s+"," ",text).strip();sentences=re.split(r"(?<=[.!?])\s+",clean)
 return (sentences[0] if sentences else clean)[:180]
async def competitor_spy(urls:list[str])->list[dict[str,Any]]:
 if not urls:raise ValueError("At least one public URL is required")
 async def fetch(url:str)->dict[str,Any]:
  try:
   body,ctype,status=await fetch_public_page(url);soup=BeautifulSoup(body,"html.parser");title=soup.title.get_text(" ",strip=True) if soup.title else "";meta=soup.find("meta",attrs={"name":"description"}) or soup.find("meta",attrs={"property":"og:description"});desc=meta.get("content","") if meta else "";headings=[h.get_text(" ",strip=True) for h in soup.find_all(["h1","h2","h3"])[:30]]
   for tag in soup(["script","style","nav","footer","noscript"]):tag.decompose()
   text=re.sub(r"\s+"," ",soup.get_text(" ",strip=True));counters={}
   for tag in soup.find_all("meta"):
    key=str(tag.get("property") or tag.get("name") or "").lower()
    if any(term in key for term in ("likes","comments","interactioncount","share-count")) and tag.get("content"):counters[key]=tag["content"]
   return {"url":url,"http_status":status,"content_type":ctype,"title":title[:500],"description":desc[:1200],"headings":headings,"word_count":len(re.findall(r"\w+",text)),"public_engagement_counters":counters,"note":"Missing engagement metrics remain unknown; login/paywall/CAPTCHA bypass is not attempted."}
  except Exception as exc:return {"url":url,"error":type(exc).__name__,"detail":str(exc)[:250]}
 return await asyncio.gather(*(fetch(url) for url in urls[:10]))
async def trending_content_scout(query:str,*,limit:int=10)->dict[str,Any]:
 settings=get_settings();query=query.strip();limit=max(1,min(int(limit),25))
 if not query:raise ValueError("query is required")
 results=[];providers={}
 if settings.reddit_client_id and settings.reddit_client_secret:
  try:
   basic=base64.b64encode(f"{settings.reddit_client_id}:{settings.reddit_client_secret}".encode()).decode()
   token_payload=await request_public_json("https://www.reddit.com/api/v1/access_token",method="POST",headers={"Authorization":f"Basic {basic}","User-Agent":settings.reddit_user_agent},data_body={"grant_type":"client_credentials"},timeout=12,max_bytes=1_000_000)
   token=str(token_payload["access_token"])
   reddit_payload=await request_public_json("https://oauth.reddit.com/search",method="GET",params={"q":query,"sort":"top","t":"month","limit":limit},headers={"Authorization":f"Bearer {token}","User-Agent":settings.reddit_user_agent},timeout=12,max_bytes=2_000_000)
   for child in reddit_payload.get("data",{}).get("children",[]):
    d=child.get("data",{});title=str(d.get("title",""));score=max(0,int(d.get("ups",0)))+2*max(0,int(d.get("num_comments",0)))
    results.append({"platform":"reddit","text":title,"hook":extract_hook(title),"url":"https://reddit.com"+str(d.get("permalink","")),"score":score,"likes":d.get("ups"),"comments":d.get("num_comments"),"source":"official_reddit_api"})
   providers["reddit"]="ok"
  except Exception as exc:providers["reddit"]=f"error:{type(exc).__name__}"
 else:providers["reddit"]="not_configured"
 if settings.x_bearer_token:
  try:
   x_payload=await request_public_json("https://api.x.com/2/tweets/search/recent",method="GET",params={"query":f"({query}) -is:retweet","max_results":min(100,limit),"tweet.fields":"public_metrics,created_at"},headers={"Authorization":f"Bearer {settings.x_bearer_token}"},timeout=12,max_bytes=2_000_000)
   for d in x_payload.get("data",[]):
    m=d.get("public_metrics",{});item_text=d.get("text","");score=sum(int(m.get(k,0)) for k in ("like_count","reply_count","retweet_count"))
    results.append({"platform":"x","text":item_text,"hook":extract_hook(item_text),"url":f"https://x.com/i/web/status/{d.get('id')}","score":score,"metrics":m,"published_at":d.get("created_at"),"source":"official_x_api_v2"})
   providers["x"]="ok"
  except Exception as exc:providers["x"]=f"error:{type(exc).__name__}"
 else:providers["x"]="not_configured"
 results.sort(key=lambda x:x["score"],reverse=True)
 for i,row in enumerate(results[:limit],1):row["rank"]=i
 return {"query":query,"results":results[:limit],"providers":providers,"warning":None if results else "No configured API returned results; no hooks or metrics were invented."}
