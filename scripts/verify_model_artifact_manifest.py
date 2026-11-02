from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_KINDS = {"embedding", "causal_lm", "lora_adapter"}
_ALLOWED_SOURCES = {"huggingface_hub", "operator_local"}


class ArtifactManifestError(ValueError):
    """A model-artifact release manifest failed a fail-closed validation."""


def _require_string(record: dict[str, Any], key: str, where: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ArtifactManifestError(f"{where}.{key} must be a non-empty string")
    return value.strip()


def _require_timestamp(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ArtifactManifestError(f"{field} must be an ISO-8601 timestamp with timezone") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ArtifactManifestError(f"{field} must include a UTC offset or Z timezone")


def artifact_tree_sha256(directory: str | Path) -> str:
    """Hash a materialized directory deterministically; reject symlinks and special files."""
    root_arg = Path(directory)
    if root_arg.is_symlink():
        raise ArtifactManifestError("artifact directory must not be a symlink")
    try:
        root = root_arg.resolve(strict=True)
    except OSError as exc:
        raise ArtifactManifestError("artifact directory does not exist") from exc
    if not root.is_dir():
        raise ArtifactManifestError("artifact path must be a directory")

    files: list[Path] = []
    try:
        entries = sorted(root.rglob("*"), key=lambda path: path.relative_to(root).as_posix())
        for entry in entries:
            if entry.is_symlink():
                raise ArtifactManifestError("artifact trees must be materialized and must not contain symlinks")
            if entry.is_file():
                files.append(entry)
            elif not entry.is_dir():
                raise ArtifactManifestError("artifact tree contains a non-regular file")
    except OSError as exc:
        raise ArtifactManifestError("could not enumerate artifact directory") from exc
    if not files:
        raise ArtifactManifestError("artifact directory contains no files")

    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        file_digest = hashlib.sha256()
        size = 0
        try:
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    file_digest.update(chunk)
        except OSError as exc:
            raise ArtifactManifestError("could not read a file in the artifact tree") from exc
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(size.to_bytes(8, "big"))
        digest.update(file_digest.digest())
    return digest.hexdigest()


def _resolve_artifact_path(root: Path, value: str, name: str) -> Path:
    if "\\" in value:
        raise ArtifactManifestError(f"artifact {name!r} path must use POSIX separators")
    relative = PurePosixPath(value)
    if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ArtifactManifestError(f"artifact {name!r} path must remain relative to artifact_root")
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ArtifactManifestError(f"artifact {name!r} path must not traverse symlinks")
    try:
        resolved = cursor.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ArtifactManifestError(f"artifact {name!r} path is missing or escapes artifact_root") from exc
    if not resolved.is_dir():
        raise ArtifactManifestError(f"artifact {name!r} path must point to a directory")
    return resolved


def verify_model_artifact_manifest(
    manifest_path: str | Path,
    artifact_root: str | Path,
    expected_application_sha: str,
) -> dict[str, Any]:
    """Validate a release manifest against real staged directories and application SHA."""
    target_sha = str(expected_application_sha).strip().lower()
    if not _SHA1.fullmatch(target_sha):
        raise ArtifactManifestError("expected application SHA must be a 40-character commit SHA")

    try:
        raw_manifest = Path(manifest_path).read_bytes()
        manifest = json.loads(raw_manifest)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactManifestError("manifest must be readable UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise ArtifactManifestError("manifest root must be a JSON object")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ArtifactManifestError("schema_version must be integer 1")

    application_sha = _require_string(manifest, "application_sha", "manifest").lower()
    if not _SHA1.fullmatch(application_sha):
        raise ArtifactManifestError("manifest.application_sha must be a 40-character commit SHA")
    if application_sha != target_sha:
        raise ArtifactManifestError("manifest application_sha does not match the deployment SHA")

    root_arg = Path(artifact_root)
    if root_arg.is_symlink():
        raise ArtifactManifestError("artifact_root must not be a symlink")
    try:
        root = root_arg.resolve(strict=True)
    except OSError as exc:
        raise ArtifactManifestError("artifact_root does not exist") from exc
    if not root.is_dir():
        raise ArtifactManifestError("artifact_root must be a directory")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ArtifactManifestError("manifest.artifacts must be a non-empty list")

    verified: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for index, item in enumerate(artifacts):
        where = f"manifest.artifacts[{index}]"
        if not isinstance(item, dict):
            raise ArtifactManifestError(f"{where} must be an object")
        name = _require_string(item, "name", where)
        if name.casefold() in seen_names:
            raise ArtifactManifestError(f"duplicate artifact name: {name}")
        seen_names.add(name.casefold())

        kind = _require_string(item, "kind", where)
        if kind not in _ALLOWED_KINDS:
            raise ArtifactManifestError(f"{where}.kind must be one of {sorted(_ALLOWED_KINDS)}")
        source = _require_string(item, "source", where)
        if source not in _ALLOWED_SOURCES:
            raise ArtifactManifestError(f"{where}.source must be one of {sorted(_ALLOWED_SOURCES)}")
        model_id = _require_string(item, "model_id", where)
        revision = item.get("revision")
        if source == "huggingface_hub":
            if not isinstance(revision, str) or not _SHA1.fullmatch(revision.strip().lower()):
                raise ArtifactManifestError(f"{where}.revision must be an immutable 40-character Hub commit SHA")
            revision = revision.strip().lower()
        elif revision not in (None, ""):
            if not isinstance(revision, str) or not _SHA1.fullmatch(revision.strip().lower()):
                raise ArtifactManifestError(f"{where}.revision must be empty or an immutable 40-character commit SHA")
            revision = revision.strip().lower()

        expected_digest = _require_string(item, "artifact_sha256", where).lower()
        if not _SHA256.fullmatch(expected_digest):
            raise ArtifactManifestError(f"{where}.artifact_sha256 must be a 64-character SHA-256 digest")

        _require_string(item, "license_id", where)
        review_status = _require_string(item, "license_review_status", where).lower()
        if review_status != "approved":
            raise ArtifactManifestError(f"{where}.license_review_status must be 'approved'")
        _require_string(item, "license_reviewed_by", where)
        _require_timestamp(_require_string(item, "license_reviewed_at", where), f"{where}.license_reviewed_at")
        _require_string(item, "acquired_by", where)
        _require_timestamp(_require_string(item, "acquired_at", where), f"{where}.acquired_at")

        if item.get("local_files_only") is not True:
            raise ArtifactManifestError(f"{where}.local_files_only must be true")
        if item.get("trust_remote_code") is not False:
            raise ArtifactManifestError(f"{where}.trust_remote_code must be false")

        relative_path = _require_string(item, "path", where)
        artifact_path = _resolve_artifact_path(root, relative_path, name)
        actual_digest = artifact_tree_sha256(artifact_path)
        if actual_digest != expected_digest:
            raise ArtifactManifestError(f"artifact digest mismatch for {name!r}")

        verified.append({
            "name": name,
            "kind": kind,
            "model_id": model_id,
            "source": source,
            "revision": revision,
            "path": relative_path,
            "artifact_sha256": actual_digest,
            "license_id": _require_string(item, "license_id", where),
            "license_review_status": review_status,
            "verified": True,
        })

    return {
        "verified": True,
        "schema_version": 1,
        "application_sha": application_sha,
        "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        "artifact_count": len(verified),
        "artifacts": verified,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed gate for staged, pinned model artifacts.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--application-sha", required=True)
    parser.add_argument("--report-out", type=Path)
    args = parser.parse_args(argv)

    try:
        report = verify_model_artifact_manifest(args.manifest, args.artifact_root, args.application_sha)
    except ArtifactManifestError as exc:
        report = {"verified": False, "error": str(exc)}
        print(f"MODEL ARTIFACT RELEASE GATE FAILED: {exc}", file=sys.stderr)
        if args.report_out:
            args.report_out.parent.mkdir(parents=True, exist_ok=True)
            args.report_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 1

    serialized = json.dumps(report, indent=2, sort_keys=True)
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    print("MODEL ARTIFACT RELEASE GATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
