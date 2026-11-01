from __future__ import annotations

import json
import os
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


BASE_URL = os.environ.get("BROWSER_BASE_URL", "http://127.0.0.1:3100")


def test_partner_messaging_inbox_starts_and_replies_to_a_program_conversation():
    conversations = []
    messages = []
    activity = []
    applications = [{
        "application_id": "app-merchant-publisher-1",
        "offer_name": "Creator Analytics Suite",
        "application_status": "approved",
        "counterparty_name": "Acme Merchant",
        "updated_at": "2026-11-01T12:00:00+00:00",
    }]
    conversation = {
        "id": "conversation-1",
        "application_id": "app-merchant-publisher-1",
        "subject": "Creator Analytics Suite · partner discussion",
        "offer_name": "Creator Analytics Suite",
        "counterparty_name": "Acme Merchant",
        "status": "open",
        "last_message_at": "2026-11-01T12:05:00+00:00",
        "last_message_preview": "Please confirm newsletter placements.",
        "unread_count": 0,
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                path = urlparse(route.request.url).path
                method = route.request.method
                if path == "/api/auth/me":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({
                        "authenticated": True,
                        "user": {"email": "publisher@example.test", "account_type": "affiliate_publisher", "is_admin": False},
                        "csrf_token": "browser-test-token",
                    }))
                    return
                if path == "/api/partner/messageable-applications" and method == "GET":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({"count": len(applications), "data": applications}))
                    return
                if path == "/api/partner/conversations" and method == "GET":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({
                        "count": len(conversations), "total_count": len(conversations), "limit": 50, "offset": 0,
                        "can_send": True, "data": conversations,
                    }))
                    return
                if path == "/api/partner/conversations" and method == "POST":
                    payload = json.loads(route.request.post_data or "{}")
                    assert payload["application_id"] == "app-merchant-publisher-1"
                    created = {
                        "id": "message-1", "sender_workspace_id": "publisher-workspace",
                        "sender_email": "publisher@example.test", "body": payload["body"],
                        "created_at": "2026-11-01T12:05:00+00:00", "read_at": None,
                        "is_mine": True, "is_read": False,
                    }
                    messages.append(created)
                    conversations.append(conversation)
                    activity.append({
                        "id": "activity-1", "actor": "publisher@example.test",
                        "action": "partner.message.sent", "outcome": "created",
                        "details": {"message_id": created["id"]},
                        "created_at": "2026-11-01T12:05:00+00:00",
                    })
                    route.fulfill(status=201, content_type="application/json", body=json.dumps({
                        "conversation_id": "conversation-1", "application_id": "app-merchant-publisher-1", "message": created,
                    }))
                    return
                if path == "/api/partner/conversations/conversation-1/activity" and method == "GET":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({
                        "conversation_id": "conversation-1", "count": len(activity), "data": activity,
                    }))
                    return
                if path == "/api/partner/conversations/conversation-1/messages" and method == "GET":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({
                        "conversation_id": "conversation-1", "application_id": "app-merchant-publisher-1",
                        "status": "open", "can_send": True, "count": len(messages), "data": messages,
                    }))
                    return
                if path == "/api/partner/conversations/conversation-1/messages" and method == "POST":
                    payload = json.loads(route.request.post_data or "{}")
                    created = {
                        "id": "message-2", "sender_workspace_id": "publisher-workspace",
                        "sender_email": "publisher@example.test", "body": payload["body"],
                        "created_at": "2026-11-01T12:06:00+00:00", "read_at": None,
                        "is_mine": True, "is_read": False,
                    }
                    messages.append(created)
                    activity.append({
                        "id": "activity-2", "actor": "publisher@example.test",
                        "action": "partner.message.sent", "outcome": "created",
                        "details": {"message_id": created["id"]},
                        "created_at": "2026-11-01T12:06:00+00:00",
                    })
                    route.fulfill(status=201, content_type="application/json", body=json.dumps({
                        "conversation_id": "conversation-1", "message": created,
                    }))
                    return
                route.fulfill(status=404, content_type="application/json", body='{"detail":"Unexpected request"}')

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/messages?applicationId=app-merchant-publisher-1", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Partner messages").wait_for(state="visible")
            page.get_by_label("Program").wait_for(state="visible")
            page.get_by_label("Message").fill("Please confirm newsletter placements.")
            page.get_by_role("button", name="Send message").click()
            page.get_by_text("Please confirm newsletter placements.", exact=True).wait_for(state="visible")
            page.get_by_label("Message").fill("Thank you. I will follow the published traffic terms.")
            send_button = page.get_by_role("button", name="Send message")
            expect(send_button).to_be_enabled(timeout=10000)
            send_button.click()
            page.get_by_text("Thank you. I will follow the published traffic terms.", exact=True).wait_for(state="visible")
            page.get_by_text("Conversation activity", exact=True).wait_for(state="visible")
            page.get_by_text("2 events", exact=True).wait_for(state="visible")
            page.get_by_text("Message sent", exact=True).wait_for(state="visible")
            assert len(messages) == 2
            assert len(activity) == 2
        finally:
            browser.close()
