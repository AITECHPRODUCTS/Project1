from __future__ import annotations

import copy

from backend.services.comparison_integrity import (
    build_source_snapshot_manifest,
    evaluate_comparison_integrity,
    sha256_text,
    source_snapshot_manifest_sha256,
)


def _snapshot():
    excerpt = "Product Alpha price is $20 per month."
    return {
        "source_id": "S01",
        "url": "https://vendor.example/alpha",
        "product_names": ["Alpha"],
        "title": "Alpha pricing",
        "status": "fetched",
        "http_status": 200,
        "content_type": "text/html; charset=utf-8",
        "fetched_at": "2026-10-29T10:00:00+00:00",
        "excerpt": excerpt,
        "excerpt_sha256": sha256_text(excerpt),
        "error_type": None,
        "detail": None,
    }


def _metadata(body, snapshots=None):
    source_snapshots = snapshots if snapshots is not None else [_snapshot()]
    manifest = build_source_snapshot_manifest(source_snapshots)
    content_digest = sha256_text(body)
    manifest_digest = source_snapshot_manifest_sha256(manifest)
    metadata = {
        "content_sha256": content_digest,
        "source_snapshots": copy.deepcopy(source_snapshots),
        "source_snapshot_manifest": manifest,
        "source_snapshot_manifest_sha256": manifest_digest,
    }
    audit = {
        "content_sha256": content_digest,
        "source_snapshot_manifest_sha256": manifest_digest,
    }
    return metadata, audit


def test_comparison_integrity_accepts_unchanged_body_and_source_snapshot():
    body = "<article><h1>Alpha comparison</h1></article>"
    metadata, audit = _metadata(body)
    result = evaluate_comparison_integrity(body, metadata, audit)
    assert result["integrity_verified"] is True
    assert result["content_integrity_status"] == "verified"
    assert result["source_snapshot_integrity_status"] == "verified"


def test_comparison_integrity_detects_body_change_even_when_reviewer_loads_new_hash():
    original_body = "<article><h1>Alpha comparison</h1></article>"
    metadata, audit = _metadata(original_body)
    changed_body = original_body + "<p>Changed after persistence</p>"
    result = evaluate_comparison_integrity(changed_body, metadata, audit)
    assert result["actual_content_sha256"] == sha256_text(changed_body)
    assert result["content_integrity_status"] == "mismatch"
    assert result["source_snapshot_integrity_status"] == "verified"
    assert result["integrity_verified"] is False


def test_comparison_integrity_detects_snapshot_excerpt_change():
    body = "<article><h1>Alpha comparison</h1></article>"
    metadata, audit = _metadata(body)
    metadata["source_snapshots"][0]["excerpt"] += " injected text"
    result = evaluate_comparison_integrity(body, metadata, audit)
    assert result["content_integrity_status"] == "verified"
    assert result["source_snapshot_integrity_status"] == "mismatch"
    assert result["integrity_verified"] is False


def test_comparison_integrity_detects_snapshot_identity_change():
    body = "<article><h1>Alpha comparison</h1></article>"
    metadata, audit = _metadata(body)
    metadata["source_snapshots"][0]["url"] = "https://attacker.example/changed-source"
    result = evaluate_comparison_integrity(body, metadata, audit)
    assert result["source_snapshot_integrity_status"] == "mismatch"


def test_comparison_integrity_fails_closed_for_legacy_unbound_drafts():
    result = evaluate_comparison_integrity("<article>old</article>", {}, None)
    assert result["content_integrity_status"] == "baseline_missing"
    assert result["source_snapshot_integrity_status"] == "baseline_missing"
    assert result["integrity_verified"] is False


def test_comparison_integrity_checks_creation_audit_binding():
    body = "<article><h1>Alpha comparison</h1></article>"
    metadata, audit = _metadata(body)
    audit["content_sha256"] = "f" * 64
    result = evaluate_comparison_integrity(body, metadata, audit)
    assert result["content_integrity_status"] == "mismatch"
    assert result["integrity_verified"] is False
