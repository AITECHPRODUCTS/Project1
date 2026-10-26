from __future__ import annotations
import hmac, json, logging, re
from typing import Any
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)
SENSITIVE = re.compile(r"(?<![a-z0-9])(bank|payout|tax|wire|withdrawal|withdraw|payment_method|routing_number|iban|swift)(?![a-z0-9])", re.I)
SAFE_READS = {"/api/finance/ledger", "/api/finance/thresholds"}
SAFE_SYSTEM = {"/health", "/docs", "/openapi.json", "/redoc"}

def _payload_has_sensitive_operation(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).replace("-", "_").lower()
            if SENSITIVE.search(normalized): return True
            if normalized in {"action", "operation", "endpoint", "resource", "command"} and isinstance(child, str) and SENSITIVE.search(child): return True
            if _payload_has_sensitive_operation(child): return True
    elif isinstance(value, list): return any(_payload_has_sensitive_operation(item) for item in value)
    return False

class FinancialSandboxMiddleware(BaseHTTPMiddleware):
    """Deny finance mutation routes/structured actions. Actual transfers are never implemented."""
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        safe_read = request.method in {"GET", "HEAD"} and path in SAFE_READS
        if path not in SAFE_SYSTEM and not safe_read and SENSITIVE.search(path + "?" + request.url.query):
            return JSONResponse(status_code=403, content={"detail":"Financial operations are human-only.","code":"FINANCIAL_SANDBOX_BLOCK"})
        if request.method in {"GET", "HEAD", "OPTIONS"}: return await call_next(request)
        body = await request.body(); payload: Any = None
        if body:
            if "application/json" in request.headers.get("content-type", ""):
                try: payload = json.loads(body)
                except (ValueError, UnicodeDecodeError): payload = {"unparsed_body": body[:2048].decode("utf-8", "ignore")}
            else: payload = {"unparsed_body": body[:2048].decode("utf-8", "ignore")}
        if _payload_has_sensitive_operation(payload):
            logger.warning("Financial sandbox blocked structured operation at %s", path)
            return JSONResponse(status_code=403, content={"detail":"Financial operations are human-only.","code":"FINANCIAL_SANDBOX_BLOCK"})
        async def receive(): return {"type":"http.request","body":body,"more_body":False}
        request._receive = receive
        return await call_next(request)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Require a per-session CSRF header for browser-session mutation routes."""

    EXEMPT_EXACT = {"/api/auth/login", "/api/auth/register", "/api/public/leads/capture"}

    async def dispatch(self, request: Request, call_next) -> Response:
        method = request.method.upper()
        if method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            return await call_next(request)
        path = request.url.path
        if path in self.EXEMPT_EXACT or path.startswith("/api/public/webinars/") or path.startswith("/api/webhooks/") or path.startswith("/unsubscribe/"):
            return await call_next(request)
        session = request.scope.get("session") or {}
        if session.get("user"):
            expected = str(session.get("csrf_token") or "")
            supplied = request.headers.get("x-csrf-token", "")
            if not expected or not supplied or not hmac.compare_digest(expected, supplied):
                return JSONResponse(status_code=403, content={
                    "detail": "CSRF validation failed. Refresh the session before retrying.",
                    "code": "CSRF_VALIDATION_FAILED",
                })
        return await call_next(request)
