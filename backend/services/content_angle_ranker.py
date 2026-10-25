from __future__ import annotations

import re
from typing import Any


_STOP_WORDS = frozenset(
    "a an and are as at be been best by can for from how in into is it its of on or our "
    "the their them these this to toward use using was we with without your".split()
)
_RISK_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "guarantee_or_risk_free_language",
        re.compile(r"\b(?:guarantee(?:d|s)?|risk[- ]free|no risk|100%\s+success)\b", re.IGNORECASE),
    ),
    (
        "specific_earnings_claim",
        re.compile(r"\b(?:earn|make)\s+\$?\d[\d,]*(?:\.\d+)?", re.IGNORECASE),
    ),
    (
        "absolute_or_medical_claim",
        re.compile(r"\b(?:cure|miracle|number one|#\s?1)\b", re.IGNORECASE),
    ),
)


def _tokens(value: str) -> set[str]:
    tokens = set()
    for token in re.findall(r"[a-z0-9]+", value.casefold()):
        if token in _STOP_WORDS or len(token) < 2:
            continue
        # Conservative plural normalization only; this is a lexical heuristic, not NLP lemmatization.
        if len(token) > 4 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
            token = token[:-1]
        tokens.add(token)
    return tokens


def _coverage(reference: set[str], content: set[str]) -> int:
    if not reference:
        return 0
    return round(100 * len(reference & content) / len(reference))


def _evidence_score(angle_tokens: set[str], evidence_facts: list[str]) -> int:
    if not evidence_facts:
        return 0
    evidence_tokens = _tokens(" ".join(evidence_facts))
    relationship = _coverage(angle_tokens, evidence_tokens)
    completeness = 30 + 15 * min(len(evidence_facts), 3)
    return min(100, completeness + round(relationship * 0.25))


def rank_content_angles(
    *,
    topic: str,
    audience: str = "",
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Rank candidate editorial angles with transparent lexical/evidence heuristics.

    This score describes editorial alignment only. It is not a conversion, revenue,
    SEO-position, CTR, or profit forecast and does not establish factual truth.
    """
    normalized_topic = str(topic or "").strip()
    normalized_audience = str(audience or "").strip()
    topic_tokens = _tokens(normalized_topic)
    audience_tokens = _tokens(normalized_audience)
    if not topic_tokens:
        raise ValueError("Topic must contain at least one meaningful keyword")
    if not candidates:
        raise ValueError("At least one candidate angle is required")

    ranked: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise ValueError("Each candidate must be an object")
        angle = str(candidate.get("angle") or "").strip()
        if len(angle) < 5:
            raise ValueError("Each angle must contain at least five non-whitespace characters")
        description = str(candidate.get("description") or "").strip()
        evidence_facts = [
            str(item).strip()[:1200]
            for item in (candidate.get("evidence_facts") or [])
            if isinstance(item, str) and item.strip()
        ][:8]
        candidate_text = f"{angle} {description}".strip()
        candidate_tokens = _tokens(candidate_text)
        topic_relevance = _coverage(topic_tokens, candidate_tokens)
        audience_alignment = _coverage(audience_tokens, candidate_tokens) if audience_tokens else None
        evidence_support = _evidence_score(candidate_tokens, evidence_facts)
        specificity = min(100, len(candidate_tokens) * 6)

        risk_flags = [
            flag
            for flag, pattern in _RISK_RULES
            if pattern.search(candidate_text)
        ]
        risk_penalty = min(36, len(risk_flags) * 12)

        if audience_tokens:
            weighted_score = (
                topic_relevance * 0.50
                + (audience_alignment or 0) * 0.20
                + evidence_support * 0.20
                + specificity * 0.10
            )
        else:
            # Reallocate the unavailable audience weight rather than treating missing data as a negative.
            weighted_score = topic_relevance * 0.625 + evidence_support * 0.25 + specificity * 0.125
        final_score = max(0, min(100, round(weighted_score - risk_penalty)))

        reasons: list[str] = []
        reasons.append(
            "strong_topic_match" if topic_relevance >= 60
            else "moderate_topic_match" if topic_relevance >= 30
            else "weak_topic_match"
        )
        if audience_tokens:
            reasons.append(
                "audience_terms_aligned" if (audience_alignment or 0) >= 40
                else "audience_alignment_needs_review"
            )
        else:
            reasons.append("audience_not_provided")
        reasons.append(
            "operator_evidence_notes_present_unverified"
            if evidence_facts else "no_evidence_notes_supplied"
        )
        if specificity < 30:
            reasons.append("angle_may_be_too_broad")
        if risk_flags:
            reasons.append("potentially_high_risk_claim_language")

        ranked.append(
            {
                "candidate_index": index,
                "angle": angle,
                "description": description,
                "score": final_score,
                "score_components": {
                    "topic_relevance": topic_relevance,
                    "audience_alignment": audience_alignment,
                    "evidence_support": evidence_support,
                    "specificity": specificity,
                    "risk_penalty": risk_penalty,
                },
                "risk_flags": risk_flags,
                "reasons": reasons,
                "evidence_facts": evidence_facts,
                "evidence_status": (
                    "operator_supplied_not_independently_verified" if evidence_facts else "not_supplied"
                ),
                "requires_review": True,
                "_original_index": index,
            }
        )

    ranked.sort(key=lambda item: (-item["score"], item["_original_index"]))
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
        item.pop("_original_index", None)

    return {
        "topic": normalized_topic,
        "audience": normalized_audience,
        "ranking_method": "deterministic_editorial_heuristic_v1",
        "score_definition": (
            "Relative editorial relevance based on lexical topic fit, optional audience fit, "
            "operator-supplied evidence-note coverage, specificity, and detected risky claim language."
        ),
        "results": ranked,
        "forecast": {
            "estimated_ctr": None,
            "estimated_conversion_rate": None,
            "estimated_revenue": None,
            "estimated_profit": None,
        },
        "requires_review": True,
        "publishing_started": False,
        "note": (
            "Scores are editorial triage heuristics, not measured performance or predictions. "
            "Evidence notes are user-supplied and have not been independently verified. "
            "Verify claims and platform rules before approval or publication."
        ),
    }
