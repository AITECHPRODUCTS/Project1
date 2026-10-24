from __future__ import annotations
import asyncio,ipaddress,socket
from urllib.parse import urlparse
import httpx
async def validate_public_http_url(url:str)->str:
 parsed=urlparse(url)
 if parsed.scheme not in {"http","https"} or not parsed.hostname:raise ValueError("Only absolute HTTP(S) URLs are allowed")
 if parsed.username or parsed.password:raise ValueError("URLs containing credentials are not allowed")
 host=parsed.hostname.lower().rstrip(".")
 if host in {"localhost","localhost.localdomain"} or host.endswith((".local",".internal",".test")):raise ValueError("Local/private hostname blocked")
 answers=await asyncio.to_thread(socket.getaddrinfo,host,parsed.port or (443 if parsed.scheme=="https" else 80),0,socket.SOCK_STREAM)
 if not answers:raise ValueError("Hostname has no addresses")
 for answer in answers:
  ip=ipaddress.ip_address(answer[4][0].split("%",1)[0])
  if not ip.is_global:raise ValueError("Private, loopback, link-local, multicast or reserved destinations are blocked")
 return url
async def fetch_public_page(url:str,*,max_bytes:int=2000000,timeout:float=12.0)->tuple[str,str,int]:
 await validate_public_http_url(url)
 async with httpx.AsyncClient(timeout=httpx.Timeout(timeout,connect=4),follow_redirects=False,headers={"User-Agent":"AffiliateOSResearch/0.1","Accept":"text/html,text/plain,application/xhtml+xml"}) as client:
  async with client.stream("GET",url) as response:
   if 300<=response.status_code<400:raise ValueError("Redirect not followed; validate the redirected URL separately")
   response.raise_for_status();content_type=response.headers.get("content-type","")
   if not any(m in content_type.lower() for m in ("text/html","text/plain","application/xhtml+xml")):raise ValueError(f"Unsupported content type: {content_type}")
   if int(response.headers.get("content-length","0") or 0)>max_bytes:raise ValueError("Response exceeds byte limit")
   chunks=[];size=0
   async for chunk in response.aiter_bytes():
    size+=len(chunk)
    if size>max_bytes:raise ValueError("Response exceeds byte limit")
    chunks.append(chunk)
   return b"".join(chunks).decode("utf-8",errors="replace"),content_type,response.status_code
