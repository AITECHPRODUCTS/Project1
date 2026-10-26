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
    count, findings, notices = verify_reports(python_reports=[report])
    assert count == 1
    assert findings == []
    assert notices == []


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
    count, findings, notices = verify_reports(python_reports=[report])
    assert count == 1
    assert len(findings) == 1
    assert notices == []


def test_license_policy_checks_cyclonedx_license_expressions(tmp_path):
    report = _cyclonedx_report(
        tmp_path,
        [
            {"name": "permissive", "version": "1.0", "licenses": [{"license": {"id": "MIT"}}]},
            {"name": "copyleft", "version": "1.0", "licenses": [{"expression": "MIT OR GPL-3.0-only"}]},
        ],
    )
    count, findings, notices = verify_reports(cyclonedx_reports=[report])
    assert count == 2
    assert len(findings) == 1
    assert "copyleft@1.0" in findings[0]
    assert notices == []


def test_license_policy_rejects_missing_cyclonedx_metadata(tmp_path):
    report = _cyclonedx_report(tmp_path, [{"name": "unlicensed-package", "version": "1.0"}])
    count, findings, notices = verify_reports(cyclonedx_reports=[report])
    assert count == 1
    assert "missing/unknown license metadata" in findings[0]
    assert notices == []


def test_time_bounded_exception_only_allows_exact_package_version_license(tmp_path: Path):
    report = _cyclonedx_report(
        tmp_path,
        [
            {"name": "@img/sharp-libvips-linux-x64", "version": "1.3.4",
             "licenses": [{"expression": "LGPL-3.0-or-later"}]},
            {"name": "@img/sharp-libvips-linux-x64", "version": "1.3.5",
             "licenses": [{"expression": "LGPL-3.0-or-later"}]},
            {"name": "unrelated-package", "version": "1.3.4",
             "licenses": [{"expression": "LGPL-3.0-or-later"}]},
        ],
    )
    policy = tmp_path / "exceptions.json"
    policy.write_text(json.dumps({
        "policy_version": 1,
        "exceptions": [{
            "package": "@img/sharp-libvips-linux-x64",
            "version": "1.3.4",
            "license": "LGPL-3.0-or-later",
            "status": "temporary-release-blocker",
            "expires": "2099-01-01",
            "reason": "Inventory only; legal review is still required."
        }]
    }), encoding="utf-8")
    count, findings, notices = verify_reports(
        cyclonedx_reports=[report], exception_policy=policy
    )
    assert count == 3
    assert len(findings) == 2
    assert len(notices) == 1
    assert "@img/sharp-libvips-linux-x64@1.3.4" in notices[0]
    assert "RELEASE BLOCKED pending legal review" in notices[0]


def test_license_exception_expiration_fails_closed(tmp_path: Path):
    policy = tmp_path / "expired-exceptions.json"
    policy.write_text(json.dumps({
        "policy_version": 1,
        "exceptions": [{
            "package": "package",
            "version": "1.0",
            "license": "LGPL-3.0-or-later",
            "status": "temporary-release-blocker",
            "expires": "2000-01-01",
            "reason": "Expired test exception"
        }]
    }), encoding="utf-8")
    report = _python_report(tmp_path, [{"Name": "package", "Version": "1.0", "License": "LGPL-3.0-or-later"}])
    with pytest.raises(ValueError, match="expired"):
        verify_reports(python_reports=[report], exception_policy=policy)
