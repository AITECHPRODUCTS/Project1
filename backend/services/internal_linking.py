from __future__ import annotations

import asyncio
import re
from collections import Counter
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunsplit

from bs4 import BeautifulSoup

from backend.services.url_safety import fetch_public_page


_STOP_WORDS = frozenset(
    "a an and are as at be been by can for from how in into is it its of on or our "
    "the their them these this to was we with your you".split()
)
_TRACKING_PARAMS = frozenset({"utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term", "gclid", "fbclid"})


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]{2,}", value.casefold())
        if token not in _STOP_WORDS
    }


def _origin(url: str) -> tuple[str, str, int]:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower().rstrip(".")
    port = parsed.port or (443 if scheme == "https" else 80)
    return scheme, host, port


def _page_key(url: str) -> str:
    parsed = urlparse(url)
    scheme, host, port = _origin(url)
    default_port = 443 if scheme == "https" else 80
    authority = host if port == default_port else f"{host}:{port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMS
    ]
    query = urlencode(sorted(query_items))
    return urlunsplit((scheme, authority, path, query, ""))


def _visible_text(soup: BeautifulSoup) -> str:
    content_root = soup.find("main") or soup.find("article") or soup.body or soup
    clean = BeautifulSoup(str(content_root), "html.parser")
    for tag in clean(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    return re.sub(r"\s+", " ", clean.get_text(" ", strip=True)).strip()


async def _analyze_page(url: str, semaphore: asyncio.Semaphore) -> dict[str, Any]:
    async with semaphore:
        try:
            html, content_type, status = await fetch_public_page(
                url,
                max_bytes=1_000_000,
                timeout=10.0,
            )
            if "text/html" not in content_type.lower() and "application/xhtml+xml" not in content_type.lower():
                raise ValueError("Supplied page is not HTML or XHTML")
            soup = BeautifulSoup(html, "html.parser")
            title = re.sub(r"\s+", " ", soup.title.get_text(" ", strip=True)).strip() if soup.title else ""
            headings = [
                re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()
                for tag in soup.find_all(re.compile(r"^h[1-3]$"))[:12]
            ]
            page_text = _visible_text(soup)
            if not page_text:
                raise ValueError("Supplied page has no visible text content")
            topic_tokens = _tokens(" ".join([title, *headings]))
            if len(topic_tokens) < 2:
                topic_tokens = _tokens(page_text[:1200])
            if len(topic_tokens) < 2:
                raise ValueError("Page has too few meaningful words for a topic comparison")

            source_origin = _origin(url)
            existing_internal_keys: set[str] = set()
            for anchor in soup.find_all("a", href=True)[:2000]:
                href = str(anchor.get("href", "")).strip()
                if not href or href.startswith(("mailto:", "tel:", "javascript:")):
                    continue
                resolved = urljoin(url, href)
                try:
                    if _origin(resolved) == source_origin:
                        key = _page_key(resolved)
                        if key != _page_key(url):
                            existing_internal_keys.add(key)
                except ValueError:
                    continue

            return {
                "url": url,
                "status": "analyzed",
                "http_status": status,
                "title": title[:300],
                "headings": headings[:8],
                "word_count": len(re.findall(r"\b[\w'-]+\b", page_text)),
                "topic_tokens": topic_tokens,
                "visible_tokens": _tokens(page_text[:80000]),
                "existing_internal_keys": existing_internal_keys,
                "existing_internal_link_count": len(existing_internal_keys),
                "page_key": _page_key(url),
                "error_type": None,
            }
        except Exception as exc:
            return {
                "url": url,
                "status": "failed",
                "error_type": type(exc).__name__,
            }


async def recommend_internal_links(
    *,
    urls: list[str],
    max_suggestions_per_page: int = 5,
) -> dict[str, Any]:
    """Suggest missing topical links across a user-supplied same-origin page set.

    The service only fetches the supplied URLs, never follows redirects or discovered
    links, never modifies a CMS, and reports heuristic relevance rather than ranking impact.
    """
    unique_urls: list[str] = []
    seen_keys: set[str] = set()
    for url in urls:
        key = _page_key(url)
        if key not in seen_keys:
            seen_keys.add(key)
            unique_urls.append(url)
    if len(unique_urls) < 2:
        raise ValueError("Supply at least two distinct public pages from the same origin")
    origins = {_origin(url) for url in unique_urls}
    if len(origins) != 1:
        raise ValueError("All supplied pages must share the same public HTTP(S) origin")
    if not 1 <= max_suggestions_per_page <= 10:
        raise ValueError("max_suggestions_per_page must be between 1 and 10")

    semaphore = asyncio.Semaphore(4)
    pages = await asyncio.gather(*[_analyze_page(url, semaphore) for url in unique_urls])
    successful = [page for page in pages if page["status"] == "analyzed"]
    if len(successful) < 2:
        raise ValueError("At least two supplied pages must be safely retrievable HTML pages")

    recommendations: list[dict[str, Any]] = []
    for source in successful:
        candidates: list[dict[str, Any]] = []
        for target in successful:
            if source["page_key"] == target["page_key"]:
                continue
            if target["page_key"] in source["existing_internal_keys"]:
                continue
            topic_tokens = target["topic_tokens"]
            overlap = topic_tokens & source["visible_tokens"]
            if len(overlap) < 2:
                continue
            topic_coverage = len(overlap) / max(1, len(topic_tokens))
            shared_term_strength = min(1.0, len(overlap) / 4.0)
            score = round(100 * (0.72 * topic_coverage + 0.28 * shared_term_strength))
            if score < 35:
                continue
            anchor_text = target["headings"][0] if target["headings"] else target["title"]
            if not anchor_text:
                continue
            candidates.append({
                "source_url": source["url"],
                "destination_url": target["url"],
                "suggested_anchor_text": anchor_text[:120],
                "relevance_score": score,
                "matched_terms": sorted(overlap)[:8],
                "reason": (
                    "The visible source text shares meaningful topic terms with the destination, "
                    "and no same-origin link to that destination was found in the source markup."
                ),
                "requires_human_review": True,
                "link_inserted": False,
            })
        candidates.sort(key=lambda row: (-row["relevance_score"], row["destination_url"]))
        recommendations.extend(candidates[:max_suggestions_per_page])

    recommendations.sort(key=lambda row: (-row["relevance_score"], row["source_url"], row["destination_url"]))
    page_summaries = [
        {
            "url": page["url"],
            "status": page["status"],
            "http_status": page.get("http_status"),
            "title": page.get("title"),
            "headings": page.get("headings", []),
            "word_count": page.get("word_count"),
            "existing_internal_link_count": page.get("existing_internal_link_count", 0),
            "error_type": page.get("error_type"),
        }
        for page in pages
    ]
    return {
        "origin": next(iter(origins)),
        "requested_page_count": len(unique_urls),
        "analyzed_page_count": len(successful),
        "failed_page_count": len(unique_urls) - len(successful),
        "pages": page_summaries,
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
        "scoring_method": "deterministic_topic_overlap_heuristic_v1",
        "score_definition": (
            "Heuristic topic overlap between destination title/headings and source visible text; "
            "it is not a search-ranking or traffic forecast."
        ),
        "read_only": True,
        "link_inserted": False,
        "automatic_crawl_enabled": False,
        "discovered_links_followed": 0,
        "requires_human_review": True,
        "note": (
            "Only supplied public pages were fetched. Redirects and discovered links were not followed. "
            "Verify context, link usefulness, existing navigation and accessibility before editing the site."
        ),
    }
