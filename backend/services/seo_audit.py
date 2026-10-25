from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from backend.services.url_safety import fetch_public_page


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _tag_text(tag: Any) -> str:
    return _clean_text(tag.get_text(" ", strip=True)) if tag else ""


def _meta_content(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find("meta", attrs={"name": re.compile(rf"^{re.escape(name)}$", re.IGNORECASE)})
    return _clean_text(tag.get("content", "")) if tag else ""


def _finding(
    check_id: str,
    status: str,
    severity: str,
    summary: str,
    recommendation: str,
) -> dict[str, str]:
    return {
        "id": check_id,
        "status": status,
        "severity": severity,
        "summary": summary,
        "recommendation": recommendation,
    }


async def audit_public_page(url: str) -> dict[str, Any]:
    """Run a read-only, deterministic technical/page-content checklist on one public URL.

    This is a page-level hygiene audit, not a search ranking, traffic, conversion,
    or revenue prediction. It does not crawl links or follow redirects.
    """
    html, content_type, http_status = await fetch_public_page(url, max_bytes=2_000_000, timeout=12.0)
    if "text/html" not in content_type.lower() and "application/xhtml+xml" not in content_type.lower():
        raise ValueError("SEO audit requires a public HTML or XHTML page")

    soup = BeautifulSoup(html, "html.parser")
    page_title = _tag_text(soup.title)
    title_length = len(page_title)
    description = _meta_content(soup, "description")
    description_length = len(description)
    html_tag = soup.find("html")
    language = _clean_text(html_tag.get("lang", "")) if html_tag else ""
    viewport = bool(soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.IGNORECASE)}))
    robots_content = _meta_content(soup, "robots")
    googlebot_content = _meta_content(soup, "googlebot")
    indexing_directives = " ".join((robots_content, googlebot_content)).lower().split()
    indexing_blocked = "noindex" in indexing_directives

    canonical_url = ""
    canonical_invalid = False
    for link in soup.find_all("link", href=True):
        rel = link.get("rel", [])
        rel_values = {str(item).lower() for item in (rel if isinstance(rel, list) else str(rel).split())}
        if "canonical" in rel_values:
            candidate = urljoin(url, str(link.get("href", "")).strip())
            parsed_candidate = urlparse(candidate)
            if parsed_candidate.scheme in {"http", "https"} and parsed_candidate.hostname:
                canonical_url = candidate
            else:
                canonical_invalid = True
            break

    headings = []
    for tag in soup.find_all(re.compile(r"^h[1-6]$"))[:100]:
        headings.append({"level": int(tag.name[1]), "text": _tag_text(tag)[:300]})
    h1_count = sum(1 for item in headings if item["level"] == 1)
    heading_order_issue = False
    prior_level = 0
    for item in headings:
        level = item["level"]
        if prior_level and level > prior_level + 1:
            heading_order_issue = True
            break
        if prior_level == 0 and level > 1:
            heading_order_issue = True
            break
        prior_level = level

    images = soup.find_all("img")
    images_missing_alt = sum(
        1 for image in images
        if image.get("alt") is None or not _clean_text(image.get("alt", ""))
    )

    requested_host = (urlparse(url).hostname or "").lower().rstrip(".")
    internal_links = 0
    external_links = 0
    for anchor in soup.find_all("a", href=True)[:5000]:
        href = str(anchor.get("href", "")).strip()
        if not href or href.startswith("#"):
            continue
        target = urlparse(urljoin(url, href))
        if target.scheme not in {"http", "https"} or not target.hostname:
            continue
        if target.hostname.lower().rstrip(".") == requested_host:
            internal_links += 1
        else:
            external_links += 1

    content_root = soup.find("main") or soup.find("article") or soup.body or soup
    content_copy = BeautifulSoup(str(content_root), "html.parser")
    for tag in content_copy(["script", "style", "noscript", "template"]):
        tag.decompose()
    word_count = len(re.findall(r"\b[\w’'-]+\b", content_copy.get_text(" ", strip=True)))

    checks: list[dict[str, str]] = []
    if not page_title:
        checks.append(_finding("title_present", "failed", "high", "The page has no non-empty document title.", "Add a unique, descriptive HTML title that identifies the page."))
    else:
        checks.append(_finding("title_present", "passed", "info", f"A document title is present ({title_length} characters).", "Keep the title specific to the page and avoid repetitive keyword stuffing."))
        if 30 <= title_length <= 60:
            checks.append(_finding("title_length", "passed", "info", f"Title length is {title_length} characters.", "Keep monitoring title clarity when content changes."))
        else:
            checks.append(_finding("title_length", "warning", "medium", f"Title length is {title_length} characters; a 30–60 character range is used here as a heuristic.", "Review whether the title communicates the page topic clearly in a compact form; this range is not a ranking guarantee."))

    if not description:
        checks.append(_finding("meta_description", "failed", "medium", "No meta description was found.", "Add a unique, accurate description of the page."))
    elif 70 <= description_length <= 160:
        checks.append(_finding("meta_description", "passed", "info", f"A meta description is present ({description_length} characters).", "Keep the description accurate and aligned with the visible page."))
    else:
        checks.append(_finding("meta_description", "warning", "low", f"Meta description length is {description_length} characters; 70–160 is used as a review heuristic.", "Review clarity and truncation risk; search engines may choose other snippets."))

    if h1_count == 1:
        checks.append(_finding("h1_count", "passed", "info", "Exactly one H1 heading was found.", "Ensure the H1 names the main page topic."))
    elif h1_count == 0:
        checks.append(_finding("h1_count", "failed", "medium", "No H1 heading was found.", "Add a clear primary heading for the page content."))
    else:
        checks.append(_finding("h1_count", "warning", "low", f"{h1_count} H1 headings were found.", "Review the heading structure so the page has a clear primary content heading."))

    if language:
        checks.append(_finding("html_language", "passed", "info", f"HTML language is set to '{language}'.", "Keep the language declaration accurate for the main content."))
    else:
        checks.append(_finding("html_language", "warning", "low", "The HTML element has no language declaration.", "Set an appropriate lang attribute on the HTML element."))

    if viewport:
        checks.append(_finding("viewport", "passed", "info", "A viewport meta tag is present.", "Verify responsive layout at common mobile and desktop widths."))
    else:
        checks.append(_finding("viewport", "warning", "medium", "No viewport meta tag was found.", "Set a responsive viewport for mobile rendering."))

    if canonical_url:
        checks.append(_finding("canonical", "passed", "info", "A valid HTTP(S) canonical URL was found.", "Confirm the canonical identifies the intended preferred page."))
    elif canonical_invalid:
        checks.append(_finding("canonical", "failed", "medium", "The canonical link does not resolve to an HTTP(S) URL.", "Use a valid absolute or relative HTTP(S) canonical URL."))
    else:
        checks.append(_finding("canonical", "warning", "low", "No canonical link was found.", "Review whether this page needs an explicit canonical URL, especially if similar URLs exist."))

    if indexing_blocked:
        checks.append(_finding("indexing_directives", "warning", "high", "A robots directive contains noindex.", "Confirm this is intentional; remove noindex only when the page should be eligible for indexing."))
    else:
        checks.append(_finding("indexing_directives", "passed", "info", "No noindex directive was found in robots/googlebot metadata.", "Check response headers and robots.txt separately; this page-level audit does not inspect them."))

    if not images:
        checks.append(_finding("image_alt_text", "not_applicable", "info", "No images were found in the page markup.", "Recheck this result if images are injected client-side."))
    elif images_missing_alt == 0:
        checks.append(_finding("image_alt_text", "passed", "info", f"All {len(images)} image(s) have non-empty alt attributes.", "Use meaningful alt text for informative images and empty alt text for decorative images."))
    else:
        checks.append(_finding("image_alt_text", "warning", "medium", f"{images_missing_alt} of {len(images)} image(s) have missing or blank alt text.", "Provide useful alt text for informative images; use alt='' for decorative images."))

    if heading_order_issue:
        checks.append(_finding("heading_outline", "warning", "low", "The heading outline appears to skip one or more levels.", "Review heading hierarchy so subsections are nested consistently."))
    else:
        checks.append(_finding("heading_outline", "passed", "info", "No obvious skipped level was found in the sampled heading outline.", "Verify heading semantics as part of accessibility testing."))

    if word_count < 300:
        checks.append(_finding("main_content_length", "warning", "low", f"Only {word_count} words were found in the selected main/article/body content.", "Review whether the page fully answers its user intent; there is no universal minimum word count for useful content."))
    else:
        checks.append(_finding("main_content_length", "passed", "info", f"{word_count} words were found in the selected main/article/body content.", "Assess usefulness, originality and evidence; length alone is not a content-quality measure."))

    if internal_links > 0:
        checks.append(_finding("internal_links", "passed", "info", f"{internal_links} same-host internal link(s) were found.", "Make internal links useful and descriptive for visitors."))
    else:
        checks.append(_finding("internal_links", "warning", "low", "No same-host internal links were found.", "Consider relevant internal navigation where it helps visitors discover related pages."))

    applicable = [item for item in checks if item["status"] != "not_applicable"]
    checklist_score = round(100 * sum(item["status"] == "passed" for item in applicable) / max(1, len(applicable)))
    issues = [item for item in checks if item["status"] in {"failed", "warning"}]

    return {
        "url": url,
        "http_status": http_status,
        "content_type": content_type,
        "title": page_title,
        "title_length": title_length,
        "meta_description": description,
        "meta_description_length": description_length,
        "h1_count": h1_count,
        "headings": headings,
        "html_language": language or None,
        "viewport_present": viewport,
        "canonical_url": canonical_url or None,
        "robots_directives": {"robots": robots_content or None, "googlebot": googlebot_content or None},
        "indexing_blocked": indexing_blocked,
        "image_count": len(images),
        "images_missing_alt": images_missing_alt,
        "internal_link_count": internal_links,
        "external_link_count": external_links,
        "main_content_word_count": word_count,
        "checklist_score": checklist_score,
        "score_definition": "Rule-based page hygiene checklist only; not a search ranking, traffic, conversion or revenue prediction.",
        "checks": checks,
        "issues": issues,
        "read_only": True,
        "requires_review": True,
        "links_crawled": 0,
        "note": "Single-page analysis only. No links are crawled, no redirects are followed, and response headers/robots.txt/Search Console are not assessed.",
    }
