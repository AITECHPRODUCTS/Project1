from __future__ import annotations

import hashlib
import html
import ipaddress
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def validate_bio_link_url(value: str) -> str:
    """Validate a browser destination without making a server-side network request."""
    raw = str(value or "").strip()
    try:
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower().rstrip(".")
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("Link destinations must be valid absolute HTTP(S) URLs") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not host:
        raise ValueError("Link destinations must be absolute HTTP(S) URLs")
    if parsed.username or parsed.password:
        raise ValueError("Link destinations must not contain credentials")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(
        (".localhost", ".local", ".internal", ".test", ".home", ".lan", ".corp")
    ):
        raise ValueError("Local/private hostnames are not valid link destinations")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Private, loopback, link-local or reserved IP destinations are not valid")
    return raw


def _add_tracking_parameters(url: str, *, page_id: str, index: int) -> str:
    parts = urlsplit(url)
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    present = {key.casefold() for key, _ in pairs}
    for key, value in (
        ("utm_source", "omni_affiliate_os"),
        ("utm_medium", "bio_link"),
        ("utm_content", f"{page_id}.{index + 1}"),
    ):
        if key not in present:
            pairs.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs, doseq=True), parts.fragment))


def build_bio_link_page(payload: dict, *, page_id: str) -> dict:
    """Render a safe static link page; no scripts, embeds, forms, or remote fetches are emitted."""
    title = str(payload["title"]).strip()
    headline = str(payload["headline"]).strip()
    subheadline = str(payload.get("subheadline") or "").strip()
    disclosure = str(payload.get("affiliate_disclosure") or "").strip()
    footer_note = str(payload.get("footer_note") or "").strip()
    links = list(payload.get("links") or [])
    affiliate_count = sum(1 for item in links if item.get("is_affiliate") is True)
    if affiliate_count and len(disclosure) < 10:
        raise ValueError("Affiliate links require a clear disclosure of at least 10 characters")
    if not links or len(links) > 50:
        raise ValueError("A bio-link page must have between 1 and 50 links")

    blocks: list[str] = []
    tracked_urls: list[str] = []
    for index, item in enumerate(links):
        label = str(item["label"]).strip()
        destination = validate_bio_link_url(item["url"])
        tracked = _add_tracking_parameters(destination, page_id=page_id, index=index)
        tracked_urls.append(tracked)
        description = str(item.get("description") or "").strip()
        is_affiliate = item.get("is_affiliate") is True
        rel = "sponsored nofollow noopener noreferrer" if is_affiliate else "nofollow noopener noreferrer"
        label_html = html.escape(label, quote=True)
        description_html = f'<span class="description">{html.escape(description, quote=True)}</span>' if description else ""
        blocks.append(
            f'<li><a class="link-card" href="{html.escape(tracked, quote=True)}" '
            f'target="_blank" rel="{rel}"><span class="link-title">{label_html}</span>'
            f'{description_html}<span class="link-arrow" aria-hidden="true">↗</span></a></li>'
        )

    disclosure_block = (
        f'<aside class="disclosure" aria-label="Affiliate disclosure">{html.escape(disclosure, quote=True)}</aside>'
        if disclosure else ""
    )
    subheadline_block = f"<p class=\"subtitle\">{html.escape(subheadline, quote=True)}</p>" if subheadline else ""
    footer_block = f"<footer>{html.escape(footer_note, quote=True)}</footer>" if footer_note else ""
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{html.escape(subheadline or headline, quote=True)[:300]}">
<title>{html.escape(title, quote=True)}</title>
<style>
:root{{color-scheme:light;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f4f6fb;color:#182033}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;padding:2rem 1rem;background:linear-gradient(180deg,#f8faff,#edf1f8)}}
main{{width:min(100%,38rem);margin:0 auto}}.brand{{display:inline-block;margin-bottom:1.1rem;color:#4f46e5;font-weight:800;letter-spacing:.12em;text-transform:uppercase;font-size:.72rem}}
h1{{font-size:clamp(1.8rem,6vw,2.8rem);line-height:1.1;letter-spacing:-.04em;margin:.2rem 0 .8rem}}
.subtitle{{margin:0 0 1.8rem;color:#667085;line-height:1.65}}ul{{padding:0;margin:0;list-style:none;display:grid;gap:.8rem}}
.link-card{{display:flex;align-items:center;gap:1rem;justify-content:space-between;padding:1.1rem 1.2rem;background:white;border:1px solid #e2e8f0;border-radius:1rem;color:#182033;text-decoration:none;box-shadow:0 8px 24px #2434520b;transition:transform .15s,border-color .15s}}
.link-card:hover,.link-card:focus-visible{{border-color:#818cf8;transform:translateY(-1px);outline:3px solid #c7d2fe;outline-offset:2px}}
.link-title{{display:block;font-weight:750}}.description{{display:block;margin-top:.3rem;font-size:.9rem;font-weight:400;color:#667085;line-height:1.45}}.link-arrow{{font-size:1.1rem;color:#6366f1}}
.disclosure{{margin-top:1.2rem;padding:1rem;border-radius:.8rem;border:1px solid #e0e7ff;background:#eef2ff;color:#3730a3;font-size:.86rem;line-height:1.55}}
footer{{margin-top:1.7rem;text-align:center;color:#667085;font-size:.8rem;line-height:1.55}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{transition:none!important}}}}
</style>
</head>
<body><main><span class="brand">Curated links</span><h1>{html.escape(headline, quote=True)}</h1>{subheadline_block}
<ul aria-label="Useful links">{''.join(blocks)}</ul>{disclosure_block}{footer_block}
</main></body></html>"""
    checksum = hashlib.sha256(document.encode("utf-8")).hexdigest()
    return {
        "html": document,
        "sha256": checksum,
        "link_count": len(links),
        "affiliate_link_count": affiliate_count,
        "tracked_urls": tracked_urls,
        "external_scripts": False,
        "user_markup_embedded": False,
        "server_side_link_fetches": 0,
    }
