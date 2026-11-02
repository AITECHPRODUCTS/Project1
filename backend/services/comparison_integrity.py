from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_MANIFEST_FIELDS = (
    "source_id", "url", "product_names", "title", "status", "http_status",
    "content_type", "fetched_at", "excerpt_sha256", "error_type", "detail",
)
_EVIDENCE_PAYLOAD_FIELDS = (
    "asset_title", "source_urls", "topic", "audience", "affiliate_disclosure",
    "revision_number", "revision_of_asset_id", "revision_root_asset_id",
    "products", "decision_criteria", "comparison_table", "unknown_fact_count",
    "word_count", "minimum_word_target", "minimum_word_target_met", "evidence_status",
    "product_facts_independently_verified", "external_product_sources_fetched",
    "source_snapshots", "source_snapshot_manifest", "source_snapshot_manifest_sha256",
    "fact_evidence", "evidence_summary", "model_provider", "content_sha256", "publishing_started",
)


def sha256_text(value: str) -> str:
    """Return a lowercase SHA-256 digest for a persisted UTF-8 string."""
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_HASH_RE.fullmatch(value))


def build_source_snapshot_manifest(source_snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bind snapshot identity and metadata to its excerpt digest."""
    manifest: list[dict[str, Any]] = []
    for snapshot in source_snapshots:
        if not isinstance(snapshot, dict):
            manifest.append({"invalid_snapshot_record": True})
            continue
        item: dict[str, Any] = {}
        for field in _MANIFEST_FIELDS:
            value = snapshot.get(field)
            if field == "product_names":
                value = [str(name)[:120] for name in value] if isinstance(value, list) else []
            elif field == "http_status":
                value = value if isinstance(value, int) and not isinstance(value, bool) else None
            elif value is not None:
                value = str(value)[:2048]
            item[field] = value
        manifest.append(item)
    return manifest


def source_snapshot_manifest_sha256(manifest: list[dict[str, Any]]) -> str:
    """Hash a canonical, deterministic source snapshot manifest."""
    return hashlib.sha256(_canonical_json(manifest).encode("utf-8")).hexdigest()


def comparison_evidence_payload_sha256(metadata: dict[str, Any]) -> str:
    """Hash immutable, user-visible comparison facts/evidence.

    Mutable review history/status are excluded so an editorial decision does not invalidate the
    creation baseline. The asset title and source URLs mirror database columns and are copied into
    this metadata object by the API before verification.
    """
    payload = {field: metadata.get(field) for field in _EVIDENCE_PAYLOAD_FIELDS}
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def evaluate_comparison_integrity(
    body: str | None,
    metadata: dict[str, Any] | None,
    creation_audit_details: dict[str, Any] | None,
) -> dict[str, Any]:
    """Verify article, source snapshots and structured evidence against creation-time baselines.

    These checks detect application-level drift and partial stored-data changes. They are not a
    digital signature and cannot protect against an attacker who can rewrite every database record.
    """
    values = metadata if isinstance(metadata, dict) else {}
    body_digest = sha256_text(body or "")
    saved_body_digest = values.get("content_sha256")
    if not _is_sha256(saved_body_digest):
        content_status = "baseline_missing"
    elif not hmac.compare_digest(saved_body_digest, body_digest):
        content_status = "mismatch"
    else:
        content_status = "verified"

    snapshots_value = values.get("source_snapshots")
    manifest_value = values.get("source_snapshot_manifest")
    manifest_digest_value = values.get("source_snapshot_manifest_sha256")
    if not isinstance(snapshots_value, list) or not isinstance(manifest_value, list) or not _is_sha256(manifest_digest_value):
        source_status = "baseline_missing"
    else:
        current_manifest = build_source_snapshot_manifest(snapshots_value)
        manifest_json_matches = _canonical_json(current_manifest) == _canonical_json(manifest_value)
        manifest_hash_matches = hmac.compare_digest(
            manifest_digest_value,
            source_snapshot_manifest_sha256(manifest_value),
        )
        source_status = "verified" if manifest_json_matches and manifest_hash_matches else "mismatch"
        if source_status == "verified":
            for snapshot in snapshots_value:
                if not isinstance(snapshot, dict):
                    source_status = "mismatch"
                    break
                snapshot_status = snapshot.get("status")
                excerpt = snapshot.get("excerpt")
                excerpt = excerpt if isinstance(excerpt, str) else ""
                excerpt_digest = snapshot.get("excerpt_sha256")
                if snapshot_status == "fetched":
                    if not excerpt or not _is_sha256(excerpt_digest):
                        source_status = "mismatch"
                        break
                    if not hmac.compare_digest(excerpt_digest, sha256_text(excerpt)):
                        source_status = "mismatch"
                        break
                elif snapshot_status == "fetch_failed":
                    if excerpt or excerpt_digest is not None:
                        source_status = "mismatch"
                        break
                else:
                    source_status = "mismatch"
                    break

    saved_evidence_digest = values.get("evidence_payload_sha256")
    try:
        actual_evidence_digest = comparison_evidence_payload_sha256(values)
    except (TypeError, ValueError, OverflowError):
        actual_evidence_digest = None
    if not _is_sha256(saved_evidence_digest):
        evidence_status = "baseline_missing"
    elif not _is_sha256(actual_evidence_digest):
        evidence_status = "mismatch"
    elif not hmac.compare_digest(saved_evidence_digest, actual_evidence_digest):
        evidence_status = "mismatch"
    else:
        evidence_status = "verified"

    audit_details = creation_audit_details
    if not isinstance(audit_details, dict):
        content_status = "baseline_missing"
        source_status = "baseline_missing"
        evidence_status = "baseline_missing"
    else:
        audit_body_digest = audit_details.get("content_sha256")
        audit_manifest_digest = audit_details.get("source_snapshot_manifest_sha256")
        audit_evidence_digest = audit_details.get("evidence_payload_sha256")
        if not _is_sha256(audit_body_digest):
            content_status = "baseline_missing"
        elif not hmac.compare_digest(audit_body_digest, str(saved_body_digest or "")):
            content_status = "mismatch"
        if not _is_sha256(audit_manifest_digest):
            source_status = "baseline_missing"
        elif not hmac.compare_digest(audit_manifest_digest, str(manifest_digest_value or "")):
            source_status = "mismatch"
        if not _is_sha256(audit_evidence_digest):
            evidence_status = "baseline_missing"
        elif not hmac.compare_digest(audit_evidence_digest, str(saved_evidence_digest or "")):
            evidence_status = "mismatch"

    return {
        "actual_content_sha256": body_digest,
        "actual_evidence_payload_sha256": actual_evidence_digest,
        "content_integrity_status": content_status,
        "source_snapshot_integrity_status": source_status,
        "evidence_payload_integrity_status": evidence_status,
        "content_integrity_verified": content_status == "verified",
        "source_snapshot_integrity_verified": source_status == "verified",
        "evidence_payload_integrity_verified": evidence_status == "verified",
        "integrity_verified": (
            content_status == "verified"
            and source_status == "verified"
            and evidence_status == "verified"
        ),
    }

