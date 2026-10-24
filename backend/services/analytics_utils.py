from __future__ import annotations
import hashlib, random
from typing import Any
from urllib.parse import parse_qs, urlparse

def conversion_tracker(url_or_query: str) -> dict[str,Any]:
    parsed=urlparse(url_or_query if "://" in url_or_query else "https://local.invalid/?"+url_or_query.lstrip("?")); params=parse_qs(parsed.query)
    def first(key: str):
        vals=params.get(key); return vals[0][:500] if vals else None
    return {"utm_source":first("utm_source"),"utm_medium":first("utm_medium"),"utm_campaign":first("utm_campaign"),"utm_term":first("utm_term"),"utm_content":first("utm_content"),"click_id":first("click_id") or first("subid") or first("aff_sub"),"gclid":first("gclid"),"fbclid":first("fbclid"),"landing_path":parsed.path if parsed.hostname!="local.invalid" else None}

def ab_test_generator(headline_a: str, headline_b: str, *, visitor_id: str, experiment_key: str, conversions_a: int=0,impressions_a: int=0,conversions_b: int=0,impressions_b: int=0) -> dict[str,Any]:
    if not headline_a.strip() or not headline_b.strip() or headline_a==headline_b: raise ValueError("Two different headlines required")
    for name,c,i in [("A",conversions_a,impressions_a),("B",conversions_b,impressions_b)]:
        if min(c,i)<0 or c>i:raise ValueError(f"Variant {name} requires 0 <= conversions <= impressions")
    if impressions_a+impressions_b>=100 and impressions_a>=30 and impressions_b>=30:
        sa=random.betavariate(conversions_a+1,impressions_a-conversions_a+1); sb=random.betavariate(conversions_b+1,impressions_b-conversions_b+1); variant="A" if sa>=sb else "B"; method="thompson_sampling"
    else:variant="A" if int.from_bytes(hashlib.sha256(f"{experiment_key}:{visitor_id}".encode()).digest()[:4],"big")%2==0 else "B"; method="stable_hash_split"
    return {"variant":variant,"headline":headline_a if variant=="A" else headline_b,"assignment_method":method,"stats":{"A":{"impressions":impressions_a,"conversions":conversions_a,"rate":conversions_a/impressions_a if impressions_a else None},"B":{"impressions":impressions_b,"conversions":conversions_b,"rate":conversions_b/impressions_b if impressions_b else None}},"warning":"Allocation heuristic, not proof of statistical significance."}
