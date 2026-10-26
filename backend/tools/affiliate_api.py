from __future__ import annotations
import asyncio, json, re, time
from collections import OrderedDict
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import quote
import httpx
from backend.config import get_settings
from backend.services.url_safety import validate_public_http_url

@dataclass(frozen=True)
class AffiliateProgram:
    id: str; slug: str; name: str; url: str | None; description: str; reward_type: str | None
    reward_value: str | None; cookie_days: int | None; traffic_score: float | None; stars_count: float
    category: str | None; tags: tuple[str,...]; verified: bool | None; raw: dict[str, Any]
    def as_dict(self) -> dict[str, Any]:
        data=asdict(self); data["tags"]=list(self.tags); return data

class TTLCache:
    def __init__(self, ttl_seconds: int = 300, max_entries: int = 200):
        self.ttl=ttl_seconds; self.max_entries=max_entries; self.items: OrderedDict[str,tuple[float,Any]]=OrderedDict(); self.lock=asyncio.Lock()
    async def get(self,key: str) -> Any | None:
        async with self.lock:
            item=self.items.get(key)
            if not item: return None
            ts,value=item
            if time.monotonic()-ts>=self.ttl: self.items.pop(key,None); return None
            self.items.move_to_end(key); return json.loads(json.dumps(value))
    async def set(self,key: str,value: Any) -> None:
        async with self.lock:
            self.items[key]=(time.monotonic(),json.loads(json.dumps(value))); self.items.move_to_end(key)
            while len(self.items)>self.max_entries: self.items.popitem(last=False)
    async def clear(self) -> None:
        async with self.lock: self.items.clear()
    async def stats(self) -> dict[str,Any]:
        async with self.lock:
            now=time.monotonic(); expired=[k for k,(t,_) in self.items.items() if now-t>=self.ttl]
            for key in expired:self.items.pop(key,None)
            ages=[now-t for t,_ in self.items.values()]
            return {"entries":len(self.items),"max_entries":self.max_entries,"oldest_age_seconds":round(max(ages,default=0),1)}

class OpenAffiliateClient:
    MAX_BYTES=5*1024*1024
    def __init__(self,base_url: str | None=None,timeout: float=10.0,cache: TTLCache | None=None):
        self.base=(base_url or get_settings().openaffiliate_base_url).rstrip("/"); self.timeout=httpx.Timeout(timeout,connect=4); self.cache=cache or TTLCache()
    async def _get(self,path: str,params: dict[str,Any] | None=None) -> Any:
        url=self.base+path
        key=json.dumps({"url":url,"params":params or {}},sort_keys=True)
        cached=await self.cache.get(key)
        if cached is not None:return cached
        # OPENAFFILIATE_BASE_URL is operator configuration, not proof that its
        # destination is public. Reject private/loopback/link-local targets
        # before opening a network client; redirects are disabled below.
        await validate_public_http_url(url)
        async with httpx.AsyncClient(timeout=self.timeout,follow_redirects=False,headers={"Accept":"application/json","User-Agent":"AffiliateOS/0.1"}) as client:
            async with client.stream("GET",url,params=params) as response:
                response.raise_for_status(); length=int(response.headers.get("content-length","0") or 0)
                if length>self.MAX_BYTES: raise ValueError("OpenAffiliate response exceeded 5 MB limit")
                data=bytearray()
                async for part in response.aiter_bytes():
                    data.extend(part)
                    if len(data)>self.MAX_BYTES: raise ValueError("OpenAffiliate response exceeded 5 MB limit")
                try: payload=json.loads(data)
                except json.JSONDecodeError as exc: raise ValueError("OpenAffiliate returned invalid JSON") from exc
        await self.cache.set(key,payload); return payload
    @staticmethod
    def adapt(row: dict[str,Any]) -> AffiliateProgram:
        commission=row.get("commission") if isinstance(row.get("commission"),dict) else {}
        reward_type=commission.get("type",row.get("reward_type",row.get("Reward Type")))
        reward_value=commission.get("rate",row.get("reward_value",row.get("Reward")))
        cookie=row.get("cookieDays",row.get("cookie_days",row.get("Cookie Days")))
        traffic=row.get("traffic_score",row.get("Traffic Score")); stars=row.get("stars",row.get("stars_count",0)) or 0
        try:
            if isinstance(cookie,str): cookie_match=re.search(r"\d+",cookie.replace(",","")); cookie=int(cookie_match.group()) if cookie_match else None
            else: cookie=int(cookie) if cookie is not None else None
        except (ValueError,TypeError): cookie=None
        try:
            if isinstance(traffic,str): traffic_match=re.search(r"-?\d+(?:\.\d+)?",traffic.replace(",","")); traffic=float(traffic_match.group()) if traffic_match else None
            else: traffic=float(traffic) if traffic is not None else None
        except (ValueError,TypeError): traffic=None
        try: stars=float(stars)
        except (ValueError,TypeError): stars=0.0
        slug=str(row.get("slug") or row.get("id") or "")
        tags=row.get("tags") if isinstance(row.get("tags"),list) else []
        return AffiliateProgram(slug,slug,str(row.get("name") or "Unnamed program"),row.get("url"),str(row.get("description") or row.get("shortDescription") or ""),
            str(reward_type) if reward_type is not None else None,str(reward_value) if reward_value is not None else None,cookie,traffic,stars,
            row.get("category"),tuple(str(t) for t in tags),row.get("verified") if isinstance(row.get("verified"),bool) else None,row)
    async def fetch_programs(self,*,q: str | None=None,category: str | None=None,limit: int=50) -> dict[str,Any]:
        if not 1<=limit<=200: raise ValueError("limit must be between 1 and 200")
        params={"limit":limit}
        if q:params["q"]=q
        if category:params["category"]=category
        payload=await self._get("/programs",params)
        if isinstance(payload,list):rows=payload; total=len(rows)
        elif isinstance(payload,dict):rows=payload.get("programs",payload.get("data",[])); total=int(payload.get("total",payload.get("count",len(rows or []))) or 0)
        else:raise ValueError("Unexpected OpenAffiliate response schema")
        if not isinstance(rows,list):raise ValueError("OpenAffiliate response has no program array")
        programs=[self.adapt(row).as_dict() for row in rows if isinstance(row,dict)]
        return {"data":programs[:limit],"count":len(programs[:limit]),"registry_total":total,
            "note":"traffic_score is null unless actually supplied by upstream data"}
    async def fetch_program(self,slug: str) -> dict[str,Any] | None:
        if not slug or len(slug)>200:raise ValueError("slug must be 1..200 characters")
        try:payload=await self._get("/programs/"+quote(slug,safe=""))
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code==404:return None
            raise
        if not isinstance(payload,dict):raise ValueError("Unexpected program response")
        return self.adapt(payload).as_dict()

client=OpenAffiliateClient()
