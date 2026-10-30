from __future__ import annotations
from types import SimpleNamespace
from typing import Any
import pytest
from backend.services import ad_manager, s1_research, s4_s5_landing

@pytest.mark.asyncio
async def test_trend_research_uses_pinned_fixed_provider_json_requests(monkeypatch):
    settings=SimpleNamespace(reddit_client_id="reddit-client",reddit_client_secret="reddit-secret",reddit_user_agent="OmniAffiliateOS-test/1.0",x_bearer_token="x-test-token")
    monkeypatch.setattr(s1_research,"get_settings",lambda:settings)
    calls: list[dict[str,Any]]=[]
    async def request(url,**kwargs):
        calls.append({"url":url,**kwargs})
        if url.endswith("/api/v1/access_token"):return {"access_token":"reddit-access-token"}
        if url=="https://oauth.reddit.com/search":return {"data":{"children":[{"data":{"title":"Reddit measured trend","ups":10,"num_comments":2,"permalink":"/r/topic/1"}}]}}
        if url=="https://api.x.com/2/tweets/search/recent":return {"data":[{"id":"123","text":"X measured trend","public_metrics":{"like_count":5,"reply_count":2,"retweet_count":1},"created_at":"2026-10-26T00:00:00Z"}]}
        raise AssertionError("Unexpected provider URL: "+url)
    monkeypatch.setattr(s1_research,"request_public_json",request)
    result=await s1_research.trending_content_scout("affiliate analytics",limit=5)
    assert len(calls)==3
    assert calls[0]["url"]=="https://www.reddit.com/api/v1/access_token" and calls[0]["method"]=="POST"
    assert calls[0]["data_body"]=={"grant_type":"client_credentials"} and calls[0]["headers"]["Authorization"].startswith("Basic ")
    assert calls[1]["url"]=="https://oauth.reddit.com/search" and calls[1]["headers"]["Authorization"]=="Bearer reddit-access-token"
    assert calls[2]["url"]=="https://api.x.com/2/tweets/search/recent" and calls[2]["headers"]["Authorization"]=="Bearer x-test-token"
    assert {row["platform"] for row in result["results"]}=={"reddit","x"}
    assert result["providers"]=={"reddit":"ok","x":"ok"}

@pytest.mark.asyncio
async def test_social_publisher_uses_pinned_transport_and_preserves_dry_run(monkeypatch):
    settings=SimpleNamespace(publishing_dry_run=False,pinterest_access_token="pinterest-token",reddit_access_token="reddit-token",reddit_user_agent="OmniAffiliateOS-test/1.0")
    monkeypatch.setattr(s4_s5_landing,"get_settings",lambda:settings)
    calls: list[dict[str,Any]]=[]
    async def request(url,**kwargs):
        calls.append({"url":url,**kwargs})
        if url=="https://api.pinterest.com/v5/pins":return {"id":"pin-123","status":"created"}
        if url=="https://oauth.reddit.com/api/submit":return {"json":{"errors":[]},"data":{"id":"reddit-123"}}
        raise AssertionError("Unexpected provider URL: "+url)
    monkeypatch.setattr(s4_s5_landing,"request_public_json",request)
    pin=await s4_s5_landing.social_media_scheduler("pinterest",{"board_id":"board-1","title":"Reviewed pin","image_url":"https://assets.example/image.png"})
    reddit=await s4_s5_landing.social_media_scheduler("reddit",{"subreddit":"marketing","title":"Reviewed post","text":"Text with disclosure."})
    assert pin["remote_id"]=="pin-123" and reddit["status"]=="published"
    assert calls[0]["url"]=="https://api.pinterest.com/v5/pins" and calls[0]["method"]=="POST" and calls[0]["json_body"]["board_id"]=="board-1"
    assert calls[1]["url"]=="https://oauth.reddit.com/api/submit" and calls[1]["method"]=="POST" and calls[1]["data_body"]["sr"]=="marketing"
    assert calls[1]["headers"]["Authorization"]=="Bearer reddit-token"
    settings.publishing_dry_run=True;calls.clear()
    dry=await s4_s5_landing.social_media_scheduler("pinterest",{"board_id":"board-1","title":"Dry run","image_url":"https://assets.example/image.png"})
    assert dry["status"]=="dry_run" and calls==[]

@pytest.mark.asyncio
async def test_meta_pause_preserves_execution_gate_and_uses_pinned_form_post(monkeypatch):
    settings=SimpleNamespace(ad_automation_execute=False)
    monkeypatch.setattr(ad_manager,"get_settings",lambda:settings)
    calls=[]
    async def request(url,**kwargs):
        calls.append({"url":url,**kwargs});return {"success":True}
    monkeypatch.setattr(ad_manager,"request_public_json",request)
    disabled=await ad_manager.pause_meta_campaign("123","meta-token")
    assert disabled["executed"] is False and calls==[]
    settings.ad_automation_execute=True
    executed=await ad_manager.pause_meta_campaign("123","meta-token")
    assert executed["executed"] is True and calls[0]["url"]=="https://graph.facebook.com/v23.0/123"
    assert calls[0]["method"]=="POST" and calls[0]["data_body"]=={"status":"PAUSED","access_token":"meta-token"} and calls[0]["timeout"]==15
    with pytest.raises(Exception):await ad_manager.pause_meta_campaign("123/../../me","meta-token")
    assert len(calls)==1
