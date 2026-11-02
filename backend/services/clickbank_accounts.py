from __future__ import annotations
import base64, hashlib, hmac, json, re
from datetime import date, datetime, timezone
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
import httpx
from cryptography.fernet import Fernet, InvalidToken
from backend.config import get_settings
from backend.services.url_safety import open_public_http_response, read_limited_response, request_public_json

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



CLICKBANK_ORDERS_COUNT_URL = "https://api.clickbank.com/rest/1.3/orders2/count"
CLICKBANK_AFFILIATE_TRANSACTION_TYPES = ("SALE", "RFND", "CGBK")


def _normalize_order_count(payload: Any) -> int:
    value: Any = payload
    if isinstance(payload, dict):
        if "count" not in payload:
            raise ClickBankProviderUnavailable("ClickBank returned an unsupported Orders count response.")
        value = payload["count"]
    if isinstance(value, bool):
        raise ClickBankProviderUnavailable("ClickBank returned an invalid order count.")
    if isinstance(value, str):
        if not re.fullmatch(r"\d{1,10}", value.strip()):
            raise ClickBankProviderUnavailable("ClickBank returned an invalid order count.")
        value = int(value.strip())
    if not isinstance(value, int) or value < 0 or value > 2_147_483_647:
        raise ClickBankProviderUnavailable("ClickBank returned an invalid order count.")
    return value


