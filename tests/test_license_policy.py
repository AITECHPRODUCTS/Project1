from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.verify_license_policy import verify_reports


def _python_report(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "licenses.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def _cyclonedx_report(tmp_path: Path, components: list[dict]) -> Path:
    path = tmp_path / "sbom.json"
    path.write_text(json.dumps({"bomFormat": "CycloneDX", "components": components}), encoding="utf-8")
    return path


@pytest.mark.parametrize("license_value", ["MIT License", "Apache Software License", "BSD-3-Clause", "ISC"])
def test_license_policy_accepts_permissive_python_licenses(tmp_path, license_value):
    report = _python_report(tmp_path, [{"Name": "sample", "Version": "1.0", "License": license_value}])
    count, findings = verify_reports(python_reports=[report])
    assert count == 1
    assert findings == []


@pytest.mark.parametrize(
    "license_value",
    [
        "GNU General Public License v3 (GPLv3)",
        "GNU Affero General Public License v3",
        "LGPL-2.1-only",
        "SSPL-1.0",
        "Business Source License 1.1",
        "Elastic License 2.0",
        "CC-BY-NC-4.0",
        "UNKNOWN",
        "",
    ],
)
def test_license_policy_rejects_unknown_or_review_required_python_licenses(tmp_path, license_value):
    report = _python_report(tmp_path, [{"Name": "sample", "Version": "1.0", "License": license_value}])
    count, findings = verify_reports(python_reports=[report])
    assert count == 1
    assert len(findings) == 1


def test_license_policy_checks_cyclonedx_license_expressions(tmp_path):
    report = _cyclonedx_report(
        tmp_path,
        [
            {"name": "permissive", "version": "1.0", "licenses": [{"license": {"id": "MIT"}}]},
            {"name": "copyleft", "version": "1.0", "licenses": [{"expression": "MIT OR GPL-3.0-only"}]},
        ],
    )
    count, findings = verify_reports(cyclonedx_reports=[report])
    assert count == 2
    assert len(findings) == 1
    assert "copyleft@1.0" in findings[0]


def test_license_policy_rejects_missing_cyclonedx_metadata(tmp_path):
    report = _cyclonedx_report(tmp_path, [{"name": "unlicensed-package", "version": "1.0"}])
    count, findings = verify_reports(cyclonedx_reports=[report])
    assert count == 1
    assert "missing/unknown license metadata" in findings[0]
