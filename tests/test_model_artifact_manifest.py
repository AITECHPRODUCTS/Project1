from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.verify_model_artifact_manifest import (
    ArtifactManifestError,
    artifact_tree_sha256,
    verify_model_artifact_manifest,
)

APPLICATION_SHA = "a" * 40
HUB_REVISION = "b" * 40


def _write_fixture(tmp_path: Path):
    root = tmp_path / "staged-models"
    model = root / "embedding"
    model.mkdir(parents=True)
    (model / "config.json").write_text('{"model_type":"fixture"}', encoding="utf-8")
    (model / "weights.bin").write_bytes(b"fixture-weights")
    manifest = {
        "schema_version": 1,
        "application_sha": APPLICATION_SHA,
        "artifacts": [{
            "name": "embedding-model",
            "kind": "embedding",
            "source": "huggingface_hub",
            "model_id": "example/approved-embedding",
            "revision": HUB_REVISION,
            "path": "embedding",
            "artifact_sha256": artifact_tree_sha256(model),
            "license_id": "Apache-2.0",
            "license_review_status": "approved",
            "license_reviewed_by": "release-reviewer",
            "license_reviewed_at": "2026-10-26T10:00:00Z",
            "acquired_by": "artifact-builder",
            "acquired_at": "2026-10-25T09:30:00Z",
            "local_files_only": True,
            "trust_remote_code": False,
        }],
    }
    manifest_path = tmp_path / "model-artifact-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path, root, manifest


def test_manifest_verifies_pinned_and_license_approved_staged_artifact(tmp_path):
    manifest_path, root, _ = _write_fixture(tmp_path)
    report = verify_model_artifact_manifest(manifest_path, root, APPLICATION_SHA)
    assert report["verified"] is True
    assert report["application_sha"] == APPLICATION_SHA
    assert report["artifact_count"] == 1
    assert report["artifacts"][0]["revision"] == HUB_REVISION
    assert report["artifacts"][0]["verified"] is True
    assert len(report["manifest_sha256"]) == 64


def test_manifest_must_match_exact_deployment_application_sha(tmp_path):
    manifest_path, root, _ = _write_fixture(tmp_path)
    with pytest.raises(ArtifactManifestError, match="does not match the deployment SHA"):
        verify_model_artifact_manifest(manifest_path, root, "c" * 40)


def test_manifest_rejects_mutable_hub_revision(tmp_path):
    manifest_path, root, manifest = _write_fixture(tmp_path)
    manifest["artifacts"][0]["revision"] = "main"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ArtifactManifestError, match="immutable 40-character Hub commit SHA"):
        verify_model_artifact_manifest(manifest_path, root, APPLICATION_SHA)


def test_manifest_rejects_artifact_digest_drift(tmp_path):
    manifest_path, root, manifest = _write_fixture(tmp_path)
    (root / "embedding" / "weights.bin").write_bytes(b"tampered-weights")
    with pytest.raises(ArtifactManifestError, match="artifact digest mismatch"):
        verify_model_artifact_manifest(manifest_path, root, APPLICATION_SHA)


def test_manifest_requires_approved_license(tmp_path):
    manifest_path, root, manifest = _write_fixture(tmp_path)
    manifest["artifacts"][0]["license_review_status"] = "pending"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ArtifactManifestError, match="must be 'approved'"):
        verify_model_artifact_manifest(manifest_path, root, APPLICATION_SHA)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("local_files_only", False, "local_files_only must be true"),
        ("trust_remote_code", True, "trust_remote_code must be false"),
    ],
)
def test_manifest_fails_closed_on_unsafe_runtime_flags(tmp_path, field, value, message):
    manifest_path, root, manifest = _write_fixture(tmp_path)
    manifest["artifacts"][0][field] = value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ArtifactManifestError, match=message):
        verify_model_artifact_manifest(manifest_path, root, APPLICATION_SHA)


def test_manifest_rejects_path_traversal(tmp_path):
    manifest_path, root, manifest = _write_fixture(tmp_path)
    manifest["artifacts"][0]["path"] = "../outside"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ArtifactManifestError, match="must remain relative"):
        verify_model_artifact_manifest(manifest_path, root, APPLICATION_SHA)


def test_artifact_tree_hash_rejects_symlinks(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    (model / "weights.bin").write_bytes(b"weights")
    try:
        (model / "linked-weights.bin").symlink_to(model / "weights.bin")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available on this test platform")
    with pytest.raises(ArtifactManifestError, match="must not contain symlinks"):
        artifact_tree_sha256(model)


def test_manifest_requires_timezone_aware_provenance_timestamps(tmp_path):
    manifest_path, root, manifest = _write_fixture(tmp_path)
    manifest["artifacts"][0]["acquired_at"] = "2026-10-25T09:30:00"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ArtifactManifestError, match="must include a UTC offset"):
        verify_model_artifact_manifest(manifest_path, root, APPLICATION_SHA)


def test_manifest_rejects_duplicate_artifact_names(tmp_path):
    manifest_path, root, manifest = _write_fixture(tmp_path)
    duplicate = dict(manifest["artifacts"][0])
    duplicate["name"] = "EMBEDDING-MODEL"
    manifest["artifacts"].append(duplicate)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ArtifactManifestError, match="duplicate artifact name"):
        verify_model_artifact_manifest(manifest_path, root, APPLICATION_SHA)
