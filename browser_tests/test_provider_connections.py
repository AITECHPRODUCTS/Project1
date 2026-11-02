from __future__ import annotations
import json,os
from playwright.sync_api import sync_playwright

BASE_URL=os.environ.get("BROWSER_BASE_URL","http://127.0.0.1:3100")
API_KEY="API-"+"z"*40


def _fulfill(route,payload:dict,status:int=200):
    route.fulfill(status=status,content_type="application/json",headers={"access-control-allow-origin":"http://127.0.0.1:3100","access-control-allow-credentials":"true"},body=json.dumps(payload))


def test_clickbank_connection_ui_masks_secret_and_removes_saved_credential():
    connections=[]
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        try:
            page=browser.new_page()
            def handle(route):
                request=route.request
                if request.url.endswith("/api/auth/me"):
                    _fulfill(route,{"authenticated":True,"user":{"email":"publisher@example.test"},"csrf_token":"browser-test"})
                elif request.method=="GET" and request.url.endswith("/api/provider-connections"):
                    _fulfill(route,{"data":connections})
                elif request.method=="POST" and request.url.endswith("/api/provider-connections/clickbank"):
                    assert json.loads(request.post_data or "{}")=={"api_key":API_KEY}
                    row={"id":"cb-1","provider_id":"clickbank","status":"connected_read_only","account_nicknames":["creator-main"],"capabilities":["quickstats.accounts.read"],"permissions_verified":["API Order Read"],"credential_present":True,"last_checked_at":"2026-10-30T12:00:00+00:00","last_error_code":None,"created_at":None}
                    connections[:]=[row];_fulfill(route,row,201)
                elif request.method=="GET" and "/api/provider-connections/cb-1/quickstats?" in request.url:
                    _fulfill(route,{"provider_id":"clickbank","evidence_type":"provider_reported_aggregate",
                        "metric_scope":"sales_refunds_chargebacks_not_affiliate_commission_or_payout",
                        "period":{"start_date":"2026-10-01","end_date":"2026-10-30"},
                        "accounts":["creator-main"],"daily":[{"account":"creator-main","date":"2026-10-01","sales":"10","refunds":"1","chargebacks":"0"}],
                        "totals":{"sales":"10","refunds":"1","chargebacks":"0"}})
                elif request.method=="GET" and "/api/provider-connections/cb-1/order-counts?" in request.url:
                    _fulfill(route,{"provider_id":"clickbank","evidence_type":"provider_reported_transaction_counts",
                        "metric_scope":"affiliate_sale_refund_chargeback_counts_not_commission_or_payout_amounts",
                        "period":{"start_date":"2026-10-01","end_date":"2026-10-30"},"account":"creator-main",
                        "transaction_types":{"SALE":4,"RFND":1,"CGBK":0},
                        "counts":{"sales":4,"refunds":1,"chargebacks":0}})
                elif request.method=="POST" and request.url.endswith("/api/provider-connections/cb-1/orders/import"):
                    payload=json.loads(request.post_data or "{}")
                    assert payload["account"]=="creator-main"
                    _fulfill(route,{"provider_id":"clickbank","evidence_type":"provider_reported_order_observations",
                        "financial_semantics":"provider_account_amount_is_unreconciled_evidence_not_confirmed_commission_or_payout",
                        "pii_stored":False,"period":{"start_date":"2026-10-01","end_date":"2026-10-30"},
                        "account":"creator-main","pages_retrieved":1,"source_order_count":1,
                        "skipped_unidentified_count":0,"skipped_scope_count":0,"imported_count":1,
                        "duplicate_count":0,"matched_click_count":1,"unmatched_tracking_id_count":0,"has_more":False,"next_page":None,
                        "transactions":[{"event_key":"event-1","source_fingerprint":"hash-1","receipt":"RECEIPT123",
                            "transaction_time":"2026-10-20T12:00:00+00:00","transaction_type":"SALE","role":"AFFILIATE",
                            "account_nickname":"creator-main","vendor_nickname":"vendor-main","affiliate_nickname":"creator-main",
                            "currency":"USD","item_number":"PROD-1","line_item_type":"STANDARD","product_title":"Sample product",
                            "account_amount":"12.50","customer_amount":"49.00","line_item_status":"ACTIVE",
                            "recurring":False,"shippable":False,"evidence_status":"provider_reported_unreconciled","click_id":"a"*32,"attribution_status":"matched_clickbank_tid"}],
                        "note":"PII-minimized evidence only."},201)
                elif request.method=="POST" and request.url.endswith("/api/provider-connections/cb-1/test"):
                    _fulfill(route,connections[0])
                elif request.method=="DELETE" and request.url.endswith("/api/provider-connections/cb-1"):
                    connections[0]["status"]="disconnected";connections[0]["credential_present"]=False
                    _fulfill(route,{"id":"cb-1","provider_id":"clickbank","status":"disconnected","credential_present":False,"provider_key_revoked_remotely":False,"detail":"Saved credential removed."})
                else:_fulfill(route,{"detail":"Unexpected request"},404)
            page.route("**/api/**",handle)
            page.goto(BASE_URL+"/integrations",wait_until="domcontentloaded")
            page.get_by_role("heading",name="Affiliate account connections").wait_for(state="visible")
            page.get_by_label("ClickBank API key").fill(API_KEY)
            page.get_by_role("button",name="Verify & connect",exact=True).click()
            page.get_by_text("creator-main",exact=True).wait_for(state="visible")
            assert page.get_by_label("ClickBank API key").input_value()==""
            assert API_KEY not in page.locator("main").inner_text()
            page.get_by_role("button",name="Load last 30 days").click()
            page.get_by_text("Provider-reported aggregate",exact=False).wait_for(state="visible")
            assert page.get_by_text("sales/refund/chargeback aggregates",exact=False).is_visible()
            page.get_by_role("button",name="Load 30-day order counts").click()
            page.get_by_text("Provider-reported affiliate transaction counts",exact=False).wait_for(state="visible")
            assert page.get_by_text("Counts only.",exact=False).is_visible()
            page.get_by_role("button",name="Import last 30 days orders").click()
            page.get_by_test_id("clickbank-order-import").wait_for(state="visible")
            assert page.get_by_text("Sample product",exact=True).is_visible()
            assert page.get_by_text("USD 12.50",exact=True).is_visible()
            assert page.get_by_text("Customer names, emails, contact details and postal data are not stored.",exact=False).is_visible()
            page.get_by_role("button",name="Test connection").click()
            page.get_by_text("ClickBank read-only account verification passed.").wait_for(state="visible")
            page.get_by_role("button",name="Disconnect").click()
            page.get_by_text("Saved credential removed.",exact=False).wait_for(state="visible")
            assert connections[0]["credential_present"] is False
        finally:browser.close()
