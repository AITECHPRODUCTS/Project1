from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from backend.services.skill_runtime import SUPPORTED_RUNTIME_HANDLERS, execute_skill_handler


_ALLOWED_SCHEMA_KEYWORDS = {
    "type", "title", "description", "properties", "required",
    "additionalProperties", "items", "enum", "minLength", "maxLength",
    "minimum", "maximum", "minItems", "maxItems", "pattern", "default", "examples",
}
_ALLOWED_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}
_RISKY_CAPABILITY_PARTS = (
    "publish", "write", "send", "email", "ad", "spend", "payout", "payment",
    "delete", "credential", "secret", "external", "deploy", "finance", "account",
    "refund", "withdraw", "transfer", "purchase",
)


def _schema_errors(schema: Any, *, path: str, depth: int = 0) -> list[str]:
    if depth > 12:
        return [f"{path}: schema nesting exceeds 12 levels"]
    if not isinstance(schema, dict):
        return [f"{path}: schema must be an object"]
    errors: list[str] = []
    unsupported = sorted(set(schema) - _ALLOWED_SCHEMA_KEYWORDS)
    if unsupported:
        errors.append(f"{path}: unsupported schema keywords: {', '.join(unsupported[:8])}")
    declared_type = schema.get("type")
    if declared_type not in _ALLOWED_TYPES:
        errors.append(f"{path}.type: choose one supported JSON type")
    valid_integer_bounds: dict[str, bool] = {}
    for key in ("minLength", "maxLength", "minItems", "maxItems"):
        valid = (
            key not in schema
            or (
                not isinstance(schema[key], bool)
                and isinstance(schema[key], int)
                and schema[key] >= 0
            )
        )
        valid_integer_bounds[key] = valid
        if not valid:
            errors.append(f"{path}.{key}: must be a non-negative integer")

    valid_numeric_bounds: dict[str, bool] = {}
    for key in ("minimum", "maximum"):
        if key not in schema:
            valid_numeric_bounds[key] = False
            continue
        value = schema[key]
        valid = (
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and not (isinstance(value, float) and not math.isfinite(value))
        )
        valid_numeric_bounds[key] = valid
        if not valid:
            errors.append(
                f"{path}.{key}: must be a finite number (booleans, NaN and infinity are not supported)"
            )

    if (
        "minLength" in schema and "maxLength" in schema
        and valid_integer_bounds["minLength"] and valid_integer_bounds["maxLength"]
        and schema["minLength"] > schema["maxLength"]
    ):
        errors.append(f"{path}: minLength cannot exceed maxLength")
    if (
        "minItems" in schema and "maxItems" in schema
        and valid_integer_bounds["minItems"] and valid_integer_bounds["maxItems"]
        and schema["minItems"] > schema["maxItems"]
    ):
        errors.append(f"{path}: minItems cannot exceed maxItems")
    if (
        valid_numeric_bounds["minimum"] and valid_numeric_bounds["maximum"]
        and schema["minimum"] > schema["maximum"]
    ):
        errors.append(f"{path}: minimum cannot exceed maximum")
    if "pattern" in schema:
        pattern = schema["pattern"]
        if not isinstance(pattern, str) or len(pattern) > 256:
            errors.append(f"{path}.pattern: must be a string of at most 256 characters")
        else:
            try:
                re.compile(pattern)
            except re.error:
                errors.append(f"{path}.pattern: invalid regular expression")
    properties = schema.get("properties", {})
    if properties is not None and not isinstance(properties, dict):
        errors.append(f"{path}.properties: must be an object")
    elif isinstance(properties, dict):
        if len(properties) > 100:
            errors.append(f"{path}.properties: maximum 100 properties supported")
        for name, child in properties.items():
            if not isinstance(name, str) or not name:
                errors.append(f"{path}.properties: property names must be non-empty strings")
                continue
            errors.extend(_schema_errors(child, path=f"{path}.properties.{name}", depth=depth + 1))
    required = schema.get("required", [])
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        errors.append(f"{path}.required: must be a list of property names")
    elif isinstance(properties, dict):
        missing = sorted(set(required) - set(properties))
        if missing:
            errors.append(f"{path}.required: undefined properties: {', '.join(missing[:8])}")
    if "additionalProperties" in schema and not isinstance(schema["additionalProperties"], bool):
        errors.append(f"{path}.additionalProperties: only boolean values are supported")
    if declared_type == "array":
        if not isinstance(schema.get("items"), dict):
            errors.append(f"{path}.items: an object schema is required for arrays")
        else:
            errors.extend(_schema_errors(schema["items"], path=f"{path}.items", depth=depth + 1))
    elif "items" in schema:
        errors.append(f"{path}.items: only supported when type is array")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"] or len(schema["enum"]) > 100):
        errors.append(f"{path}.enum: must be a non-empty list with at most 100 values")
    if errors:
        return errors[:30]
    return []


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return False


