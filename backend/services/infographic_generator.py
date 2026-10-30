from __future__ import annotations

import math
import textwrap
from typing import Any
from xml.sax.saxutils import escape

WIDTH = 1080
HEIGHT = 1350
_CARD_COLORS = ("#e0e7ff", "#dcfce7", "#fef3c7", "#fce7f3", "#dbeafe", "#ede9fe")
_ACCENTS = ("#4338ca", "#047857", "#b45309", "#be185d", "#1d4ed8", "#6d28d9")


def _wrap(value: str, width: int, max_lines: int) -> list[str]:
    normalized = " ".join(str(value or "").split())
    if not normalized:
        return [""]
    lines = textwrap.wrap(normalized, width=width, break_long_words=True, break_on_hyphens=False)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1].rstrip()
        lines[-1] = (last[:-1].rstrip() if len(last) >= width else last) + "…"
    return lines


def _text(lines: list[str], *, x: int, y: int, size: int, fill: str, weight: int = 400, line_height: int = 32) -> str:
    if not lines:
        return ""
    spans = []
    for index, line in enumerate(lines):
        dy = "" if index == 0 else f' dy="{line_height}"'
        spans.append(f'<tspan x="{x}"{dy}>{escape(line)}</tspan>')
    return (
        f'<text x="{x}" y="{y}" fill="{fill}" font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{size}" font-weight="{weight}">' + "".join(spans) + "</text>"
    )


def build_infographic(*, title: str, subtitle: str = "", audience: str = "", key_points: list[str], source_urls: list[str] | None = None) -> dict[str, Any]:
    """Build a self-contained SVG from supplied text; does not call an image provider or fetch URLs."""
    title = " ".join(str(title or "").split())
    subtitle = " ".join(str(subtitle or "").split())
    audience = " ".join(str(audience or "").split())
    points = list(dict.fromkeys(" ".join(str(item or "").split()) for item in key_points if str(item or "").strip()))
    if len(title) < 3 or len(title) > 100:
        raise ValueError("Title must contain 3–100 characters")
    if not 3 <= len(points) <= 6:
        raise ValueError("Provide between three and six distinct points")
    if any(len(item) > 220 for item in points):
        raise ValueError("Each point must be at most 220 characters")
    if len(subtitle) > 180 or len(audience) > 120:
        raise ValueError("Subtitle or audience exceeds its supported length")

    title_lines = _wrap(title, 29, 3)
    subtitle_text = subtitle or (f"For {audience}" if audience else "A visual summary of the points you supplied.")
    subtitle_lines = _wrap(subtitle_text, 52, 2)
    rows = math.ceil(len(points) / 2)
    card_top, card_bottom, margin = 350, 1190, 64
    column_gap, row_gap = 24, 20
    card_width = (WIDTH - margin * 2 - column_gap) // 2
    card_height = int((card_bottom - card_top - row_gap * (rows - 1)) / rows)

    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="infographic-title">',
        f'<title id="infographic-title">{escape(title)}</title>',
        '<rect width="1080" height="1350" fill="#f8fafc"/>',
        '<rect width="1080" height="320" fill="#0f172a"/>',
        '<circle cx="1005" cy="50" r="180" fill="#4f46e5" opacity="0.28"/>',
        '<circle cx="975" cy="300" r="115" fill="#06b6d4" opacity="0.14"/>',
        _text(title_lines, x=64, y=92, size=54, fill="#ffffff", weight=700, line_height=58),
        _text(subtitle_lines, x=66, y=92 + len(title_lines) * 58 + 12, size=25, fill="#cbd5e1", weight=400, line_height=31),
        '<text x="64" y="318" fill="#6366f1" font-family="Arial, Helvetica, sans-serif" font-size="16" font-weight="700" letter-spacing="3">KEY TAKEAWAYS</text>',
    ]

    cards: list[dict[str, Any]] = []
    for index, point in enumerate(points):
        row, column = divmod(index, 2)
        x = margin + column * (card_width + column_gap)
        y = card_top + row * (card_height + row_gap)
        color, accent = _CARD_COLORS[index % len(_CARD_COLORS)], _ACCENTS[index % len(_ACCENTS)]
        lines = _wrap(point, 34, 5)
        pieces.extend([
            f'<rect x="{x}" y="{y}" width="{card_width}" height="{card_height}" rx="24" fill="{color}"/>',
            f'<rect x="{x}" y="{y}" width="9" height="{card_height}" rx="4" fill="{accent}"/>',
            f'<text x="{x + 30}" y="{y + 48}" fill="{accent}" font-family="Arial, Helvetica, sans-serif" font-size="17" font-weight="700" letter-spacing="2">POINT {index + 1:02d}</text>',
            _text(lines, x=x + 30, y=y + 94, size=25, fill="#0f172a", weight=600, line_height=32),
        ])
        cards.append({
            "number": index + 1, "label": f"Point {index + 1:02d}", "text": point,
            "lines": lines, "color": color, "accent": accent,
        })

    pieces.extend([
        '<line x1="64" y1="1226" x2="1016" y2="1226" stroke="#cbd5e1" stroke-width="2"/>',
        '<text x="64" y="1265" fill="#475569" font-family="Arial, Helvetica, sans-serif" font-size="18" font-weight="600">Draft asset · Review source facts before publication</text>',
        '<text x="64" y="1301" fill="#64748b" font-family="Arial, Helvetica, sans-serif" font-size="15">No external images, remote resources or scripts are embedded.</text>',
        "</svg>",
    ])
    svg = "\n".join(pieces)
    if "<script" in svg.lower() or "onload=" in svg.lower() or "foreignObject" in svg:
        raise ValueError("Generated SVG failed the safe-output check")
    return {
        "title": title, "subtitle": subtitle_text, "audience": audience or None,
        "key_points": points, "cards": cards, "width": WIDTH, "height": HEIGHT,
        "format": "image/svg+xml", "svg": svg,
        "source_urls": list(dict.fromkeys(source_urls or [])),
        "requires_review": True, "publishing_started": False, "external_image_provider_used": False,
        "note": "This is a deterministic vector draft using only supplied text. References are saved but not fetched; confirm facts, rights and disclosures before publication.",
    }
