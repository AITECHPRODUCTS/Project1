from __future__ import annotations

import json
import os
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("BROWSER_BASE_URL", "http://127.0.0.1:3100")


def _json(route, payload: dict, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        headers={
            "access-control-allow-origin": "http://127.0.0.1:3100",
            "access-control-allow-credentials": "true",
        },
        body=json.dumps(payload),
    )


def _user_payload() -> dict:
    return {
        "authenticated": True,
        "user": {
            "user_id": "email-visual-user",
            "email": "automation-owner@example.test",
            "is_admin": False,
            "workspace_id": "email-visual-workspace",
            "workspace_role": "owner",
        },
        "csrf_token": "email-visual-csrf-token",
    }


def _initial_graph() -> dict:
    return {
        "schema_version": 1,
        "name": "Visual creator nurture",
        "description": "A visual branching journey for consented subscribers.",
        "version": "1.0.0",
        "entry_step_id": "welcome",
        "target_jurisdictions": ["US"],
        "nodes": [
            {
                "id": "welcome", "kind": "email",
                "subject": "Your guide is ready",
                "body_text": "Thanks for requesting the guide.",
                "delay_days": 0, "next_step_id": "purchase-check",
                "has_affiliate_links": False, "affiliate_disclosure": "",
            },
            {
                "id": "purchase-check", "kind": "branch",
                "condition": "purchased",
                "true_step_id": "purchased-stop",
                "false_step_id": "engagement-check",
            },
            {
                "id": "engagement-check", "kind": "branch",
                "condition": "engaged",
                "true_step_id": "engaged-followup",
                "false_step_id": "quiet-followup",
            },
            {
                "id": "engaged-followup", "kind": "email",
                "subject": "A practical next step",
                "body_text": "Apply one useful idea today.",
                "delay_days": 2, "next_step_id": "done",
                "has_affiliate_links": False, "affiliate_disclosure": "",
            },
            {
                "id": "quiet-followup", "kind": "email",
                "subject": "A simple checklist",
                "body_text": "Compare your next steps with this checklist.",
                "delay_days": 3, "next_step_id": "done",
                "has_affiliate_links": False, "affiliate_disclosure": "",
            },
            {"id": "purchased-stop", "kind": "stop"},
            {"id": "done", "kind": "stop"},
        ],
    }


