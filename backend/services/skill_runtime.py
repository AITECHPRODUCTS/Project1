from __future__ import annotations

import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any

SUPPORTED_RUNTIME_HANDLERS = (
    "none",
    "content.extractive_summary",
    "research.keyword_extract",
    "analytics.roas_calculator",
)

_HANDLER_DESCRIPTIONS = {
    "none": "Declarative-only package; instructions are not executed.",
    "content.extractive_summary": "Deterministic local extractive summary from supplied text; no model or network call.",
    "research.keyword_extract": "Deterministic frequency-based keyword extraction from supplied text; no search-volume claim.",
    "analytics.roas_calculator": "Decimal-based ROAS calculation and review-only stop-loss signal; no campaign action.",
}


def describe_runtime_handlers() -> list[dict[str, str]]:
    return [
        {"key": key, "description": _HANDLER_DESCRIPTIONS[key], "external_side_effects": "none"}
        for key in SUPPORTED_RUNTIME_HANDLERS
    ]


def _require_input_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Skill runtime input must be a JSON object")
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Skill runtime input must contain finite JSON values only") from exc
    if len(encoded.encode("utf-8")) > 32 * 1024:
        raise ValueError("Skill runtime input exceeds the 32 KiB execution limit")
    return value


def _text_extract_summary(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload.get("text")
    limit = payload.get("max_sentences")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if len(text) > 20000:
        raise ValueError("text exceeds the 20,000 character runtime limit")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
        raise ValueError("max_sentences must be an integer from 1 to 10")
    normalized = " ".join(text.split())
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]
    selected = sentences[:limit]
    return {
        "summary": " ".join(selected),
        "sentence_count": len(selected),
        "source_character_count": len(normalized),
    }


_STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "your", "you", "are",
    "was", "were", "has", "have", "had", "into", "about", "when", "where",
    "how", "why", "can", "will", "not", "but", "its", "their", "our", "use",
    "using", "through", "then", "than", "they", "them", "all", "new", "per",
}


def _keyword_extract(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload.get("text")
    limit = payload.get("limit")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if len(text) > 20000:
        raise ValueError("text exceeds the 20,000 character runtime limit")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("limit must be an integer from 1 to 20")
    tokens = re.findall(r"[a-z0-9][a-z0-9'-]{1,}", text.casefold())
    counts = Counter(token.strip("'-") for token in tokens)
    candidates = {word: count for word, count in counts.items() if len(word) >= 3 and word not in _STOP_WORDS}
    ranked = sorted(candidates, key=lambda word: (-candidates[word], word))[:limit]
    return {
        "keywords": ranked,
        "keyword_count": len(ranked),
        "source_token_count": len(tokens),
    }


def _roas_calculator(payload: dict[str, Any]) -> dict[str, Any]:
    values = {}
    for key in ("spend_usd", "commission_usd", "minimum_roas"):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError(f"{key} must be a finite non-negative number")
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"{key} must be a finite non-negative number") from exc
        if not decimal_value.is_finite() or decimal_value < 0:
            raise ValueError(f"{key} must be a finite non-negative number")
        values[key] = decimal_value
    spend = values["spend_usd"]
    commission = values["commission_usd"]
    minimum = values["minimum_roas"]
    common = {
        "roas_available": spend > 0,
        "pause_recommended": False,
        "minimum_roas": float(minimum),
        "requires_human_review": True,
    }
    if spend == 0:
        return {**common, "reason": "ROAS is unavailable because spend is zero."}
    ratio = commission / spend
    below = ratio < minimum
    return {
        **common,
        "roas": float(ratio.quantize(Decimal("0.000001"))),
        "pause_recommended": bool(below),
        "reason": (
            "Below threshold; review only. Confirm attribution-window maturity before any pause."
            if below else
            "At or above threshold; no remote campaign action was taken."
        ),
    }


def execute_skill_handler(handler_key: str, input_value: Any) -> dict[str, Any]:
    """Execute one code-owned pure handler. Package Markdown and authored code are never executed."""
    if handler_key not in SUPPORTED_RUNTIME_HANDLERS:
        raise ValueError("Unsupported runtime handler")
    if handler_key == "none":
        raise ValueError("This package has no executable runtime handler")
    payload = _require_input_object(input_value)
    if handler_key == "content.extractive_summary":
        return _text_extract_summary(payload)
    if handler_key == "research.keyword_extract":
        return _keyword_extract(payload)
    if handler_key == "analytics.roas_calculator":
        return _roas_calculator(payload)
    raise ValueError("Unsupported runtime handler")
