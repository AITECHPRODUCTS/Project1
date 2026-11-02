from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path("knowledge/affiliate-skills/upstream/SOURCE_MANIFEST.json")
REGISTRY_PATH = Path("knowledge/affiliate-skills/upstream/registry.json")
MATRIX_PATH = Path("docs/skill-parity-matrix.csv")
STATUS_PATH = Path("docs/IMPLEMENTATION_STATUS.md")
EXPECTED_ARCHIVE_SHA256 = "dc463b31d80d6917142d99d9bc7f7b19385e8e0c74ff5c0cc57f4410ed73e1a6"


def git_blob_sha(content: bytes) -> str:
    """Return the SHA-1 Git uses for a blob, including the type/length header."""
    header = b"blob " + str(len(content)).encode("ascii") + b"\0"
    return hashlib.sha1(header + content).hexdigest()


def read_skill_matrix(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        expected = {"skill_id", "stage", "status", "evidence", "gap"}
        if set(reader.fieldnames or []) != expected:
            raise ValueError(f"skill matrix columns must be {sorted(expected)}")
        rows = list(reader)
    if any(not row.get("skill_id") or not row.get("status") for row in rows):
        raise ValueError("skill matrix contains an empty skill_id/status row")
    return rows


def readme_skill_claim(text: str) -> int | None:
    match = re.search(r"8 Stages,\s*(\d+)\s*Skills", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def verify_skill_registry(root: Path = ROOT) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    notes: list[str] = []
    summary: dict[str, Any] = {}
    manifest_path = root / MANIFEST_PATH
    registry_path = root / REGISTRY_PATH
    matrix_path = root / MATRIX_PATH
    status_path = root / STATUS_PATH

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read pinned source manifest: {exc}"], notes, summary

    if manifest.get("source_repository") != "https://github.com/Affitor/affiliate-skills":
        errors.append("unexpected upstream skill source repository")
    if manifest.get("source_commit") != "f4cb063a0ee83b1b9e5167e396ab46cc9123dadc":
        errors.append("upstream skill source commit is not the pinned revision")
    if manifest.get("archive_sha256") != EXPECTED_ARCHIVE_SHA256:
        errors.append("upstream source archive hash does not match the pinned archive")
    if manifest.get("license") != "MIT":
        errors.append("upstream skill source must retain the MIT license record")

    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry_skills = registry["skills"]
        if not isinstance(registry_skills, list):
            raise ValueError("registry skills is not a list")
    except (OSError, KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
        return errors + [f"cannot read pinned upstream registry: {exc}"], notes, summary

    registry_slugs = [str(skill.get("slug", "")) for skill in registry_skills]
    if len(registry_skills) != 53:
        errors.append(f"pinned upstream registry must contain 53 skills; found {len(registry_skills)}")
    if len(set(registry_slugs)) != len(registry_slugs) or any(not slug for slug in registry_slugs):
        errors.append("pinned upstream registry contains empty or duplicate slugs")

    manifest_skills = manifest.get("skill_rows", [])
    manifest_slugs = [str(skill.get("slug", "")) for skill in manifest_skills]
    if len(manifest_skills) != 53 or set(manifest_slugs) != set(registry_slugs):
        errors.append("pinned source manifest does not match all 53 registry skills")

    vendored_files = manifest.get("vendored_files", [])
    manifest_targets = [str(item.get("target_path", "")) for item in vendored_files]
    if len(vendored_files) != 72:
        errors.append(f"source manifest should pin 72 files; found {len(vendored_files)}")
    if len(set(manifest_targets)) != len(manifest_targets):
        errors.append("source manifest contains duplicate target paths")
    for item in vendored_files:
        target = str(item.get("target_path", ""))
        expected_sha = str(item.get("upstream_git_blob_sha", ""))
        if not target or target.startswith("/") or ".." in Path(target).parts:
            errors.append(f"unsafe source-manifest target path: {target!r}")
            continue
        file_path = root / target
        try:
            raw = file_path.read_bytes()
        except OSError:
            errors.append(f"vendored upstream source file is missing: {target}")
            continue
        if len(raw) != item.get("size_bytes"):
            errors.append(f"vendored source file size differs from upstream: {target}")
        if git_blob_sha(raw) != expected_sha:
            errors.append(f"vendored source file does not match pinned Git blob: {target}")

    try:
        matrix_rows = read_skill_matrix(matrix_path)
    except (OSError, ValueError, csv.Error) as exc:
        errors.append(f"cannot parse runtime skill matrix: {exc}")
        matrix_rows = []
    matrix_ids = [row["skill_id"] for row in matrix_rows]
    matrix_slugs = [skill_id.rsplit("/", 1)[-1] for skill_id in matrix_ids]
    if len(matrix_rows) != 53:
        errors.append(f"runtime skill matrix must contain 53 rows; found {len(matrix_rows)}")
    if len(set(matrix_ids)) != len(matrix_ids):
        errors.append("runtime skill matrix contains duplicate skill IDs")
    if set(matrix_slugs) != set(registry_slugs):
        missing = sorted(set(registry_slugs) - set(matrix_slugs))
        unknown = sorted(set(matrix_slugs) - set(registry_slugs))
        errors.append(f"runtime matrix/registry slug mismatch; missing={missing}, unknown={unknown}")

    status_counts = Counter(row["status"] for row in matrix_rows)
    for row in registry_skills:
        slug = str(row.get("slug", ""))
        source_path = str(row.get("path", ""))
        expected_target = f"knowledge/affiliate-skills/upstream/{source_path}/SKILL.md"
        if not source_path.startswith("skills/") or not source_path.endswith(slug):
            errors.append(f"registry path does not align with its slug: {slug}")
        manifest_row = next((item for item in manifest_skills if item.get("slug") == slug), None)
        if not manifest_row or manifest_row.get("target_path") != expected_target:
            errors.append(f"manifest does not map registry skill to its pinned SKILL.md: {slug}")

    try:
        status_text = status_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"implementation status ledger unavailable: {exc}")
    else:
        match = re.search(
            r"Current matrix is (\d+) partial and (\d+) not implemented, (\d+) fully implemented end-to-end",
            status_text,
        )
        if not match:
            errors.append("implementation status lacks the canonical 53-skill count summary")
        else:
            recorded = tuple(int(value) for value in match.groups())
            actual = (
                status_counts.get("partial", 0),
                status_counts.get("not_implemented", 0),
                status_counts.get("implemented", 0),
            )
            if recorded != actual:
                errors.append(f"status summary {recorded} does not match CSV counts {actual}")

    claimed = manifest.get("upstream_readme_claimed_skill_count")
    actual_registry = len(registry_skills)
    if claimed is not None and int(claimed) != actual_registry:
        notes.append(
            f"Upstream README says {claimed} skills, while pinned registry and skill filesystem contain "
            f"{actual_registry}; registry/filesystem count is authoritative."
        )

    summary = {
        "source_skills": len(registry_skills),
        "matrix_rows": len(matrix_rows),
        "status_counts": dict(sorted(status_counts.items())),
        "vendored_files_checked": len(vendored_files),
    }
    return errors, notes, summary


def main() -> int:
    errors, notes, summary = verify_skill_registry()
    if errors:
        print("SKILL SOURCE / PARITY GUARD FAILED")
        for error in errors:
            print(f"- {error}")
        for note in notes:
            print(f"NOTE: {note}")
        return 1
    print("SKILL SOURCE / PARITY GUARD PASSED")
    print(f"Upstream skills pinned: {summary['source_skills']}")
    print(f"Runtime matrix rows: {summary['matrix_rows']}")
    print(f"Vendored source blobs verified: {summary['vendored_files_checked']}")
    print(f"Runtime skill statuses: {summary['status_counts']}")
    for note in notes:
        print(f"NOTE: {note}")
    print("Source presence and parity are separate from end-to-end capability implementation/provider connection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
