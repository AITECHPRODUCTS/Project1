from __future__ import annotations
import base64,hashlib,hmac,json,os,time
from typing import Any
import httpx
from bs4 import BeautifulSoup
from backend.config import get_settings
from backend.core.errors import IntegrationNotConfiguredError
from backend.services.url_safety import validate_public_http_url
def _b64(data:bytes)->str:return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
def _ghost_jwt(key:str)->str:
 try:kid,secret_hex=key.split(":",1);secret=bytes.fromhex(secret_hex)
 except ValueError as exc:raise ValueError("Ghost API key must be id:hex-secret") from exc
 now=int(time.time());header=_b64(json.dumps({"alg":"HS256","typ":"JWT","kid":kid},separators=(",",":")).encode());payload=_b64(json.dumps({"iat":now,"exp":now+300,"aud":"/admin/"},separators=(",",":")).encode());signing=f"{header}.{payload}".encode();return f"{header}.{payload}.{_b64(hmac.new(secret,signing,hashlib.sha256).digest())}"
def sanitize_article(markup:str,disclosure:str)->str:
 soup=BeautifulSoup(markup,"html.parser")
 for node in soup.find_all(["iframe","object","embed","form","input","button"]):node.decompose()
 for node in soup.find_all("script"):
  if node.get("type")!="application/ld+json":node.decompose()
 for node in soup.find_all(True):
  for key in list(node.attrs):
   if key.lower().startswith("on") or key.lower()=="srcdoc":del node.attrs[key]
  for key in ("src","href"):
   value=node.get(key)
   if isinstance(value,str) and value.strip().lower().startswith(("javascript:","data:text/html")):del node.attrs[key]
 p=soup.new_tag("p",attrs={"class":"affiliate-disclosure"});p.string=disclosure[:1200] if disclosure else "Disclosure: This article may contain affiliate links; a commission may be earned.";(soup.body or soup).append(p);return str(soup)
async def publish_article(*,provider:str,title:str,article_html:str,canonical_url:str,status:str="draft",tags:list[str]|None=None,disclosure:str="")->dict[str,Any]:
 s=get_settings()
 if provider not in {"wordpress","ghost"}:raise ValueError("provider must be wordpress or ghost")
 if status not in {"draft","publish"}:raise ValueError("status must be draft or publish")
 if status=="publish" and not s.cms_publish_execute:raise IntegrationNotConfiguredError("CMS_PUBLISH_EXECUTE=true required for actual publishing")
 if not title.strip():raise ValueError("title required")
 await validate_public_http_url(canonical_url);content=sanitize_article(article_html,disclosure);timeout=httpx.Timeout(25,connect=5)
 async with httpx.AsyncClient(timeout=timeout,follow_redirects=False) as c:
  if provider=="wordpress":
   base=os.getenv("WORDPRESS_SITE_URL","").rstrip("/");user=os.getenv("WORDPRESS_USERNAME","");password=os.getenv("WORDPRESS_APPLICATION_PASSWORD","")
   if not all((base,user,password)):raise IntegrationNotConfiguredError("Configure WordPress site URL, username and application password")
   await validate_public_http_url(base);credential=base64.b64encode(f"{user}:{password}".encode()).decode();response=await c.post(base+"/wp-json/wp/v2/posts",json={"title":title[:300],"content":content,"status":status},headers={"Authorization":f"Basic {credential}"});response.raise_for_status();data=response.json()
   return {"provider":provider,"status":data.get("status"),"remote_id":data.get("id"),"url":data.get("link"),"disclosure_injected":True}
  base=os.getenv("GHOST_SITE_URL","").rstrip("/");key=os.getenv("GHOST_ADMIN_API_KEY","")
  if not base or not key:raise IntegrationNotConfiguredError("Configure GHOST_SITE_URL and GHOST_ADMIN_API_KEY")
  await validate_public_http_url(base);payload={"posts":[{"title":title[:300],"html":content,"status":status,"tags":[{"name":t[:100]} for t in (tags or [])[:20]]}]};response=await c.post(base+"/ghost/api/admin/posts/?source=html",json=payload,headers={"Authorization":f"Ghost {_ghost_jwt(key)}","Accept-Version":"v5.0"});response.raise_for_status();data=response.json().get("posts",[{}])[0]
  return {"provider":provider,"status":data.get("status"),"remote_id":data.get("id"),"url":data.get("url"),"disclosure_injected":True}
