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
