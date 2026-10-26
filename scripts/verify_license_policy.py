#!/usr/bin/env python3
"""Fail CI on missing license metadata or licenses requiring a legal review.

This is a conservative release gate, not legal advice. A package requiring an
exception must receive an explicitly reviewed, time-bound exception before it
is approved for distribution.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

UNKNOWN_LICENSES = {
    "", "unknown", "noassertion", "unlicensed", "none", "n/a", "not specified",
    "not specified in metadata", "license not specified",
}
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


def _unknown(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value).strip().lower()
    return normalized in UNKNOWN_LICENSES


def _blocked(value: str) -> bool:
    return any(pattern.search(value) for pattern in BLOCKED_PATTERNS)


def _python_findings(report: Path) -> tuple[int, list[str]]:
    payload = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{report}: expected pip-licenses JSON array")
    findings: list[str] = []
    for row in payload:
        if not isinstance(row, dict):
            findings.append(f"{report}: malformed package record")
            continue
        name = str(row.get("Name") or row.get("name") or "<unnamed>")
        version = str(row.get("Version") or row.get("version") or "?")
        license_value = row.get("License") or row.get("license")
        if isinstance(license_value, list):
            license_text = " OR ".join(str(item) for item in license_value)
        else:
            license_text = str(license_value or "").strip()
        identity = f"{name}@{version}"
        if _unknown(license_text):
            findings.append(f"{identity}: missing/unknown license metadata")
        elif _blocked(license_text):
            findings.append(f"{identity}: requires legal review (blocked license: {license_text})")
    return len(payload), findings


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
            continue
        license_obj = entry.get("license")
        if isinstance(license_obj, dict):
            value = license_obj.get("id") or license_obj.get("name")
            if value:
                result.append(str(value))
    return result


def _cyclonedx_findings(report: Path) -> tuple[int, list[str]]:
    payload = json.loads(report.read_text(encoding="utf-8"))
    if payload.get("bomFormat") != "CycloneDX":
        raise ValueError(f"{report}: expected a CycloneDX SBOM")
    components = payload.get("components")
    if not isinstance(components, list):
        raise ValueError(f"{report}: expected a components array")
    findings: list[str] = []
    for component in components:
        if not isinstance(component, dict):
            findings.append(f"{report}: malformed component record")
            continue
        name = str(component.get("name") or "<unnamed>")
        version = str(component.get("version") or "?")
        license_values = _component_license_strings(component)
        identity = f"{name}@{version}"
        if not license_values:
            findings.append(f"{identity}: missing/unknown license metadata")
            continue
        license_text = " OR ".join(license_values)
        if any(_unknown(value) for value in license_values):
            findings.append(f"{identity}: missing/unknown license metadata")
        elif _blocked(license_text):
            findings.append(f"{identity}: requires legal review (blocked license: {license_text})")
    return len(components), findings


def verify_reports(
    *,
    python_reports: list[Path] | None = None,
    cyclonedx_reports: list[Path] | None = None,
) -> tuple[int, list[str]]:
    total = 0
    findings: list[str] = []
    for report in python_reports or []:
        count, issues = _python_findings(report)
        total += count
        findings.extend(issues)
    for report in cyclonedx_reports or []:
        count, issues = _cyclonedx_findings(report)
        total += count
        findings.extend(issues)
    return total, findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-report", action="append", type=Path, default=[])
    parser.add_argument("--cyclonedx-report", action="append", type=Path, default=[])
    args = parser.parse_args(argv)
    if not args.python_report and not args.cyclonedx_report:
        parser.error("provide at least one --python-report or --cyclonedx-report")
    try:
        count, findings = verify_reports(
            python_reports=args.python_report,
            cyclonedx_reports=args.cyclonedx_report,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"License policy scan could not be completed: {exc}", file=sys.stderr)
        return 2
    if findings:
        for item in findings:
            print(f"LICENSE POLICY: {item}", file=sys.stderr)
        print(f"License policy failed: {len(findings)} finding(s) across {count} package(s).", file=sys.stderr)
        return 1
    print(f"License policy passed: {count} packages reviewed; no unknown or blocked licenses found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
