from __future__ import annotations
import asyncio, json, math, re, time
from collections import OrderedDict
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import quote
import httpx
from backend.config import get_settings
from backend.services.url_safety import open_public_http_response, read_limited_response

 
MAX_COOKIE_DAYS = 2_147_483_647
_NUMBER_TEXT = re.compile(r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?(?:[eE][+-]?\d+)?\Z")
_COOKIE_DAYS_TEXT = re.compile(r"(?:(?:\d{1,3}(?:,\d{3})+)|\d+)\s*(?:days?|d)?\Z", re.IGNORECASE)


def _non_negative_finite_float(value: Any) -> float | None:
    """Parse a numeric value without extracting guessed numbers from provider prose."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        candidate = value.strip()
        if len(candidate) > 64 or not _NUMBER_TEXT.fullmatch(candidate):
            return None
        candidate = candidate.replace(",", "")
    elif isinstance(value, (int, float)):
        candidate = value
    else:
        return None
    try:
        number = float(candidate)
    except (ValueError, TypeError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _non_negative_cookie_days(value: Any) -> int | None:
    """Parse cookie duration only as an exact non-negative integer supported by SQL Integer."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        days = value
    elif isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            return None
        days = int(value)
    elif isinstance(value, str):
        candidate = value.strip()
        if len(candidate) > 64 or not _COOKIE_DAYS_TEXT.fullmatch(candidate):
            return None
        candidate = re.sub(r"\s*(?:days?|d)\Z", "", candidate, flags=re.IGNORECASE)
        days = int(candidate.replace(",", "").strip())
    else:
        return None
    if days < 0 or days > MAX_COOKIE_DAYS:
        return None
    return days

@dataclass(frozen=True)
class AffiliateProgram:
    id: str; slug: str; name: str; url: str | None; description: str; reward_type: str | None
    reward_value: str | None; cookie_days: int | None; traffic_score: float | None; stars_count: float | None
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
        self.base=(base_url or get_settings().openaffiliate_base_url).rstrip("/"); self.timeout_seconds=timeout; self.cache=cache or TTLCache()
    async def _get(self,path: str,params: dict[str,Any] | None=None) -> Any:
        url=self.base+path
        key=json.dumps({"url":url,"params":params or {}},sort_keys=True)
        cached=await self.cache.get(key)
        if cached is not None:return cached
        # Configured provider URLs are also untrusted. The shared transport pins
        # the connection to a vetted public IP and disables redirects/proxy env.
        async with open_public_http_response(
            url,
            method="GET",
            params=params,
            headers={"Accept":"application/json","User-Agent":"AffiliateOS/0.1"},
            timeout=self.timeout_seconds,
        ) as response:
            if 300 <= response.status_code < 400:
                raise ValueError("OpenAffiliate redirects are not followed")
            response.raise_for_status()
            content_type=response.headers.get("content-type","").split(";",1)[0].strip().lower()
            if content_type and content_type not in {"application/json","application/problem+json"}:
                raise ValueError(f"Unsupported OpenAffiliate content type: {content_type}")
            data=await read_limited_response(response,max_bytes=self.MAX_BYTES)
            try: payload=json.loads(data)
            except json.JSONDecodeError as exc: raise ValueError("OpenAffiliate returned invalid JSON") from exc
        await self.cache.set(key,payload); return payload
    @staticmethod
    def adapt(row: dict[str,Any]) -> AffiliateProgram:
        commission=row.get("commission") if isinstance(row.get("commission"),dict) else {}
        reward_type=commission.get("type",row.get("reward_type",row.get("Reward Type")))
        reward_value=commission.get("rate",row.get("reward_value",row.get("Reward")))
        cookie_raw=row.get("cookieDays")
        if cookie_raw is None: cookie_raw=row.get("cookie_days",row.get("Cookie Days"))
        traffic_raw=row.get("traffic_score")
        if traffic_raw is None: traffic_raw=row.get("Traffic Score")
        stars_raw=row.get("stars")
        if stars_raw is None: stars_raw=row.get("stars_count")
        cookie=_non_negative_cookie_days(cookie_raw)
        traffic=_non_negative_finite_float(traffic_raw)
        stars=_non_negative_finite_float(stars_raw)
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