def _value_errors(value: Any, schema: dict[str, Any], *, path: str, depth: int = 0) -> list[str]:
    if depth > 12:
        return [f"{path}: value nesting exceeds 12 levels"]
    expected = schema.get("type")
    if not isinstance(expected, str) or expected not in _ALLOWED_TYPES:
        return [f"{path}: invalid schema type"]
    if not _matches_type(value, expected):
        return [f"{path}: expected {expected}, received {type(value).__name__}"]
    errors: list[str] = []
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is not in the allowed enum")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: string is shorter than minLength")
        if len(value) > schema.get("maxLength", 10**12):
            errors.append(f"{path}: string is longer than maxLength")
        if "pattern" in schema and isinstance(schema["pattern"], str) and not re.search(schema["pattern"], value):
            errors.append(f"{path}: string does not match pattern")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not math.isfinite(value):
            errors.append(f"{path}: number must be finite")
        else:
            if "minimum" in schema and value < schema["minimum"]:
                errors.append(f"{path}: number is less than minimum")
            if "maximum" in schema and value > schema["maximum"]:
                errors.append(f"{path}: number is greater than maximum")
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: array has fewer items than minItems")
        if len(value) > schema.get("maxItems", 10**12):
            errors.append(f"{path}: array has more items than maxItems")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value[:100]):
                errors.extend(_value_errors(item, item_schema, path=f"{path}[{index}]", depth=depth + 1))
                if len(errors) >= 30:
                    break
    elif isinstance(value, dict):
        properties = schema.get("properties", {})
        properties = properties if isinstance(properties, dict) else {}
        required = schema.get("required", [])
        for name in required if isinstance(required, list) else []:
            if name not in value:
                errors.append(f"{path}.{name}: required property is missing")
        for name, item in list(value.items())[:100]:
            child_schema = properties.get(name)
            if child_schema is None:
                if schema.get("additionalProperties", True) is False:
                    errors.append(f"{path}.{name}: additional property is not allowed")
            else:
                errors.extend(_value_errors(item, child_schema, path=f"{path}.{name}", depth=depth + 1))
            if len(errors) >= 30:
                break
    return errors[:30]


def _canonical_manifest(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def validate_skill_value(value: Any, schema: dict[str, Any], *, path: str = "input") -> list[str]:
    """Validate JSON-compatible runtime input or output against a bounded package schema."""
    return _value_errors(value, schema, path=path)


def build_skill_package(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a package and run only a code-owned pure handler against fixtures when selected."""
    runtime_handler = str(payload.get("runtime_handler") or "none")
    if runtime_handler not in SUPPORTED_RUNTIME_HANDLERS:
        raise ValueError("runtime_handler must be a supported built-in handler key")
    schema_errors = _schema_errors(payload["input_schema"], path="input_schema")
    schema_errors.extend(_schema_errors(payload["output_schema"], path="output_schema"))
    if schema_errors:
        raise ValueError("; ".join(schema_errors[:10]))

    cases: list[dict[str, Any]] = []
    for fixture in payload["test_cases"]:
        input_errors = _value_errors(fixture["input"], payload["input_schema"], path="input")
        output_errors = _value_errors(fixture["expected_output"], payload["output_schema"], path="expected_output")
        runtime_errors: list[str] = []
        runtime_performed = False
        runtime_matches: bool | None = None
        if runtime_handler != "none" and not input_errors:
            runtime_performed = True
            try:
                actual_output = execute_skill_handler(runtime_handler, fixture["input"])
                runtime_output_errors = _value_errors(actual_output, payload["output_schema"], path="runtime_output")
                runtime_errors.extend(runtime_output_errors)
                runtime_matches = not runtime_output_errors and actual_output == fixture["expected_output"]
                if not runtime_matches and not runtime_output_errors:
                    runtime_errors.append("runtime_output: actual output does not exactly match expected_output")
            except ValueError as exc:
                runtime_matches = False
                runtime_errors.append(f"runtime_handler: {str(exc)[:240]}")
        passed = not input_errors and not output_errors and (
            runtime_handler == "none" or (runtime_performed and runtime_matches is True)
        )
        cases.append({
            "name": fixture["name"],
            "passed": passed,
            "input_errors": input_errors,
            "expected_output_errors": output_errors,
            "runtime_execution_performed": runtime_performed,
            "runtime_output_matches_expected": runtime_matches,
            "runtime_errors": runtime_errors[:10],
            "execution_performed": runtime_performed,
        })
    passed_count = sum(1 for case in cases if case["passed"])
    risky = sorted(
        capability for capability in payload["capabilities"]
        if any(part in capability for part in _RISKY_CAPABILITY_PARTS)
    )
    runtime_count = sum(1 for case in cases if case["runtime_execution_performed"])
    report = {
        "schema_version": 2,
        "input_schema_valid": True,
        "output_schema_valid": True,
        "runtime_handler": runtime_handler,
        "runtime_handler_allowlisted": True,
        "fixture_count": len(cases),
        "fixtures_passed": passed_count,
        "fixtures_failed": len(cases) - passed_count,
        "all_fixtures_passed": bool(cases) and passed_count == len(cases),
        "cases": cases,
        "capabilities_requiring_human_review": risky,
        "declarative_only": True,
        "skill_instructions_executed": False,
        "runtime_execution_tested": runtime_count > 0,
        "runtime_fixtures_executed": runtime_count,
        "external_actions_executed": False,
        "warnings": [
            "Package Markdown remains declarative data and is never executed as code.",
            (
                "Fixtures executed the selected allowlisted, deterministic local handler; this does not prove arbitrary instructions or external integrations."
                if runtime_handler != "none" else
                "Fixtures validate input/output JSON contracts only; no runtime handler was selected."
            ),
            "Approval does not grant provider credentials, API scopes, publishing access, or financial authority.",
        ],
    }
    manifest = {
        "skill_id": payload["skill_id"],
        "display_name": payload["display_name"],
        "version": payload["version"],
        "description": payload["description"],
        "stage": payload["stage"],
        "capabilities": payload["capabilities"],
        "runtime_handler": runtime_handler,
        "input_schema": payload["input_schema"],
        "output_schema": payload["output_schema"],
        "instructions_markdown": payload["instructions_markdown"],
        "test_cases": payload["test_cases"],
    }
    checksum = hashlib.sha256(_canonical_manifest(manifest)).hexdigest()
    return {"manifest": manifest, "validation_report": report, "package_sha256": checksum}
