# Security, privacy and compliance

- Enforce workspace/object-level authorization on every API, webhook, background job, WebSocket, export and file path. Global admin requires separate auth and audited justification.
- Protect session rotation/expiry/revocation, password hashing/reset, login abuse, CSRF, CORS, cookie flags, secret rotation and least-privilege roles. Never expose secrets to browser code or logs.
- SSRF guard: restrict schemes, credentials, internal/link-local/reserved IPs, redirects, uploads and DNS rebinding; verify the actual connected address and block policy bypass.
- Verify webhook HMAC/signatures, timestamps, replay/idempotency and event ordering; rate-limit public endpoints and sanitize error payloads.
- Treat websites, comments, RAG documents, skill files and model outputs as untrusted data; prompt/tool injection cannot alter policy or cross tenant.
- Disclose affiliate relationships clearly, keep claim evidence, honor source/license rights, consent and email unsubscribe/suppression, data deletion/retention and jurisdiction-specific provider rules.
- Run dependency/license/SBOM and secret scans; security tests cover horizontal tenant access, CSRF/CORS, SSRF, webhook replay, abuse, model prompt injection, logging redaction and backup/restore.
- The repository is public by user choice. Do not commit private provider credentials, user data or proprietary model artifacts.
