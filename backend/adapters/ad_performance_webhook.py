from __future__ import annotations

import hashlib
import hmac


class AdPerformanceWebhookAdapter:
    """Verify HMAC-SHA256 from a trusted collector for one workspace/platform.

    Provision the signing key only to a collector that has independently verified the
    native platform response. This class authenticates the collector and does not
    claim to verify Meta, Google, TikTok, or another native provider signature.
    """

    def __init__(self, secret: str):
        if not isinstance(secret, str) or len(secret) < 32:
            raise ValueError("Ad performance webhook secret must contain at least 32 characters")
        self._secret = secret.encode("utf-8")

    def verify(self, raw_body: bytes, signature: str) -> bool:
        if not isinstance(raw_body, bytes) or not isinstance(signature, str):
            return False
        candidate = signature.strip()
        if candidate.startswith("sha256="):
            candidate = candidate[len("sha256="):]
        if len(candidate) != hashlib.sha256().digest_size * 2:
            return False
        try:
            bytes.fromhex(candidate)
        except ValueError:
            return False
        expected = hmac.new(self._secret, raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, candidate.lower())
