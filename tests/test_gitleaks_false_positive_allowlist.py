from __future__ import annotations

from pathlib import Path

EXPECTED_REVIEWED_FALSE_POSITIVE = (
    "513bbaacd9441024ef191472c95dd80289c6ea31:"
    "knowledge/affiliate-skills/upstream/skills/content/viral-post-writer/SKILL.md:"
    "linkedin-client-id:68"
)


def test_gitleaks_allowlist_contains_only_one_exact_reviewed_fingerprint():
    entries = [
        line.strip()
        for line in Path(".gitleaksignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert entries == [EXPECTED_REVIEWED_FALSE_POSITIVE]


def test_gitleaks_allowlist_never_contains_wildcards_or_path_exclusions():
    entry = Path(".gitleaksignore").read_text(encoding="utf-8").strip()
    assert "*" not in entry
    assert entry.startswith("513bbaacd9441024ef191472c95dd80289c6ea31:")
    assert ":linkedin-client-id:68" in entry