def test_visual_email_automation_builder_adds_connects_persists_and_simulates_branch():
    submitted: list[dict] = []
    simulation_requests: list[dict] = []
    stored_graph: dict | None = None
    automation_id = "visual-email-automation-1"

    def automation_response(graph: dict, status: str = "review_required") -> dict:
        return {
            "id": automation_id,
            "name": graph["name"],
            "description": graph["description"],
            "version": graph["version"],
            "status": status,
            "entry_step_id": graph["entry_step_id"],
            "node_count": len(graph["nodes"]),
            "validation_report": {
                "email_step_count": sum(node["kind"] == "email" for node in graph["nodes"]),
                "branch_count": sum(node["kind"] == "branch" for node in graph["nodes"]),
                "stop_count": sum(node["kind"] == "stop" for node in graph["nodes"]),
                "warnings": [],
            },
            "graph_sha256": "a" * 64,
            "created_by": "automation-owner@example.test",
            "reviewed_by": None,
            "reviewed_at": None,
            "reviewer_notes": None,
            "graph": graph,
            "execution_boundary": "Review and simulation do not send email.",
        }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                nonlocal stored_graph
                request = route.request
                path = urlparse(request.url).path

                if path == "/api/auth/me":
                    _json(route, _user_payload())
                    return

                if path == "/api/workspaces":
                    _json(
                        route,
                        {
                            "active_workspace_id": "email-visual-workspace",
                            "data": [{
                                "id": "email-visual-workspace",
                                "name": "Email Visual Workspace",
                                "role": "owner",
                                "is_active": True,
                                "lifecycle_state": "active",
                            }],
                        },
                    )
                    return

                if path == "/api/email/automations" and request.method == "GET":
                    data = [automation_response(stored_graph)] if stored_graph else []
                    _json(route, {"count": len(data), "data": data})
                    return

                if path == "/api/email/automations" and request.method == "POST":
                    stored_graph = json.loads(request.post_data or "{}")
                    submitted.append(stored_graph)
                    _json(route, automation_response(stored_graph), status=201)
                    return

                if path == f"/api/email/automations/{automation_id}/simulate" and request.method == "POST":
                    context = json.loads(request.post_data or "{}")
                    simulation_requests.append(context)
                    graph = stored_graph or _initial_graph()
                    nodes = {node["id"]: node for node in graph["nodes"]}
                    _json(
                        route,
                        {
                            "automation_id": automation_id,
                            "automation_status": "review_required",
                            "provider_calls_made": 0,
                            "messages_scheduled": 0,
                            "simulation": {
                                "graph_sha256": "a" * 64,
                                "path": [
                                    "welcome",
                                    "purchase-check:false",
                                    "engagement-check:false",
                                    "quiet-followup",
                                    "email-1",
                                    "done",
                                ],
                                "emails": [{
                                    "step_id": "email-1",
                                    "subject": nodes["email-1"]["subject"],
                                    "body_text": nodes["email-1"]["body_text"],
                                    "scheduled_offset_days": 4,
                                    "affiliate_disclosure_required": False,
                                    "affiliate_disclosure": None,
                                }],
                                "stopped": True,
                                "stop_reason": "terminal_step",
                                "provider_calls_made": 0,
                                "messages_scheduled": 0,
                            },
                        },
                    )
                    return

                if path.startswith("/api/"):
                    _json(route, {"detail": "Unexpected API request"}, status=404)
                    return

                route.continue_()

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/email-automations", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Branching email automation").wait_for(state="visible")
            page.get_by_test_id("visual-graph-editor").wait_for(state="visible")

            assert page.get_by_label("Branch graph JSON").count() == 0
            assert page.get_by_test_id("node-engagement-check-condition").input_value() == "engaged"

            page.get_by_test_id("node-engagement-check-condition").select_option("not_engaged")
            page.get_by_test_id("add-email-step").click()

            page.get_by_test_id("node-email-1-subject").fill("Your next creator workflow")
            page.get_by_test_id("node-email-1-body").fill(
                "Use this evidence checklist to plan your next content experiment."
            )
            page.get_by_test_id("node-email-1-delay").fill("4")

            assert page.get_by_test_id("node-quiet-followup-next").input_value() == "email-1"
            assert page.get_by_test_id("node-email-1-next").input_value() == "done"
            assert page.get_by_test_id("node-engagement-check-false").input_value() == "quiet-followup"

            with page.expect_response(
                lambda response: (
                    urlparse(response.url).path == "/api/email/automations"
                    and response.request.method == "POST"
                )
            ) as create_response:
                page.get_by_role("button", name="Validate and save review-required graph").click()

            created = create_response.value
            assert created.status == 201, created.text()
            assert len(submitted) == 1
            graph = submitted[0]
            submitted_nodes = {node["id"]: node for node in graph["nodes"]}
            assert graph["entry_step_id"] == "welcome"
            assert submitted_nodes["engagement-check"]["condition"] == "not_engaged"
            assert submitted_nodes["engagement-check"]["false_step_id"] == "quiet-followup"
            assert submitted_nodes["quiet-followup"]["next_step_id"] == "email-1"
            assert submitted_nodes["email-1"]["subject"] == "Your next creator workflow"
            assert submitted_nodes["email-1"]["delay_days"] == 4
            assert submitted_nodes["email-1"]["next_step_id"] == "done"

            page.get_by_test_id("simulation-engaged").check()
            page.get_by_test_id("simulate-selected-automation").click()
            page.get_by_test_id("simulation-result").wait_for(state="visible")
            assert len(simulation_requests) == 1
            assert simulation_requests[0] == {
                "purchased": False,
                "engaged": True,
                "consent_granted": True,
                "unsubscribed": False,
            }
            page.get_by_test_id("simulation-result").get_by_text("email-1").wait_for()
            page.get_by_text("provider calls: 0; messages scheduled: 0").wait_for()
            assert stored_graph is not None
        finally:
            browser.close()
