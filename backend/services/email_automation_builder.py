from __future__ import annotations

import hashlib
import json
import re
from typing import Any


_MAX_NODES = 30
_STEP_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_ALLOWED_KINDS = {"email", "branch", "stop"}
_ALLOWED_CONDITIONS = {"purchased", "not_purchased", "engaged", "not_engaged"}


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _nonblank(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    result = value.strip()
    if not result or len(result) > maximum:
        raise ValueError(f"{field} must contain 1-{maximum} non-blank characters")
    return result


def build_email_automation(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and checksum a declarative branching email plan; never send email."""
    name = _nonblank(payload.get("name"), "name", 180)
    description = _nonblank(payload.get("description"), "description", 3000)
    version = _nonblank(payload.get("version"), "version", 40)
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?", version):
        raise ValueError("version must use semantic versioning such as 1.0.0")
    entry_id = payload.get("entry_step_id")
    if not isinstance(entry_id, str) or not _STEP_ID.fullmatch(entry_id):
        raise ValueError("entry_step_id must be a valid step identifier")
    supplied_nodes = payload.get("nodes")
    if not isinstance(supplied_nodes, list) or not 2 <= len(supplied_nodes) <= _MAX_NODES:
        raise ValueError(f"nodes must contain 2-{_MAX_NODES} steps")

    nodes: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for index, source in enumerate(supplied_nodes):
        if not isinstance(source, dict):
            raise ValueError(f"nodes[{index}] must be an object")
        step_id = source.get("id")
        kind = source.get("kind")
        if not isinstance(step_id, str) or not _STEP_ID.fullmatch(step_id):
            raise ValueError(f"nodes[{index}].id is invalid")
        if step_id in by_id:
            raise ValueError(f"Duplicate step id: {step_id}")
        if kind not in _ALLOWED_KINDS:
            raise ValueError(f"nodes[{index}].kind must be email, branch or stop")

        if kind == "email":
            subject = _nonblank(source.get("subject"), f"{step_id}.subject", 300)
            body_text = _nonblank(source.get("body_text"), f"{step_id}.body_text", 12000)
            delay_days = source.get("delay_days", 0)
            if isinstance(delay_days, bool) or not isinstance(delay_days, int) or not 0 <= delay_days <= 90:
                raise ValueError(f"{step_id}.delay_days must be an integer from 0 to 90")
            next_step_id = source.get("next_step_id")
            if not isinstance(next_step_id, str) or not _STEP_ID.fullmatch(next_step_id):
                raise ValueError(f"{step_id}.next_step_id must reference a valid step id")
            has_affiliate_links = source.get("has_affiliate_links", False)
            if not isinstance(has_affiliate_links, bool):
                raise ValueError(f"{step_id}.has_affiliate_links must be a boolean")
            disclosure = str(source.get("affiliate_disclosure") or "").strip()
            if has_affiliate_links and len(disclosure) < 10:
                raise ValueError(f"{step_id} requires an affiliate_disclosure when has_affiliate_links is true")
            node = {
                "id": step_id, "kind": kind, "subject": subject,
                "body_text": body_text, "delay_days": delay_days,
                "next_step_id": next_step_id,
                "has_affiliate_links": has_affiliate_links,
                "affiliate_disclosure": disclosure,
            }
            if not has_affiliate_links and re.search(r"https?://\S+", body_text, re.IGNORECASE):
                warnings.append(f"{step_id}: contains a URL; confirm destination, commercial relationship and disclosure before use.")
        elif kind == "branch":
            condition = source.get("condition")
            if condition not in _ALLOWED_CONDITIONS:
                raise ValueError(f"{step_id}.condition must be one of {', '.join(sorted(_ALLOWED_CONDITIONS))}")
            true_step_id = source.get("true_step_id")
            false_step_id = source.get("false_step_id")
            if not isinstance(true_step_id, str) or not _STEP_ID.fullmatch(true_step_id):
                raise ValueError(f"{step_id}.true_step_id must reference a valid step id")
            if not isinstance(false_step_id, str) or not _STEP_ID.fullmatch(false_step_id):
                raise ValueError(f"{step_id}.false_step_id must reference a valid step id")
            if true_step_id == false_step_id:
                warnings.append(f"{step_id}: both branch outcomes lead to the same step.")
            node = {"id": step_id, "kind": kind, "condition": condition,
                    "true_step_id": true_step_id, "false_step_id": false_step_id}
        else:
            node = {"id": step_id, "kind": kind}
        nodes.append(node)
        by_id[step_id] = node

    if entry_id not in by_id:
        raise ValueError("entry_step_id must reference a defined node")
    if not any(node["kind"] == "email" for node in nodes):
        raise ValueError("An automation must contain at least one email step")

    edges: dict[str, list[str]] = {}
    for node in nodes:
        if node["kind"] == "email":
            targets = [node["next_step_id"]]
        elif node["kind"] == "branch":
            targets = [node["true_step_id"], node["false_step_id"]]
        else:
            targets = []
        for target in targets:
            if target not in by_id:
                raise ValueError(f"{node['id']} references unknown step {target}")
        edges[node["id"]] = targets

    visiting: set[str] = set()
    visited: set[str] = set()
    reachable: set[str] = set()

    def visit(step_id: str) -> None:
        if step_id in visiting:
            raise ValueError(f"Automation graph contains a cycle at step {step_id}")
        if step_id in visited:
            reachable.add(step_id)
            return
        visiting.add(step_id)
        reachable.add(step_id)
        for target in edges[step_id]:
            visit(target)
        visiting.remove(step_id)
        visited.add(step_id)

    visit(entry_id)
    if len(reachable) != len(nodes):
        hidden = sorted(set(by_id) - reachable)
        raise ValueError("Every step must be reachable from entry_step_id; unreachable steps: " + ", ".join(hidden[:8]))
    if any(node["kind"] == "branch" and not edges[node["id"]] for node in nodes):
        raise ValueError("Branch nodes must provide both outcome paths")

    graph = {
        "schema_version": 1,
        "name": name,
        "description": description,
        "version": version,
        "entry_step_id": entry_id,
        "nodes": nodes,
    }
    checksum = hashlib.sha256(_canonical_json(graph)).hexdigest()
    report = {
        "valid": True,
        "node_count": len(nodes),
        "email_step_count": sum(node["kind"] == "email" for node in nodes),
        "branch_count": sum(node["kind"] == "branch" for node in nodes),
        "stop_count": sum(node["kind"] == "stop" for node in nodes),
        "graph_acyclic": True,
        "all_steps_reachable": True,
        "checksum_sha256": checksum,
        "warnings": warnings,
        "review_required": True,
        "messages_sent": 0,
        "provider_calls_made": 0,
        "note": "Graph validation checks structure only. Simulation has no provider side effects; review does not activate delivery.",
    }
    return {"graph": graph, "validation_report": report, "sha256": checksum}


def simulate_email_automation(
    graph: dict[str, Any],
    *,
    purchased: bool = False,
    engaged: bool = False,
    consent_granted: bool = True,
    unsubscribed: bool = False,
) -> dict[str, Any]:
    """Trace one example path without sending/scheduling email or mutating lead records."""
    built = build_email_automation(graph)
    normalized = built["graph"]
    if not consent_granted:
        return {
            "graph_sha256": built["sha256"], "path": [], "emails": [],
            "stopped": True, "stop_reason": "consent_not_granted",
            "provider_calls_made": 0, "messages_scheduled": 0,
        }
    if unsubscribed:
        return {
            "graph_sha256": built["sha256"], "path": [], "emails": [],
            "stopped": True, "stop_reason": "recipient_unsubscribed",
            "provider_calls_made": 0, "messages_scheduled": 0,
        }
    by_id = {node["id"]: node for node in normalized["nodes"]}
    context = {
        "purchased": purchased,
        "not_purchased": not purchased,
        "engaged": engaged,
        "not_engaged": not engaged,
    }
    node_id = normalized["entry_step_id"]
    path: list[str] = []
    emails: list[dict[str, Any]] = []
    cumulative_delay = 0
    for _ in range(len(by_id)):
        node = by_id[node_id]
        path.append(node_id)
        if node["kind"] == "stop":
            return {
                "graph_sha256": built["sha256"], "path": path, "emails": emails,
                "stopped": True, "stop_reason": "terminal_step",
                "provider_calls_made": 0, "messages_scheduled": 0,
            }
        if node["kind"] == "email":
            cumulative_delay += node["delay_days"]
            email = {
                "step_id": node["id"],
                "subject": node["subject"],
                "body_text": node["body_text"],
                "scheduled_offset_days": cumulative_delay,
                "affiliate_disclosure_required": node["has_affiliate_links"],
                "affiliate_disclosure": node["affiliate_disclosure"] if node["has_affiliate_links"] else None,
            }
            emails.append(email)
            node_id = node["next_step_id"]
            continue
        outcome = bool(context[node["condition"]])
        path.append(f"{node['id']}:{'true' if outcome else 'false'}")
        node_id = node["true_step_id"] if outcome else node["false_step_id"]
    raise RuntimeError("Validated graph unexpectedly exceeded its bounded traversal length")
