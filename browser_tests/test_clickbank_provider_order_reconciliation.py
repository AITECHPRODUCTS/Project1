from __future__ import annotations

import json
import os
from playwright.sync_api import sync_playwright

BASE_URL=os.environ.get("BROWSER_BASE_URL","http://127.0.0.1:3100")


def _fulfill(route,payload,status=200):
    route.fulfill(
        status=status,
        content_type="application/json",
        headers={
            "access-control-allow-origin":"http://127.0.0.1:3100",
            "access-control-allow-credentials":"true",
        },
        body=json.dumps(payload),
    )


def test_clickbank_provider_order_reconciliation_accepts_exact_signed_ledger_candidate():
    report={
        "count":1,
        "limit":100,
        "read_only":True,
        "commission_ledger_mutated":False,
        "payout_confirmed":False,
        "counts":{"not_reviewed":1},
        "data":[{
            "observation_id":"observation-1",
            "provider_id":"clickbank",
            "account_nickname":"creator-main",
            "receipt":"CB-RECEIPT-1",
            "transaction_time":"2026-10-20T12:00:00+00:00",
            "transaction_type":"SALE",
            "product_title":"Sample product",
            "line_item_status":"ACTIVE",
            "account_amount":"12.500000",
            "currency":"USD",
            "click_id":"a"*32,
            "attribution_status":"matched_clickbank_tid",
            "evidence_status":"provider_reported_unreconciled",
            "observed_at":"2026-10-20T12:01:00+00:00",
            "review_status":"not_reviewed",
            "reviewed_by":None,
            "reviewed_at":None,
            "review_note":None,
            "candidate_count":1,
            "candidates":[{
                "ledger_entry_id":"ledger-1",
                "network":"clickbank",
                "external_event_id":"cb-event-1",
                "commission_amount":"12.500000",
                "currency":"USD",
                "status":"approved",
                "evidence_status":"signed_webhook_verified",
            }],
            "match_block_reason":None,
        }],
        "policy":"An exact signed candidate still requires a human review decision.",
    }
    review_calls=[]
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        try:
            page=browser.new_page()
            page_errors=[]
            failed_requests=[]
            page.on("pageerror",lambda error:page_errors.append(str(error)))
            page.on("requestfailed",lambda request:failed_requests.append({
                "method":request.method,"url":request.url,"failure":request.failure
            }))
            def handle(route):
                request=route.request
                if request.url.endswith("/api/auth/me"):
                    _fulfill(route,{"authenticated":True,"user":{
                        "email":"owner@example.test","workspace_role":"owner","is_admin":False
                    },"csrf_token":"browser-test"})
                elif request.method=="GET" and "/api/finance/provider-orders/reconciliation" in request.url:
                    _fulfill(route,report)
                elif request.method=="PATCH" and request.url.endswith("/api/finance/provider-orders/observation-1/review"):
                    payload=json.loads(request.post_data or "{}")
                    assert payload=={
                        "decision":"matched_to_conversion",
                        "candidate_ledger_entry_id":"ledger-1",
                        "note":"Reviewed in the ClickBank provider-order queue",
                    }
                    review_calls.append(payload)
                    report["counts"]={"matched_to_conversion":1}
                    report["data"][0]["review_status"]="matched_to_conversion"
                    report["data"][0]["reviewed_by"]="owner@example.test"
                    report["data"][0]["candidate_count"]=0
                    report["data"][0]["candidates"]=[]
                    _fulfill(route,{
                        "observation_id":"observation-1","review_id":"review-1",
                        "decision":"matched_to_conversion","candidate_ledger_entry_id":"ledger-1",
                        "reviewed_by":"owner@example.test","reviewed_at":"2026-10-20T12:02:00+00:00",
                        "commission_ledger_mutated":False,"payout_confirmed":False,"transfers_initiated":False,
                    })
                else:
                    _fulfill(route,{"detail":"Unexpected reconciliation request"},404)
            page.route("**/api/**",handle)
            with page.expect_response(
                lambda response:"/api/finance/provider-orders/reconciliation" in response.url
            ) as queue_response_info:
                page.goto(BASE_URL+"/finance/provider-orders",wait_until="domcontentloaded")
            queue_response=queue_response_info.value
            assert queue_response.status==200,(
                f"Reconciliation API returned {queue_response.status}: {queue_response.text()}"
            )
            queue_payload=queue_response.json()
            assert queue_payload["count"]==1
            assert queue_payload["data"][0]["observation_id"]=="observation-1"
            assert queue_payload["data"][0]["product_title"]=="Sample product"
            page.get_by_role("heading",name="ClickBank order evidence reconciliation").wait_for(state="visible")
            row=page.get_by_test_id("provider-order-observation-1")
            try:
                row.wait_for(state="visible",timeout=10000)
            except Exception as error:
                raise AssertionError(
                    "Reconciliation API returned a valid observation but the matching card did not render. "
                    f"API payload: {queue_payload}; Page errors: {page_errors}; "
                    f"failed requests: {failed_requests}; URL: {queue_response.url}"
                ) from error
            assert "Sample product" in row.locator("h3").inner_text()
            assert "USD 12.500000" in row.inner_text()
            assert row.get_by_label("Ledger candidate for CB-RECEIPT-1").input_value()=="ledger-1"
            page.get_by_role("button",name="Accept exact ledger match").click()
            page.get_by_text("matched to conversion",exact=False).wait_for(state="visible")
            assert len(review_calls)==1
            assert page.get_by_text("Payout confirmed: no",exact=False).is_visible()
        finally:
            browser.close()
