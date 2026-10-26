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


## 2026-10-26 public fetch/video hardening — exact-SHA verified
- Verified candidate `f2d232f7ce5efaea2e3d1abca8a6ba7e47cf339c`: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40288412469 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40288420524 both completed successfully.
- Regression coverage and the full matrix passed: Python 301 passed, 2 skipped; PostgreSQL migrations/concurrency; AI/RAG import profile (9 imports); frontend typecheck/build; dependency audit; 53-skill guard; lockfile reproduction.
- DNS-rebinding prevention is addressed by a connection-pinned shared helper with explicit Host/SNI handling, no env proxies/redirects, total deadline and declared/streamed body limits. Pexels media and narration/output caps were added; competitor page fetching is now workspace-authenticated/rate-limited.
- Trusted-proxy config and staging ingress proof remain outstanding; the documented Chroma advisory exceptions remain a security-release blocker.


## 2026-10-26 CMS provider DNS-rebinding boundary — candidate
- Existing CMS code checked the configured hostname and then sent credentialed WordPress/Ghost POST requests via a separate HTTPX client. DNS rebinding could change the actual destination after validation.
- Candidate routes CMS JSON POSTs through the shared pinned-IP helper, refuses redirects and proxy-environment routing, and caps provider response bodies at 2 MiB.
- Existing live publish flag remains mandatory. Four regression tests have been added; full exact-SHA CI is pending.
