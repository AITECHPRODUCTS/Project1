# Security, privacy and compliance

- Enforce workspace/object-level authorization on every API, webhook, background job, WebSocket, export and file path. Global admin requires separate auth and audited justification.
- Protect session rotation/expiry/revocation, password hashing/reset, login abuse, CSRF, CORS, cookie flags, secret rotation and least-privilege roles. Never expose secrets to browser code or logs.
- SSRF guard: restrict schemes, credentials, internal/link-local/reserved IPs, redirects, uploads and DNS rebinding; verify the actual connected address and block policy bypass.
- Verify webhook HMAC/signatures, timestamps, replay/idempotency and event ordering; rate-limit public endpoints and sanitize error payloads.
- Treat websites, comments, RAG documents, skill files and model outputs as untrusted data; prompt/tool injection cannot alter policy or cross tenant.
- Disclose affiliate relationships clearly, keep claim evidence, honor source/license rights, consent and email unsubscribe/suppression, data deletion/retention and jurisdiction-specific provider rules.
- Run dependency/license/SBOM and secret scans; security tests cover horizontal tenant access, CSRF/CORS, SSRF, webhook replay, abuse, model prompt injection, logging redaction and backup/restore.
- The repository is public by user choice. Do not commit private provider credentials, user data or proprietary model artifacts.


## 2026-10-26 outbound fetch/video SSRF work — candidate
- Candidate replaces check-then-resolve behavior with a pinned-IP transport (Host/SNI preserved), disables implicit proxy-environment routing and redirects, enforces total request deadlines and content-size checks, and adds media-type limits.
- Video generation enforces Pexels response/media caps, validates source and actual clip duration, caps narration at 180 seconds, restricts output paths to the configured video directory, and caps encoded output at 500 MiB.
- Competitor research is authenticated, workspace-bound and rate-limited; each supplied URL is bounded in length.
- New tests are pending exact-SHA hosted CI. Production ingress/trusted-proxy settings still require staging verification.
