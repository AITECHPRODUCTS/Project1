from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any

from backend.config import get_settings
from backend.core.errors import IntegrationNotConfiguredError
from backend.services.url_safety import request_public_json


@dataclass(frozen=True)
class ROASDecision:
    campaign_id: str
    spend: float
    commission: float
    roas: float | None
    threshold: float
    pause_recommended: bool
    executed: bool
    reason: str


def _finite_nonnegative_number(name: str, value: Any) -> float:
    """Reject invalid money/threshold inputs instead of silently clamping them."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite, non-negative number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite, non-negative number") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be a finite, non-negative number")
    return number


def evaluate_roas(
    campaign_id: str,
    spend: float,
    commission: float,
    threshold: float = 1.2,
) -> ROASDecision:
    if not isinstance(campaign_id, str) or not campaign_id.strip() or len(campaign_id) > 255:
        raise ValueError("campaign_id must be a non-empty string of at most 255 characters")

    spend_value = _finite_nonnegative_number("spend", spend)
    commission_value = _finite_nonnegative_number("commission", commission)
    threshold_value = _finite_nonnegative_number("threshold", threshold)

    roas = commission_value / spend_value if spend_value > 0 else None
    if roas is not None and not math.isfinite(roas):
        raise ValueError("ROAS result exceeds the supported numeric range")

    should_pause = (
        spend_value > 0
        and roas is not None
        and roas < threshold_value
    )
    return ROASDecision(
        campaign_id=campaign_id.strip(),
        spend=spend_value,
        commission=commission_value,
        roas=roas,
        threshold=threshold_value,
        pause_recommended=should_pause,
        executed=False,
        reason=(
            "Stop-loss recommendation only; no remote campaign state was changed."
            if should_pause
            else "ROAS is above threshold or there is no spend data."
        ),
    )


async def pause_meta_campaign(campaign_id: str, access_token: str) -> dict[str, Any]:
    if not get_settings().ad_automation_execute:
        return {"executed": False, "reason": "AD_AUTOMATION_EXECUTE=false"}
    if (
        not campaign_id
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", campaign_id)
        or not access_token
    ):
        raise IntegrationNotConfiguredError(
            "Meta campaign id and authorized access token required"
        )
    data = await request_public_json(
        f"https://graph.facebook.com/v23.0/{campaign_id}",
        method="POST",
        data_body={"status": "PAUSED", "access_token": access_token},
        timeout=15,
        max_bytes=1_000_000,
    )
    return {"executed": bool(data.get("success")), "provider": "meta", "response": data}
