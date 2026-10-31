from __future__ import annotations

from pathlib import Path

EXPECTED_REVIEWED_FALSE_POSITIVES = [
    (
        "513bbaacd9441024ef191472c95dd80289c6ea31:"
        "knowledge/affiliate-skills/upstream/skills/content/viral-post-writer/SKILL.md:"
        "linkedin-client-id:68"
    ),
    (
        "439a3c39c374ad1d51bde0a8a5cb2f205b976e09:"
        "knowledge/affiliate-skills/upstream/skills/content/viral-post-writer/SKILL.md:"
        "linkedin-client-id:68"
    ),
    # These two report fingerprints are synthetic test idempotency identifiers from
    # the first queue commit. Current fixtures compose their keys at runtime; the
    # exact historical fingerprints remain ignored because this job scans full history.
    "a726658f0e0a94d3fb84857b3040ffa73c241d8f:tests/test_distribution_queue.py:generic-api-key:138",
    "a726658f0e0a94d3fb84857b3040ffa73c241d8f:tests/test_distribution_queue.py:generic-api-key:179",
    "d4d095ee13e576ee33747a0f64ae9b4a78237260:tests/test_affiliate_research_search.py:generic-api-key:83",
]


def test_gitleaks_allowlist_contains_only_exact_reviewed_fingerprints():
    entries = [
        line.strip()
        for line in Path(".gitleaksignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert entries == EXPECTED_REVIEWED_FALSE_POSITIVES


def test_gitleaks_allowlist_never_contains_wildcards_or_path_exclusions():
    entry = Path(".gitleaksignore").read_text(encoding="utf-8").strip()
    assert "*" not in entry
    assert any(line.startswith(("513bbaacd9441024ef191472c95dd80289c6ea31:", "439a3c39c374ad1d51bde0a8a5cb2f205b976e09:")) for line in entry.splitlines())
    assert all(":linkedin-client-id:68" in line for line in entry.splitlines() if "viral-post-writer/SKILL.md" in line)
