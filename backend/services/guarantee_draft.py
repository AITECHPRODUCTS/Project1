from __future__ import annotations

import re
from typing import Any


_KIND_TERMS = {
    "refund": re.compile(r"\b(?:refund|money[\s-]*back|reimburse|return period)\b", re.IGNORECASE),
    "replacement": re.compile(r"\b(?:replacement|replace|exchange)\b", re.IGNORECASE),
    "repair": re.compile(r"\b(?:repair|warranty)\b", re.IGNORECASE),
    "trial": re.compile(r"\b(?:trial|test period)\b", re.IGNORECASE),
    "service_credit": re.compile(r"\b(?:service credit|credit)\b", re.IGNORECASE),
    "other": None,
}


def build_guarantee_draft(
    *,
    product_name: str,
    guarantee_type: str,
    duration_days: int,
    eligibility: str,
    exclusions: list[str],
    claim_process: str,
    merchant_terms_text: str,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Draft transparent guarantee copy only when the supplied terms mention its type and duration."""
    product_name = " ".join(str(product_name or "").split())
    eligibility = " ".join(str(eligibility or "").split())
    claim_process = " ".join(str(claim_process or "").split())
    terms = " ".join(str(merchant_terms_text or "").split())
    kind = str(guarantee_type or "").strip().lower()
    if not product_name or not eligibility or not claim_process or len(terms) < 30:
        raise ValueError("Product, eligibility, claim process and merchant terms are required")
    if not 1 <= int(duration_days) <= 3650:
        raise ValueError("Duration must be between 1 and 3650 days")
    if kind not in _KIND_TERMS:
        raise ValueError("Unsupported guarantee type")

    duration_pattern = re.compile(
        rf"(?<!\d){int(duration_days)}\s*(?:-\s*)?(?:calendar\s+)?days?\b",
        re.IGNORECASE,
    )
    if not duration_pattern.search(terms):
        raise ValueError("The requested duration is not explicitly present in the supplied merchant terms")
    kind_pattern = _KIND_TERMS[kind]
    if kind_pattern is not None and not kind_pattern.search(terms):
        raise ValueError("The supplied merchant terms do not mention this guarantee type")

    normalized_exclusions = list(dict.fromkeys(
        " ".join(str(item or "").split()) for item in (exclusions or []) if str(item or "").strip()
    ))[:10]
    exclusions_text = (
        "; ".join(normalized_exclusions)
        if normalized_exclusions
        else "No exclusions were supplied; do not imply that the merchant has no exclusions."
    )
    display_kind = kind.replace("_", " ")
    source_label = f" Source reference: {source_url}." if source_url else ""
    draft_copy = (
        f"Draft copy — operator-supplied terms, not independently verified: "
        f"According to the merchant terms provided for review, {product_name} is described as having a "
        f"{int(duration_days)}-day {display_kind} for {eligibility}. "
        f"Exclusions to confirm: {exclusions_text} "
        f"Claim process supplied for review: {claim_process}. "
        f"Check the current official merchant terms and all conditions before publishing.{source_label}"
    )
    return {
        "product_name": product_name,
        "guarantee_type": kind,
        "duration_days": int(duration_days),
        "eligibility": eligibility,
        "exclusions": normalized_exclusions,
        "claim_process": claim_process,
        "source_url": source_url,
        "draft_copy": draft_copy,
        "merchant_terms_status": "operator_supplied_not_independently_verified",
        "duration_found_in_terms": True,
        "guarantee_type_found_in_terms": kind_pattern is None or bool(kind_pattern.search(terms)),
        "terms_verified": False,
        "requires_review": True,
        "publishing_started": False,
        "note": "This is a review-only draft based on supplied text. It is not legal advice, does not prove the merchant offer is current, and must not be published before official terms are checked.",
    }
