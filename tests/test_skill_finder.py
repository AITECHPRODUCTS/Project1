from __future__ import annotations

import csv

import pytest

from backend.services import skill_finder


def write_matrix(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["skill_id", "stage", "status", "evidence", "gap"])
        writer.writeheader()
        writer.writerows(rows)


def test_finder_ranks_matching_skill_and_preserves_partial_gap_status(tmp_path, monkeypatch):
    path = tmp_path / "skills.csv"
    write_matrix(path, [
        {"skill_id":"research/purple-cow-audit","stage":"S2","status":"partial","evidence":"purple cow service and API","gap":"Buyer validation remains"},
        {"skill_id":"meta/skill-finder","stage":"S1","status":"partial","evidence":"searchable skill inventory","gap":"Upstream skill text remains incomplete"},
        {"skill_id":"blog/content-decay-detector","stage":"S3","status":"not_implemented","evidence":"","gap":"No Search Console ingestion"},
    ])
    monkeypatch.setattr(skill_finder, "MATRIX_PATH", path)
    result = skill_finder.find_skills(query="purple cow", stage="S2", status="partial", limit=5)
    assert result["skill_count"] == 3
    assert result["matched_count"] == 1
    assert result["results"][0]["skill_id"] == "research/purple-cow-audit"
    assert result["results"][0]["status"] == "partial"
    assert result["read_only"] is True


def test_finder_can_search_gap_text_and_returns_empty_results_for_no_match(tmp_path, monkeypatch):
    path = tmp_path / "skills.csv"
    write_matrix(path, [
        {"skill_id":"blog/content-decay-detector","stage":"S3","status":"not_implemented","evidence":"","gap":"No Search Console ingestion"},
    ])
    monkeypatch.setattr(skill_finder, "MATRIX_PATH", path)
    result = skill_finder.find_skills(query="Search Console", status="not_implemented")
    assert result["matched_count"] == 1
    assert result["results"][0]["gap"] == "No Search Console ingestion"
    assert skill_finder.find_skills(query="webinar provider")["matched_count"] == 0


def test_finder_rejects_invalid_filters_and_missing_inventory(tmp_path, monkeypatch):
    path = tmp_path / "skills.csv"
    write_matrix(path, [{"skill_id":"meta/skill-finder","stage":"S1","status":"partial","evidence":"searchable skill inventory","gap":"Need UAT"}])
    monkeypatch.setattr(skill_finder, "MATRIX_PATH", path)
    with pytest.raises(ValueError, match="S1 through S8"):
        skill_finder.find_skills(query="skill", stage="S9")
    with pytest.raises(ValueError, match="not present"):
        skill_finder.find_skills(query="skill", status="fully_implemented")
    monkeypatch.setattr(skill_finder, "MATRIX_PATH", tmp_path / "missing.csv")
    with pytest.raises(FileNotFoundError):
        skill_finder.find_skills(query="skill")
