from __future__ import annotations
import httpx
import pytest
from backend.services import clickbank_accounts as clickbank


@pytest.mark.asyncio
async def test_quickstats_uses_fixed_endpoint_and_documented_authorization_header(monkeypatch):
    calls=[]
    async def fake_request(url,**kwargs):
        calls.append((url,kwargs))
        return {"accountData":[{"nickName":"creator-main"},{"nickName":"creator-secondary"}]}
    monkeypatch.setattr(clickbank,"request_public_json",fake_request)
    key="API-"+"x"*40
    assert await clickbank.verify_clickbank_api_key(key)==["creator-main","creator-secondary"]
    url,kwargs=calls[0]
    assert url=="https://api.clickbank.com/rest/1.3/quickstats/accounts"
    assert kwargs["method"]=="GET"
    assert kwargs["headers"]=={"Authorization":key,"Accept":"application/json"}
    assert kwargs["timeout"]==8.0 and kwargs["max_bytes"]==32000


@pytest.mark.asyncio
async def test_forbidden_quickstats_request_becomes_permission_error(monkeypatch):
    async def forbidden(*args,**kwargs):
        request=httpx.Request("GET",clickbank.CLICKBANK_ACCOUNTS_URL)
        response=httpx.Response(403,request=request)
        raise httpx.HTTPStatusError("forbidden",request=request,response=response)
    monkeypatch.setattr(clickbank,"request_public_json",forbidden)
    with pytest.raises(clickbank.ClickBankAccessError,match="API Order Read"):
        await clickbank.verify_clickbank_api_key("API-"+"x"*40)


def test_credential_encryption_and_fingerprint(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(clickbank,"get_settings",lambda:SimpleNamespace(app_session_secret="test-session-secret-that-is-long-enough-for-encryption"))
    key="API-"+"x"*40
    ciphertext=clickbank.encrypt_clickbank_api_key(key)
    assert ciphertext!=key and key not in ciphertext
    assert clickbank.decrypt_clickbank_api_key(ciphertext)==key
    fingerprint=clickbank.fingerprint_clickbank_api_key(key)
    assert fingerprint!=key and len(fingerprint)==64


def test_account_name_parser_rejects_unsafe_values():
    assert clickbank._account_names({"accounts":["valid-name","Valid-Name","../private"]})==["valid-name"]
    assert clickbank._account_names({"unexpected":"shape"})==[]



@pytest.mark.asyncio
async def test_quickstats_list_request_is_date_bounded_and_returns_decimal_strings(monkeypatch):
    calls = []
    async def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        return {"accountData":[{"nickName":"creator-main","quickStats":[
            {"quickStatDate":"2026-10-01T00:00:00Z","sale":"10.50","refund":"1.25","chargeback":"0"},
            {"quickStatDate":"2026-10-02T00:00:00Z","sale":"3","refund":None,"chargeback":"0.50"},
        ]}]}
    monkeypatch.setattr(clickbank,"request_public_json",fake_request)
    result = await clickbank.fetch_clickbank_quickstats(
        "API-"+"x"*40,start_date=__import__("datetime").date(2026,10,1),
        end_date=__import__("datetime").date(2026,10,30),account="creator-main")
    url,kwargs=calls[0]
    assert url=="https://api.clickbank.com/rest/1.3/quickstats/list"
    assert kwargs["params"]=={"startDate":"2026-10-01","endDate":"2026-10-30","account":"creator-main"}
    assert result["totals"]=={"sales":"13.50","refunds":"1.25","chargebacks":"0.50"}
    assert result["daily"][0]["date"]=="2026-10-01"


@pytest.mark.asyncio
async def test_quickstats_rejects_unparseable_money(monkeypatch):
    async def fake_request(url,**kwargs):
        return {"accountData":[{"nickName":"creator-main","quickStats":[
            {"quickStatDate":"2026-10-01T00:00:00Z","sale":"NaN","refund":"0","chargeback":"0"}]}]}
    monkeypatch.setattr(clickbank,"request_public_json",fake_request)
    from datetime import date
    with pytest.raises(clickbank.ClickBankProviderUnavailable,match="invalid sales amount"):
        await clickbank.fetch_clickbank_quickstats(
            "API-"+"x"*40,start_date=date(2026,10,1),end_date=date(2026,10,1),account="creator-main")
