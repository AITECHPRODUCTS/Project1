from __future__ import annotations

import base64
import hashlib
import hmac
from decimal import Decimal, ROUND_HALF_UP
from cryptography.fernet import Fernet, InvalidToken

from backend.config import get_settings


class MerchantWebhookCredentialError(RuntimeError):
    pass


def _credential_key() -> bytes:
    secret = str(get_settings().app_session_secret or "")
    if len(secret) < 32:
        raise MerchantWebhookCredentialError(
            "APP_SESSION_SECRET is not configured strongly enough for merchant webhook credentials."
        )
    return hashlib.sha256(
        b"omni-affiliate-merchant-webhooks:v1:" + secret.encode("utf-8")
    ).digest()


def _cipher() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_credential_key()))


def encrypt_merchant_webhook_secret(secret: str) -> str:
    if not isinstance(secret, str) or len(secret) < 32:
        raise MerchantWebhookCredentialError("Merchant webhook signing secrets must contain at least 32 characters.")
    return _cipher().encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_merchant_webhook_secret(ciphertext: str, key_version: int = 1) -> str:
    # This field versions the merchant signing secret, not the Fernet key derivation.
    # A signing-secret rotation must not make the newly encrypted value undecryptable.
    if not isinstance(key_version, int) or key_version < 1:
        raise MerchantWebhookCredentialError("Stored merchant webhook credential version is invalid.")
    try:
        return _cipher().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError):
        raise MerchantWebhookCredentialError(
            "Stored merchant webhook credential cannot be decrypted; rotate the integration secret."
        ) from None


def fingerprint_merchant_webhook_secret(secret: str) -> str:
    return hmac.new(_credential_key(), secret.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_merchant_webhook_signature(raw_body: bytes, supplied_signature: str, secret: str) -> bool:
    if not isinstance(raw_body, bytes) or not isinstance(supplied_signature, str) or len(secret) < 32:
        return False
    candidate = supplied_signature.strip()
    if candidate.lower().startswith("sha256="):
        candidate = candidate[7:]
    if len(candidate) != 64:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, candidate.lower())


def calculate_merchant_commission(
    commission_type: str,
    commission_value: Decimal,
    revenue: Decimal,
) -> Decimal:
    if commission_type in {"percentage", "recurring_percentage"}:
        amount = revenue * commission_value / Decimal("100")
    elif commission_type in {"fixed", "recurring_fixed", "cpa", "cpl"}:
        amount = commission_value
    else:
        raise ValueError("Unsupported merchant commission model")
    result = amount.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    if result < 0 or result >= Decimal("1000000000000"):
        raise ValueError("Calculated commission is outside the supported ledger range")
    return result
