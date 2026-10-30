from __future__ import annotations
import base64, hashlib, hmac, re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
import httpx
from cryptography.fernet import Fernet, InvalidToken
from backend.config import get_settings
from backend.services.url_safety import request_public_json

CLICKBANK_ACCOUNTS_URL = "https://api.clickbank.com/rest/1.3/quickstats/accounts"
CREDENTIAL_KEY_VERSION = 1


class ClickBankAccessError(RuntimeError):
    pass


class ClickBankProviderUnavailable(RuntimeError):
    pass


class StoredCredentialError(RuntimeError):
    pass


def _credential_key() -> bytes:
    secret = str(get_settings().app_session_secret or "")
    if len(secret) < 32:
        raise StoredCredentialError("APP_SESSION_SECRET is not configured strongly enough for provider credentials.")
    return hashlib.sha256(b"omni-affiliate-provider-credentials:v1:" + secret.encode("utf-8")).digest()


def _cipher() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_credential_key()))


def encrypt_clickbank_api_key(api_key: str) -> str:
    return _cipher().encrypt(api_key.encode("utf-8")).decode("ascii")


def decrypt_clickbank_api_key(ciphertext: str, key_version: int = CREDENTIAL_KEY_VERSION) -> str:
    if key_version != CREDENTIAL_KEY_VERSION:
        raise StoredCredentialError("Stored provider credential uses an unsupported encryption version.")
    try:
        return _cipher().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError):
        raise StoredCredentialError("Stored ClickBank credential cannot be decrypted; reconnect the account.") from None


def fingerprint_clickbank_api_key(api_key: str) -> str:
    return hmac.new(_credential_key(), api_key.encode("utf-8"), hashlib.sha256).hexdigest()


def _account_names(payload: Any) -> list[str]:
    def visit(value: Any, depth: int = 0) -> list[str]:
        if depth > 5:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            found: list[str] = []
            for item in value[:500]:
                found.extend(visit(item, depth + 1))
            return found
        if not isinstance(value, dict):
            return []
        for field in ("nickName", "nickname", "accountNickname", "account_nickname"):
            candidate = value.get(field)
            if isinstance(candidate, str) and candidate.strip():
                return [candidate.strip()]
        found: list[str] = []
        for field in ("accountData", "accounts", "account", "accountNicknames", "account_nicknames", "nicknames", "data"):
            if field in value:
                found.extend(visit(value[field], depth + 1))
        return found

    names: list[str] = []
    seen: set[str] = set()
    for name in visit(payload):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", name):
            continue
        if name.casefold() not in seen:
            seen.add(name.casefold())
            names.append(name)
    return names


async def verify_clickbank_api_key(api_key: str) -> list[str]:
    """Read account nicknames using the documented Quickstats API key header."""
    try:
        payload = await request_public_json(
            CLICKBANK_ACCOUNTS_URL,
            method="GET",
            headers={"Authorization": api_key, "Accept": "application/json"},
            timeout=8.0,
            max_bytes=32_000,
        )
    except httpx.HTTPStatusError as exc:
        status = int(exc.response.status_code)
        if status in {401, 403}:
            raise ClickBankAccessError("ClickBank rejected Quickstats account-list access. Confirm that the key is active and has API Order Read permission.") from None
        if status == 429:
            raise ClickBankProviderUnavailable("ClickBank rate-limited the verification request. Try again later.") from None
        raise ClickBankProviderUnavailable(f"ClickBank returned HTTP {status} while verifying the account.") from None
    except (httpx.RequestError, TimeoutError):
        raise ClickBankProviderUnavailable("Could not reach ClickBank's API verification endpoint.") from None
    except ValueError:
        raise ClickBankProviderUnavailable("ClickBank returned an unsupported or invalid account-list response.") from None

    accounts = _account_names(payload)
    if not accounts:
        raise ClickBankAccessError("ClickBank authorized the request but returned no readable account nicknames. Check API Order Read permission and selected account nicknames.")
    return accounts



CLICKBANK_QUICKSTATS_LIST_URL = "https://api.clickbank.com/rest/1.3/quickstats/list"


def _quickstats_amount(value: Any, field: str) -> str | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ClickBankProviderUnavailable(f"ClickBank returned an invalid {field} amount.") from None
    if not amount.is_finite() or abs(amount) > Decimal("999999999999999999"):
        raise ClickBankProviderUnavailable(f"ClickBank returned an invalid {field} amount.")
    return format(amount, "f")


