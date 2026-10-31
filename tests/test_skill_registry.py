from __future__ import annotations

import csv
from pathlib import Path

from scripts.verify_skill_registry import git_blob_sha, read_skill_matrix, readme_skill_claim, verify_skill_registry


def test_git_blob_sha_uses_git_object_header():
    assert git_blob_sha(b"hello") == "b6fc4c620b67d95f953a5c1c1230aaab5db5a1b0"


def test_readme_skill_count_parser_captures_historical_mismatch():
    assert readme_skill_claim("## The Affiliate Flywheel — 8 Stages, 52 Skills") == 52
    assert readme_skill_claim("A newer doc without the claim") is None


def test_matrix_parser_handles_commas_and_escaped_quotes_in_fields(tmp_path: Path):
    path = tmp_path / "matrix.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["skill_id", "stage", "status", "evidence", "gap"])
        writer.writeheader()
        writer.writerow({
            "skill_id": "research/traffic-analyzer",
            "stage": "S1",
            "status": "partial",
            "evidence": 'POST /api/research, "review-only"',
            "gap": "No provider",
        })
    rows = read_skill_matrix(path)
    assert rows[0]["evidence"] == 'POST /api/research, "review-only"'


def test_current_pinned_source_registry_matches_runtime_matrix():
    errors, notes, summary = verify_skill_registry()
    assert not errors, "\n".join(errors)
    assert summary["source_skills"] == 53
    assert summary["matrix_rows"] == 53
    assert summary["vendored_files_checked"] == 72
    assert summary["status_counts"]["partial"] == 53
    assert summary["status_counts"].get("not_implemented", 0) == 0
    assert any("README says 52" in note for note in notes)
