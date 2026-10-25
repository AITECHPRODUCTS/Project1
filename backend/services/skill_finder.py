from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

MATRIX_PATH = Path(__file__).resolve().parents[2] / "docs" / "skill-parity-matrix.csv"
_REQUIRED_COLUMNS = {"skill_id", "stage", "status", "evidence", "gap"}


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def _read_inventory() -> list[dict[str, str]]:
    if not MATRIX_PATH.is_file():
        raise FileNotFoundError("Skill parity inventory is missing")
    with MATRIX_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not _REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
            raise ValueError("Skill parity inventory has an unexpected schema")
        rows = []
        for raw in reader:
            row = {column: str(raw.get(column) or "").strip() for column in _REQUIRED_COLUMNS}
            if row["skill_id"]:
                rows.append(row)
    if not rows:
        raise ValueError("Skill parity inventory contains no skill rows")
    return rows


def find_skills(*, query: str, stage: str | None = None, status: str | None = None, limit: int = 10) -> dict[str, Any]:
    """Search the committed skill inventory; status is a traceability label, not a release certification."""
    query = str(query or "").strip()
    terms = _tokens(query)
    if len(query) < 2 or not terms:
        raise ValueError("Enter at least two characters with a searchable term")
    if stage:
        stage = stage.strip().upper()
        if not re.fullmatch(r"S[1-8]", stage):
            raise ValueError("Stage must be one of S1 through S8")
    if not 1 <= limit <= 30:
        raise ValueError("Limit must be between 1 and 30")

    rows = _read_inventory()
    allowed_statuses = {row["status"] for row in rows}
    if status:
        status = status.strip().lower()
        if status not in allowed_statuses:
            raise ValueError("Status filter is not present in the current skill inventory")

    ranked: list[dict[str, Any]] = []
    for row in rows:
        if stage and row["stage"] != stage:
            continue
        if status and row["status"] != status:
            continue
        identifiers = _tokens(row["skill_id"].replace("/", " "))
        evidence = _tokens(row["evidence"])
        gaps = _tokens(row["gap"])
        status_tokens = _tokens(row["status"])
        stage_tokens = _tokens(row["stage"])
        weighted = 0
        matched: list[str] = []
        for term in sorted(terms):
            weights = [
                5 if term in identifiers else 0,
                3 if term in evidence else 0,
                2 if term in status_tokens else 0,
                1 if term in gaps or term in stage_tokens else 0,
            ]
            best = max(weights)
            weighted += best
            if best:
                matched.append(term)
        if not matched:
            continue
        relevance = round(100 * weighted / (5 * len(terms)))
        ranked.append({
            "skill_id": row["skill_id"],
            "stage": row["stage"],
            "status": row["status"],
            "evidence": row["evidence"],
            "gap": row["gap"],
            "matched_query_terms": matched,
            "relevance_score": relevance,
        })
    ranked.sort(key=lambda item: (-item["relevance_score"], item["skill_id"]))
    return {
        "query": query,
        "filters": {"stage": stage, "status": status},
        "inventory_source": "docs/skill-parity-matrix.csv",
        "skill_count": len(rows),
        "matched_count": len(ranked),
        "results": ranked[:limit],
        "read_only": True,
        "note": "Statuses are project traceability labels; they do not prove current provider authorization, full end-to-end behavior, or production readiness.",
    }