def _normalize_quickstats(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or "accountData" not in payload:
        raise ClickBankProviderUnavailable("ClickBank returned an unsupported Quickstats response.")
    account_data = payload.get("accountData")
    if isinstance(account_data, dict):
        account_rows = [account_data]
    elif isinstance(account_data, list):
        account_rows = account_data[:500]
    else:
        raise ClickBankProviderUnavailable("ClickBank returned an unsupported Quickstats account list.")

    daily: list[dict[str, Any]] = []
    account_names: list[str] = []
    for account_row in account_rows:
        if not isinstance(account_row, dict):
            continue
        nickname = account_row.get("nickName")
        if not isinstance(nickname, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", nickname):
            continue
        account_names.append(nickname)
        raw_stats = account_row.get("quickStats")
        if raw_stats is None:
            stats = []
        elif isinstance(raw_stats, dict):
            stats = [raw_stats]
        elif isinstance(raw_stats, list):
            stats = raw_stats[:400]
        else:
            raise ClickBankProviderUnavailable("ClickBank returned an unsupported daily Quickstats structure.")

        for item in stats:
            if not isinstance(item, dict):
                continue
            raw_day = item.get("quickStatDate")
            if not isinstance(raw_day, str) or len(raw_day) < 10:
                raise ClickBankProviderUnavailable("ClickBank returned a daily Quickstats record without a valid date.")
            try:
                normalized_day = date.fromisoformat(raw_day[:10]).isoformat()
            except ValueError:
                raise ClickBankProviderUnavailable("ClickBank returned a daily Quickstats record with an invalid date.") from None
            daily.append({
                "account": nickname,
                "date": normalized_day,
                "sales": _quickstats_amount(item.get("sale"), "sales"),
                "refunds": _quickstats_amount(item.get("refund"), "refunds"),
                "chargebacks": _quickstats_amount(item.get("chargeback"), "chargebacks"),
            })

    if not account_names:
        raise ClickBankProviderUnavailable("ClickBank returned no account-level Quickstats data.")
    daily.sort(key=lambda row: (row["account"].casefold(), row["date"]))
    totals: dict[str, str | None] = {}
    for metric in ("sales", "refunds", "chargebacks"):
        values = [Decimal(row[metric]) for row in daily if row[metric] is not None]
        totals[metric] = format(sum(values, Decimal(0)), "f") if values else None
    return {"accounts": list(dict.fromkeys(account_names)), "daily": daily, "totals": totals}


async def fetch_clickbank_quickstats(
    api_key: str,
    *,
    start_date: date,
    end_date: date,
    account: str | None = None,
) -> dict[str, Any]:
    """Retrieve aggregate daily sales/refunds/chargebacks; these are not commissions or payouts."""
    params = {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()}
    if account:
        params["account"] = account
    try:
        payload = await request_public_json(
            CLICKBANK_QUICKSTATS_LIST_URL,
            method="GET",
            params=params,
            headers={"Authorization": api_key, "Accept": "application/json"},
            timeout=10.0,
            max_bytes=512_000,
        )
    except httpx.HTTPStatusError as exc:
        status = int(exc.response.status_code)
        if status in {401, 403}:
            raise ClickBankAccessError("ClickBank rejected Quickstats data access. Confirm API Order Read permission for the selected account.") from None
        if status == 429:
            raise ClickBankProviderUnavailable("ClickBank rate-limited the Quickstats request. Try again later.") from None
        raise ClickBankProviderUnavailable(f"ClickBank returned HTTP {status} while retrieving Quickstats.") from None
    except (httpx.RequestError, TimeoutError):
        raise ClickBankProviderUnavailable("Could not reach ClickBank's Quickstats endpoint.") from None
    except ValueError:
        raise ClickBankProviderUnavailable("ClickBank returned invalid Quickstats JSON.") from None

    result = _normalize_quickstats(payload)
    if account and account.casefold() not in {name.casefold() for name in result["accounts"]}:
        raise ClickBankAccessError("ClickBank did not return Quickstats for the selected account nickname.")
    if account:
        result["daily"] = [row for row in result["daily"] if row["account"].casefold() == account.casefold()]
        result["accounts"] = [name for name in result["accounts"] if name.casefold() == account.casefold()]
        for metric in ("sales", "refunds", "chargebacks"):
            values = [Decimal(row[metric]) for row in result["daily"] if row[metric] is not None]
            result["totals"][metric] = format(sum(values, Decimal(0)), "f") if values else None
    return result