async def fetch_clickbank_order_counts(
    api_key: str,
    *,
    account: str,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """Read aggregate affiliate transaction counts only; never fetch customer order rows."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", account):
        raise ClickBankAccessError("The selected ClickBank affiliate nickname is invalid.")

    counts: dict[str, int] = {}
    for transaction_type in CLICKBANK_AFFILIATE_TRANSACTION_TYPES:
        try:
            payload = await request_public_json(
                CLICKBANK_ORDERS_COUNT_URL,
                method="GET",
                params={
                    "affiliate": account,
                    "role": "AFFILIATE",
                    "startDate": start_date.isoformat(),
                    "endDate": end_date.isoformat(),
                    "type": transaction_type,
                },
                headers={"Authorization": api_key, "Accept": "application/json"},
                timeout=8.0,
                max_bytes=16_000,
            )
        except httpx.HTTPStatusError as exc:
            status = int(exc.response.status_code)
            if status in {401, 403}:
                raise ClickBankAccessError(
                    "ClickBank rejected affiliate Orders count access. Confirm API Order Read permission for the selected account nickname."
                ) from None
            if status == 429:
                raise ClickBankProviderUnavailable("ClickBank rate-limited the Orders count request. Try again later.") from None
            raise ClickBankProviderUnavailable(f"ClickBank returned HTTP {status} while retrieving Orders counts.") from None
        except (httpx.RequestError, TimeoutError):
            raise ClickBankProviderUnavailable("Could not reach ClickBank's Orders count endpoint.") from None
        except ValueError:
            raise ClickBankProviderUnavailable("ClickBank returned invalid Orders count JSON.") from None
        counts[transaction_type] = _normalize_order_count(payload)

    return {
        "account": account,
        "transaction_types": counts,
        "counts": {
            "sales": counts["SALE"],
            "refunds": counts["RFND"],
            "chargebacks": counts["CGBK"],
        },
    }



CLICKBANK_ORDERS_LIST_URL = "https://api.clickbank.com/rest/1.3/orders2/list"


def _safe_order_amount(value: Any, field: str) -> str | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ClickBankProviderUnavailable(f"ClickBank returned an invalid {field} amount.") from None
    if not amount.is_finite() or abs(amount) > Decimal("999999999999"):
        raise ClickBankProviderUnavailable(f"ClickBank returned an invalid {field} amount.")
    if max(0, -amount.as_tuple().exponent) > 6:
        raise ClickBankProviderUnavailable(f"ClickBank returned an unsupported precision for {field}.")
    return format(amount, "f")


def _safe_order_text(value: Any, limit: int = 500) -> str | None:
    if value is None:
        return None
    if not isinstance(value, (str, int)):
        return None
    result = str(value).strip()
    return result[:limit] if result else None


def _clickbank_order_rows(payload: Any) -> list[dict[str, Any]]:
    value: Any = payload
    if isinstance(payload, dict):
        for key in ("orderData", "orders", "data"):
            if key in payload:
                value = payload[key]
                break
        else:
            if "receipt" in payload:
                value = [payload]
            else:
                raise ClickBankProviderUnavailable("ClickBank returned an unsupported Orders list response.")
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        raise ClickBankProviderUnavailable("ClickBank returned an unsupported Orders list structure.")
    if len(value) > 100:
        raise ClickBankProviderUnavailable("ClickBank returned more than 100 orders in one page.")
    return [item for item in value if isinstance(item, dict)]


def _normalize_clickbank_order_rows(
    payload: Any,
    *,
    account: str,
) -> tuple[list[dict[str, Any]], int, int]:
    """Return PII-minimized affiliate transaction line items and safe skip counts."""
    rows = _clickbank_order_rows(payload)
    normalized: list[dict[str, Any]] = []
    skipped_unidentified = 0
    skipped_scope = 0

    for order in rows:
        role = _safe_order_text(order.get("role"), 20)
        if role is not None and role.upper() != "AFFILIATE":
            skipped_scope += 1
            continue
        affiliate = _safe_order_text(order.get("affiliate"), 100)
        if affiliate is not None and affiliate.casefold() != account.casefold():
            skipped_scope += 1
            continue

        receipt = _safe_order_text(order.get("receipt"), 80)
        transaction_time = _safe_order_text(order.get("transactionTime"), 80)
        transaction_type = (_safe_order_text(order.get("transactionType"), 32) or "").upper()
        if (
            not receipt
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", receipt)
            or not transaction_time
            or not re.fullmatch(r"[A-Z0-9_]{2,32}", transaction_type)
        ):
            skipped_unidentified += 1
            continue
        try:
            parsed_time = datetime.fromisoformat(transaction_time.replace("Z", "+00:00"))
        except ValueError:
            skipped_unidentified += 1
            continue
        if parsed_time.tzinfo is None:
            parsed_time = parsed_time.replace(tzinfo=timezone.utc)
        normalized_time = parsed_time.isoformat()

        tracking_click_id_candidate = None
        for tracking_field in ("trackingId", "tracking_id", "promo"):
            tracking_value = _safe_order_text(order.get(tracking_field), 100)
            if tracking_value and re.fullmatch(r"[0-9a-f]{32}", tracking_value):
                tracking_click_id_candidate = tracking_value
                break

        currency_raw = (_safe_order_text(order.get("currency"), 3) or "").upper()
        currency = currency_raw if re.fullmatch(r"[A-Z]{3}", currency_raw) else None
        vendor = _safe_order_text(order.get("vendor"), 100)
        affiliate_name = affiliate or account

        line_items = order.get("lineItemData")
        if line_items is None:
            line_items = [{}]
        elif isinstance(line_items, dict):
            line_items = [line_items]
        if not isinstance(line_items, list):
            raise ClickBankProviderUnavailable("ClickBank returned an unsupported line-item structure.")
        if len(line_items) > 100:
            raise ClickBankProviderUnavailable("ClickBank returned too many line items for one transaction.")

        for line_item in line_items:
            if not isinstance(line_item, dict):
                continue
            item_number = _safe_order_text(line_item.get("itemNo"), 100)
            line_item_type = _safe_order_text(line_item.get("lineItemType"), 80)
            product_title = _safe_order_text(line_item.get("productTitle"), 500)
            account_amount = _safe_order_amount(line_item.get("accountAmount"), "account")
            customer_amount = _safe_order_amount(line_item.get("customerAmount"), "customer")
            item_status = _safe_order_text(line_item.get("status"), 80)
            recurring = line_item.get("recurring") if isinstance(line_item.get("recurring"), bool) else None
            shippable = line_item.get("shippable") if isinstance(line_item.get("shippable"), bool) else None
            line_item_key = item_number or "__order__"

            safe_record = {
                "receipt": receipt,
                "transaction_time": normalized_time,
                "transaction_type": transaction_type,
                "role": "AFFILIATE",
                "account_nickname": account,
                "vendor_nickname": vendor,
                "affiliate_nickname": affiliate_name,
                "currency": currency,
                "item_number": item_number,
                "line_item_type": line_item_type,
                "product_title": product_title,
                "account_amount": account_amount,
                "customer_amount": customer_amount,
                "line_item_status": item_status,
                "recurring": recurring,
                "shippable": shippable,
            }
            event_material = "|".join((
                account.casefold(), receipt, normalized_time, transaction_type, line_item_key,
            ))
            source_material = json.dumps(
                {**safe_record, "tracking_click_id_candidate": tracking_click_id_candidate},
                sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            )
            safe_record["event_key"] = hashlib.sha256(event_material.encode("utf-8")).hexdigest()
            safe_record["source_fingerprint"] = hashlib.sha256(source_material.encode("utf-8")).hexdigest()
            safe_record["tracking_click_id_candidate"] = tracking_click_id_candidate
            normalized.append(safe_record)

    # A page can contain repeated line-item records; keep one normalized observation per source identity.
    deduplicated: dict[tuple[str, str], dict[str, Any]] = {}
    for record in normalized:
        deduplicated[(record["event_key"], record["source_fingerprint"])] = record
    return list(deduplicated.values()), skipped_unidentified, skipped_scope


async def _request_clickbank_orders_page(
    api_key: str,
    *,
    account: str,
    start_date: date,
    end_date: date,
    page: int,
) -> tuple[Any, int]:
    params = {
        "affiliate": account,
        "role": "AFFILIATE",
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
    }
    headers = {
        "Authorization": api_key,
        "Accept": "application/json",
        "Page": str(page),
    }
    async with open_public_http_response(
        CLICKBANK_ORDERS_LIST_URL,
        method="GET",
        params=params,
        headers=headers,
        timeout=12.0,
    ) as response:
        status = int(response.status_code)
        if 300 <= status < 400:
            raise ClickBankProviderUnavailable("ClickBank Orders API redirects are not followed.")
        if status not in {200, 206}:
            response.raise_for_status()
            raise ClickBankProviderUnavailable(f"ClickBank returned unsupported Orders status {status}.")
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type not in {"application/json", "application/problem+json"}:
            raise ClickBankProviderUnavailable("ClickBank returned an unsupported Orders response content type.")
        body = await read_limited_response(response, max_bytes=512_000)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise ClickBankProviderUnavailable("ClickBank returned invalid Orders JSON.") from None
    if not isinstance(payload, (dict, list)):
        raise ClickBankProviderUnavailable("ClickBank returned an unexpected Orders response.")
    return payload, status


async def fetch_clickbank_order_transactions(
    api_key: str,
    *,
    account: str,
    start_date: date,
    end_date: date,
    start_page: int = 1,
    max_pages: int = 5,
) -> dict[str, Any]:
    """Read affiliate-scoped Orders rows with bounded pagination and PII minimization."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", account):
        raise ClickBankAccessError("The selected ClickBank affiliate nickname is invalid.")
    if start_page < 1 or start_page > 1000 or max_pages < 1 or max_pages > 10:
        raise ValueError("ClickBank Orders pagination is outside the allowed range.")

    transactions: list[dict[str, Any]] = []
    skipped_unidentified = 0
    skipped_scope = 0
    source_order_count = 0
    pages_retrieved = 0
    has_more = False

    for page in range(start_page, start_page + max_pages):
        try:
            payload, status = await _request_clickbank_orders_page(
                api_key,
                account=account,
                start_date=start_date,
                end_date=end_date,
                page=page,
            )
        except httpx.HTTPStatusError as exc:
            status_code = int(exc.response.status_code)
            if status_code in {401, 403}:
                raise ClickBankAccessError(
                    "ClickBank rejected affiliate Orders access. Confirm API Order Read permission for the selected account nickname."
                ) from None
            if status_code == 429:
                raise ClickBankProviderUnavailable("ClickBank rate-limited the Orders request. Try again later.") from None
            raise ClickBankProviderUnavailable(f"ClickBank returned HTTP {status_code} while retrieving Orders.") from None
        except (httpx.RequestError, TimeoutError):
            raise ClickBankProviderUnavailable("Could not reach ClickBank's Orders endpoint.") from None
        except ValueError as exc:
            raise ClickBankProviderUnavailable(str(exc)) from None

        page_rows = _clickbank_order_rows(payload)
        source_order_count += len(page_rows)
        records, page_skipped, page_scope_skipped = _normalize_clickbank_order_rows(payload, account=account)
        transactions.extend(records)
        skipped_unidentified += page_skipped
        skipped_scope += page_scope_skipped
        pages_retrieved += 1

        if status == 200:
            has_more = False
            break
        has_more = page == start_page + max_pages - 1

    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for transaction in transactions:
        unique[(transaction["event_key"], transaction["source_fingerprint"])] = transaction

    return {
        "account": account,
        "transactions": list(unique.values()),
        "pages_retrieved": pages_retrieved,
        "source_order_count": source_order_count,
        "skipped_unidentified_count": skipped_unidentified,
        "skipped_scope_count": skipped_scope,
        "has_more": has_more,
        "next_page": start_page + pages_retrieved if has_more else None,
    }
