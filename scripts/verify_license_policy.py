#!/usr/bin/env python3
"""Report dependency licenses and fail on unknown or unreviewed restricted licenses.

Narrow, time-bounded exceptions keep CI inventory reporting available, but are
always marked release blockers. They are not legal clearance.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

UNKNOWN_LICENSES = {"", "unknown", "noassertion", "unlicensed", "none", "n/a",
                    "not specified", "not specified in metadata", "license not specified"}
BLOCKED_PATTERNS = (
    re.compile(r"\bGNU\s+Affero\s+General\s+Public\s+License\b", re.I),
    re.compile(r"\bAffero\s+General\s+Public\s+License\b", re.I),
    re.compile(r"\bGNU\s+Lesser\s+General\s+Public\s+License\b", re.I),
    re.compile(r"\bGNU\s+General\s+Public\s+License\b", re.I),
    re.compile(r"(?<![A-Z])(?:AGPL|LGPL|GPL)(?:[- ]?v?\d+(?:\.\d+)*(?:[-+][A-Za-z0-9.]+)?|[- ]\d+(?:\.\d+)*)\b", re.I),
    re.compile(r"\b(?:AGPL|LGPL|GPL)\b", re.I),
    re.compile(r"\b(?:SSPL|Server\s+Side\s+Public\s+License)\b", re.I),
    re.compile(r"\bElastic\s+License\b", re.I),
    re.compile(r"\bBusiness\s+Source\s+License\b", re.I),
    re.compile(r"\bCommons\s+Clause\b", re.I),
    re.compile(r"\bCC\s*[- ]?BY\s*[- ]?NC(?:[- ]?\w+)?\b", re.I),
    re.compile(r"Creative\s+Commons\s+Attribution.NonCommercial", re.I),
    re.compile(r"\bProprietary\b", re.I),
)


def _normalized_license(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _unknown(value: str) -> bool:
    return _normalized_license(value) in UNKNOWN_LICENSES


def _blocked(value: str) -> bool:
    return any(pattern.search(value) for pattern in BLOCKED_PATTERNS)


def _load_exceptions(path: Path | None, *, build_inventory_only: bool = False) -> dict[tuple[str, str, str], dict[str, Any]]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("policy_version") != 1:
        raise ValueError(f"{path}: expected license exception policy_version=1")
    entries = payload.get("exceptions")
    if not isinstance(entries, list):
        raise ValueError(f"{path}: expected exceptions array")
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    today = datetime.now(timezone.utc).date()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: malformed license exception")
        required = ("package", "version", "license", "status", "expires", "reason")
        if any(not str(entry.get(key) or "").strip() for key in required):
            raise ValueError(f"{path}: every exception needs {', '.join(required)}")
        if entry["status"] not in {"temporary-release-blocker", "temporary-build-inventory-only"}:
            raise ValueError(f"{path}: unsupported license exception status")
        if entry["status"] == "temporary-build-inventory-only":
            if entry.get("scope") != "frontend-build-only" or entry.get("excluded_from_production") is not True:
                raise ValueError(
                    f"{path}: build-only exception must declare scope=frontend-build-only "
                    "and excluded_from_production=true"
                )
        try:
            expires = date.fromisoformat(str(entry["expires"]))
        except ValueError as exc:
            raise ValueError(f"{path}: invalid ISO exception expiry") from exc
        if today > expires:
            raise ValueError(f"{path}: expired license exception for {entry['package']}@{entry['version']}")
        key = (str(entry["package"]), str(entry["version"]), _normalized_license(str(entry["license"])))
        if key in result:
            raise ValueError(f"{path}: duplicate exception for {key[0]}@{key[1]}")
        result[key] = entry
    return result


def _matches_exception(name: str, version: str, licenses: list[str],
                       exceptions: dict[tuple[str, str, str], dict[str, Any]],
                       *, build_inventory_only: bool = False) -> dict[str, Any] | None:
    # Exact package + exact version + exact single license; never a license-family/path waiver.
    if len(licenses) != 1 or _unknown(licenses[0]):
        return None
    entry = exceptions.get((name, version, _normalized_license(licenses[0])))
    if entry and entry["status"] == "temporary-build-inventory-only" and not build_inventory_only:
        return None
    return entry


def _exception_notice(name: str, version: str, entry: dict[str, Any]) -> str:
    if entry["status"] == "temporary-build-inventory-only":
        return (
            f"{name}@{version}: {entry['license']} is a BUILD-ONLY INVENTORY NOTICE until "
            f"{entry['expires']}; excluded_from_production=true. This exception is valid only "
            "for a full install/build SBOM and never for the production SBOM. "
            f"Reason: {entry['reason']}"
        )
    return (f"{name}@{version}: {entry['license']} has a temporary CI-inventory exception "
            f"until {entry['expires']}; RELEASE BLOCKED pending legal review. Reason: {entry['reason']}")


def _python_findings(report: Path, exceptions: dict[tuple[str, str, str], dict[str, Any]],
                     *, build_inventory_only: bool = False
                     ) -> tuple[int, list[str], list[str]]:
    payload = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{report}: expected pip-licenses JSON array")
    findings: list[str] = []
    notices: list[str] = []
    for row in payload:
        if not isinstance(row, dict):
            findings.append(f"{report}: malformed package record")
            continue
        name = str(row.get("Name") or row.get("name") or "<unnamed>")
        version = str(row.get("Version") or row.get("version") or "?")
        raw = row.get("License") or row.get("license")
        licenses = [str(item).strip() for item in raw] if isinstance(raw, list) else [str(raw or "").strip()]
        identity = f"{name}@{version}"
        license_text = " OR ".join(licenses)
        if _unknown(license_text):
            findings.append(f"{identity}: missing/unknown license metadata")
        elif _blocked(license_text):
            exception = _matches_exception(
                name, version, licenses, exceptions, build_inventory_only=build_inventory_only
            )
            if exception:
                notices.append(_exception_notice(name, version, exception))
            else:
                findings.append(f"{identity}: requires legal review (blocked license: {license_text})")
    return len(payload), findings, notices


def _component_license_strings(component: dict[str, Any]) -> list[str]:
    licenses = component.get("licenses")
    result: list[str] = []
    if not isinstance(licenses, list):
        return result
    for entry in licenses:
        if not isinstance(entry, dict):
            continue
        expression = entry.get("expression")
        if expression:
            result.append(str(expression))
        else:
            obj = entry.get("license")
            if isinstance(obj, dict):
                value = obj.get("id") or obj.get("name")
                if value:
                    result.append(str(value))
    return result


def _cyclonedx_findings(report: Path, exceptions: dict[tuple[str, str, str], dict[str, Any]],
                        *, build_inventory_only: bool = False
                        ) -> tuple[int, list[str], list[str]]:
    payload = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("bomFormat") != "CycloneDX":
        raise ValueError(f"{report}: expected a CycloneDX SBOM")
    components = payload.get("components")
    if not isinstance(components, list):
        raise ValueError(f"{report}: expected components array")
    findings: list[str] = []
    notices: list[str] = []
    for component in components:
        if not isinstance(component, dict):
            findings.append(f"{report}: malformed component record")
            continue
        name = str(component.get("name") or "<unnamed>")
        version = str(component.get("version") or "?")
        licenses = _component_license_strings(component)
        identity = f"{name}@{version}"
        if not licenses or any(_unknown(value) for value in licenses):
            findings.append(f"{identity}: missing/unknown license metadata")
            continue
        license_text = " OR ".join(licenses)
        if _blocked(license_text):
            exception = _matches_exception(name, version, licenses, exceptions, build_inventory_only=build_inventory_only)
            if exception:
                notices.append(_exception_notice(name, version, exception))
            else:
                findings.append(f"{identity}: requires legal review (blocked license: {license_text})")
    return len(components), findings, notices


def verify_reports(*, python_reports: list[Path] | None = None,
                   cyclonedx_reports: list[Path] | None = None,
                   exception_policy: Path | None = None,
                   build_inventory_only: bool = False
                   ) -> tuple[int, list[str], list[str]]:
    exceptions = _load_exceptions(exception_policy, build_inventory_only=build_inventory_only)
    total, findings, notices = 0, [], []
    for report in python_reports or []:
        count, issues, warnings = _python_findings(
            report, exceptions, build_inventory_only=build_inventory_only
        )
        total += count
        findings.extend(issues)
        notices.extend(warnings)
    for report in cyclonedx_reports or []:
        count, issues, warnings = _cyclonedx_findings(
            report, exceptions, build_inventory_only=build_inventory_only
        )
        total += count
        findings.extend(issues)
        notices.extend(warnings)
    return total, findings, notices


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-report", action="append", type=Path, default=[])
    parser.add_argument("--cyclonedx-report", action="append", type=Path, default=[])
    parser.add_argument("--exceptions", type=Path)
    parser.add_argument(
        "--build-inventory-only",
        action="store_true",
        help="Scope exception policy to a full build/install inventory; never use this mode for production SBOM approval.",
    )
    parser.add_argument("--report-output", type=Path)
    args = parser.parse_args(argv)
    if not args.python_report and not args.cyclonedx_report:
        parser.error("provide at least one --python-report or --cyclonedx-report")
    try:
        count, findings, notices = verify_reports(
            python_reports=args.python_report,
            cyclonedx_reports=args.cyclonedx_report,
            exception_policy=args.exceptions,
            build_inventory_only=args.build_inventory_only,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"License policy scan could not be completed: {exc}", file=sys.stderr)
        return 2
    release_blockers = [notice for notice in notices if "RELEASE BLOCKED pending legal review" in notice]
    build_only_notices = [notice for notice in notices if "BUILD-ONLY INVENTORY NOTICE" in notice]
    summary = {
        "commit_sha": os.environ.get("GITHUB_SHA", "local"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inventory_scope": "build-install-only" if args.build_inventory_only else "production-or-unspecified",
        "packages_reviewed": count,
        "findings": findings,
        "temporary_exceptions_release_blockers": release_blockers,
        "build_inventory_only_notices": build_only_notices,
        "release_approved": None if args.build_inventory_only else not findings and not release_blockers,
    }
    if args.report_output:
        try:
            args.report_output.parent.mkdir(parents=True, exist_ok=True)
            args.report_output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"License policy report could not be written: {exc}", file=sys.stderr)
            return 2
    for notice in notices:
        if "BUILD-ONLY INVENTORY NOTICE" in notice:
            print(f"LICENSE INVENTORY (BUILD ONLY): {notice}")
        else:
            print(f"LICENSE EXCEPTION (RELEASE BLOCKER): {notice}", file=sys.stderr)
    if findings:
        for item in findings:
            print(f"LICENSE POLICY: {item}", file=sys.stderr)
        print(f"License policy failed: {len(findings)} finding(s) across {count} package(s).", file=sys.stderr)
        return 1
    if release_blockers:
        print(f"License inventory completed for {count} packages with {len(release_blockers)} release blocker(s); release_approved=false.", file=sys.stderr)
    elif args.build_inventory_only and build_only_notices:
        print(
            f"Build/install inventory reviewed {count} packages; {len(build_only_notices)} explicitly scoped build-only notice(s). "
            "Production approval is indeterminate in this report and must be checked against a separate production SBOM without exceptions."
        )
    elif notices:
        print(f"License inventory completed for {count} packages with {len(notices)} notice(s).")
    else:
        print(f"License policy passed: {count} packages reviewed; no unknown or blocked licenses found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
