from __future__ import annotations
import re
from typing import Any

_STOP_WORDS = frozenset("a an and are as at be been best by can for from how in into is it its of on or our the their them these this to was we with without your".split())
_RISK_RULES = (
    ("guarantee_or_risk_free_language", re.compile(r"\b(?:guarantee(?:d|s)?|risk[- ]free|no risk|100%\s+success)\b", re.I)),
    ("absolute_superiority_or_exclusivity", re.compile(r"\b(?:best|number one|#\s?1|only|first ever|unmatched|unbeatable)\b", re.I)),
    ("medical_or_income_claim", re.compile(r"\b(?:cure|miracle|earn\s+\$?\d[\d,]*(?:\.\d+)?)\b", re.I)),
)

def _tokens(value: str) -> set[str]:
    tokens: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", str(value or "").casefold()):
        if token in _STOP_WORDS or len(token) < 2:
            continue
        if len(token) > 4 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
            token = token[:-1]
        tokens.add(token)
    return tokens

def _coverage(reference: set[str], candidate: set[str]) -> int:
    return round(100 * len(reference & candidate) / len(reference)) if reference else 0

def _clarity_score(statement: str, token_count: int) -> int:
    words = len(statement.split())
    if 6 <= words <= 18 and token_count >= 4:
        return 100
    if 4 <= words <= 25 and token_count >= 3:
        return 75
    return 45

def audit_purple_cow_positioning(*, offer_name: str, target_audience: str, positioning_statement: str, alternatives: list[dict[str, Any]], evidence_notes: list[str] | None = None) -> dict[str, Any]:
    """Compare wording with supplied alternatives; this is not market research or a performance forecast."""
    offer_name, target_audience, positioning_statement = (str(x or "").strip() for x in (offer_name, target_audience, positioning_statement))
    if len(offer_name) < 2 or len(target_audience) < 2 or len(positioning_statement) < 5:
        raise ValueError("Offer name, target audience and positioning statement are required")
    if not alternatives:
        raise ValueError("At least one supplied alternative positioning statement is required")
    position_tokens, audience_tokens = _tokens(positioning_statement), _tokens(target_audience)
    if len(position_tokens) < 2:
        raise ValueError("Positioning statement needs at least two meaningful terms")
    comparisons, overlap_scores = [], []
    for alt in alternatives[:10]:
        name, text = str(alt.get("name") or "").strip()[:120], str(alt.get("positioning_statement") or "").strip()[:600]
        if len(name) < 2 or len(text) < 5:
            raise ValueError("Each alternative needs a name and positioning statement")
        terms = _tokens(text)
        shared, overlap = sorted(position_tokens & terms), _coverage(position_tokens, terms)
        overlap_scores.append(overlap)
        comparisons.append({"name":name,"positioning_statement":text,"lexical_overlap_score":overlap,"shared_terms":shared[:12],"evidence_note_status":"operator_supplied_not_independently_verified" if alt.get("evidence_note") else "not_supplied"})
    distinctiveness = max(0, 100-max(overlap_scores, default=0))
    audience_fit = _coverage(audience_tokens, position_tokens | _tokens(offer_name))
    clarity = _clarity_score(positioning_statement, len(position_tokens))
    evidence = list(dict.fromkeys(str(n).strip()[:1200] for n in (evidence_notes or []) if isinstance(n,str) and n.strip()))[:8]
    proof = min(100, 25*len(evidence)) if evidence else None
    weighted = [(distinctiveness,.35),(audience_fit,.30),(clarity,.15)]
    if proof is not None:
        weighted.append((proof,.20))
    base = round(sum(value*weight for value,weight in weighted)/sum(weight for _,weight in weighted))
    risk_flags = [name for name, pattern in _RISK_RULES if pattern.search(positioning_statement)]
    penalty = min(36,12*len(risk_flags))
    recommendations = []
    max_overlap=max(overlap_scores,default=0)
    if max_overlap >= 60:
        recommendations.append("The positioning shares many lexical terms with at least one supplied alternative. Test a concrete use case or mechanism instead of relying on generic adjectives.")
    elif max_overlap >= 35:
        recommendations.append("Some language overlaps with the supplied alternatives. Clarify the specific audience problem or operating mechanism that makes the approach meaningfully different.")
    else:
        recommendations.append("The wording is lexically distinct from the alternatives supplied here; validate whether buyers perceive the difference as valuable.")
    if audience_fit < 40:
        recommendations.append("Make the intended audience and the job-to-be-done more explicit in the positioning statement.")
    if proof is None:
        recommendations.append("Add primary-source proof, product facts or customer-research notes before making a comparative differentiation claim.")
    else:
        recommendations.append("Evidence notes are operator-supplied only. Verify each note independently before treating it as proof.")
    if risk_flags:
        recommendations.append("Review absolute, guarantee, medical or income wording; remove it unless current evidence and applicable rules substantiate the claim.")
    if clarity < 75:
        recommendations.append("Rewrite the statement into a concrete and readable sentence describing who it helps and the specific problem or workflow.")
    return {
        "offer_name":offer_name,"target_audience":target_audience,"positioning_statement":positioning_statement,
        "score":max(0,min(100,base-penalty)),
        "score_definition":"Relative editorial triage from lexical separation versus supplied alternatives, audience-language fit, statement clarity and optional evidence-note presence. Missing evidence is excluded and weights are renormalized. Not proof of uniqueness or a market, demand, conversion or revenue forecast.",
        "score_components":{"lexical_distinctiveness_vs_supplied_alternatives":distinctiveness,"audience_language_fit":audience_fit,"positioning_clarity":clarity,"evidence_readiness":proof},
        "risk_penalty":penalty,"risk_flags":risk_flags,"alternative_comparisons":comparisons,
        "evidence_notes":evidence,"evidence_status":"operator_supplied_not_independently_verified" if evidence else "not_supplied",
        "recommendations":recommendations,"requires_review":True,"market_research_performed":False,"publishing_started":False,
        "note":"Only supplied positioning statements were compared. Competitor claims, evidence and audience fit were not independently verified; do not describe this result as proof that the offer is unique."
    }
