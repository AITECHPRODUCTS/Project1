from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

# Store only campaign attribution dimensions we actively support. Values are
# bounded and obvious email addresses are dropped so UTM tags don't become a
# convenient accidental PII store.
UTM_FIELD_LIMITS: dict[str, int] = {
    "utm_source": 120,
    "utm_medium": 80,
    "utm_campaign": 200,
    "utm_content": 200,
    "utm_term": 160,
}
_EMAIL_IN_TEXT = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")


def normalize_utm_attribution(values: Mapping[str, Any] | None) -> dict[str, str]:
    """Return only allowlisted, bounded UTM fields suitable for storage/rendering."""
    if not isinstance(values, Mapping):
        return {}
    result: dict[str, str] = {}
    for name, limit in UTM_FIELD_LIMITS.items():
        raw = values.get(name)
        if raw is None or isinstance(raw, (Mapping, list, tuple, set)):
            continue
        cleaned = "".join(character for character in str(raw) if character.isprintable()).strip()
        if not cleaned or _EMAIL_IN_TEXT.search(cleaned):
            continue
        result[name] = cleaned[:limit]
    return result


def merge_lead_attribution_metadata(
    existing_metadata: Any,
    values: Mapping[str, Any] | None,
    *,
    observed_at: datetime,
) -> dict[str, Any]:
    """Preserve first touch and update last touch on tagged lead-capture events."""
    metadata = dict(existing_metadata) if isinstance(existing_metadata, Mapping) else {}
    current = normalize_utm_attribution(values)
    if not current:
        return metadata

    previous = metadata.get("attribution")
    previous = previous if isinstance(previous, Mapping) else {}
    first_touch = normalize_utm_attribution(previous.get("first_touch"))
    if not first_touch:
        first_touch = dict(current)

    timestamp = (
        observed_at.replace(tzinfo=timezone.utc)
        if observed_at.tzinfo is None
        else observed_at.astimezone(timezone.utc)
    )
    metadata["attribution"] = {
        "first_touch": first_touch,
        "last_touch": current,
        "last_touch_at": timestamp.isoformat(),
    }
    return metadata


def lead_attribution_summary(existing_metadata: Any) -> dict[str, Any]:
    """Expose the allowlisted attribution summary without returning raw metadata."""
    if not isinstance(existing_metadata, Mapping):
        return {}
    attribution = existing_metadata.get("attribution")
    if not isinstance(attribution, Mapping):
        return {}
    first_touch = normalize_utm_attribution(attribution.get("first_touch"))
    last_touch = normalize_utm_attribution(attribution.get("last_touch"))
    if not first_touch and not last_touch:
        return {}
    last_touch_at = attribution.get("last_touch_at")
    return {
        "first_touch": first_touch,
        "last_touch": last_touch,
        "last_touch_at": last_touch_at if isinstance(last_touch_at, str) else None,
    }
