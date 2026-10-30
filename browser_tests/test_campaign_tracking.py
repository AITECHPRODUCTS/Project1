from __future__ import annotations
import json,os
from playwright.sync_api import sync_playwright

BASE_URL=os.environ.get("BROWSER_BASE_URL","http://127.0.0.1:3100")

def _fulfill(route,payload,status=200):
    route.fulfill(status=status,content_type="application/json",
        headers={"access-control-allow-origin":"http://127.0.0.1:3100","access-control-allow-credentials":"true"},
        body=json.dumps(payload))

def test_campaign_tracking_ui_creates_clickbank_tid_redirect_and_health_check():
    campaigns=[]
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        try:
            page=browser.new_page()
            def handle(route):
                request=route.request
                if request.url.endswith("/api/auth/me"):
                    _fulfill(route,{"authenticated":True,"user":{"email":"publisher@example.test"},"csrf_token":"browser-test"})
                elif request.method=="GET" and request.url.endswith("/api/campaigns"):
                    _fulfill(route,{"count":len(campaigns),"data":campaigns})
                elif request.method=="POST" and request.url.endswith("/api/campaigns"):
                    payload=json.loads(request.post_data or "{}")
                    assert payload["tracking_parameter"]=="tid"
                    assert payload["auto_publish"] is False
                    assert payload["max_daily_spend"]==0
                    row={"id":"campaign-1","name":payload["name"],"niche":payload["niche"],
                        "primary_destination":payload["primary_destination"],"fallback_destination":payload["fallback_destination"],
                        "tracking_parameter":"tid","tracking_url":"http://127.0.0.1:8000/r/campaign-1",
                        "is_active":True,"primary_healthy":None,"fallback_healthy":None,"health_last_error":None}
                    campaigns[:]=[row]
                    _fulfill(route,{"id":"campaign-1","name":row["name"],"tracking_parameter":"tid",
                        "tracking_url":row["tracking_url"],"status":"created"},201)
                elif request.method=="POST" and request.url.endswith("/api/campaigns/campaign-1/health"):
                    _fulfill(route,{"campaign_id":"campaign-1","route":"primary",
                        "destination":"https://hop.clickbank.net/?affiliate=creator&vendor=merchant&tid=abc",
                        "status_code":200,"primary_healthy":True,"fallback_healthy":None,"health_error":None,
                        "note":"Fallback applies to this click; campaign configuration is unchanged."})
                else:_fulfill(route,{"detail":"Unexpected campaign request"},404)
            page.route("**/api/**",handle)
            page.goto(BASE_URL+"/campaigns",wait_until="domcontentloaded")
            page.get_by_role("heading",name="Campaign tracking links").wait_for(state="visible")
            page.get_by_label("Campaign name").fill("ClickBank review article")
            page.get_by_label("Niche").fill("software")
            page.get_by_label("Primary affiliate destination URL").fill("https://hop.clickbank.net/?affiliate=creator&vendor=merchant")
            page.get_by_role("button",name="Create tracking link").click()
            page.get_by_test_id("created-campaign").wait_for(state="visible")
            assert "tid" in page.get_by_test_id("created-campaign").inner_text()
            assert page.get_by_text("ClickBank review article",exact=True).is_visible()
            page.get_by_role("button",name="Check destination health").click()
            page.get_by_text("Primary destination healthy",exact=True).wait_for(state="visible")
        finally:browser.close()
