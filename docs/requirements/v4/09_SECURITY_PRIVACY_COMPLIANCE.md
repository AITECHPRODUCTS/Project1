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


## 2026-10-26 credentialed CMS transport — verified
- Implementation `13ec393d0897c4ba75ed83ba6bed8ce8690f7c06` passed push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290026088 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290033400.
- WordPress/Ghost credentialed POSTs use the pinned-IP transport, preserve Host/SNI, disable redirects and proxy env, and cap response bodies at 2 MiB. Four regression tests passed, including redirect and oversized-response cases.
- Python suite: 305 passed, 2 skipped. PostgreSQL, AI/RAG, frontend, security audits, skill parity and lockfile sync all passed. `CMS_PUBLISH_EXECUTE` remains the live-publication gate.
- Remaining release blockers include four documented Chroma advisories, trusted-proxy ingress staging verification, provider live UAT, SBOM/license/secret evidence, deployment smoke and backup/restore.


## 2026-10-26 fixed credentialed provider endpoints — candidate
- The verified CMS transport is pinned; remaining bare HTTPX clients exist for Resend, Reddit/X, Pinterest/Reddit and Meta campaign pause, all using fixed official-provider endpoints but bypassing the same no-proxy/no-redirect/pinned-IP policy.
- Candidate migrates these calls to the shared helper with JSON/form POST support, timeouts and bounded JSON responses. Email idempotency and ad/publishing execution gates remain unchanged. Exact-SHA tests/CI are pending.


## 2026-10-26 generic affiliate adapter transport — candidate
- `ConfiguredJSONAdapter` previously called `validate_public_http_url` then connected with a separate `httpx.AsyncClient`. This was the last direct provider client found outside the shared pinned transport after scanning 59 Python modules under backend and AI memory.
- Candidate uses `request_public_json`, applies a 2 MiB cap, retains HTTPS-only construction and the configured item extraction, and adds a loopback-denial + mocked request-contract test pair.
- Do not call this fixed until the full push and PR runs pass on the candidate SHA.

## 2026-10-26 generic affiliate adapter egress boundary — verified
- Exact SHA `aa3a0e175c09df3572f077b1c76d565ec2776207`, push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40301426819, PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40301436060: both full workflows passed.
- `ConfiguredJSONAdapter` now calls `request_public_json` directly rather than checking DNS then opening a separate client. The helper pins the connection to a vetted public address, disables ambient proxies/redirects and caps JSON responses at 2 MiB.
- Regression coverage includes loopback rejection through the actual helper and a request-contract test. The 59-module source scan found no other raw clients outside the central URL-safety transport.
- Actual staging proxy ingress remains unverified; config validation alone does not prove trusted forwarding behavior.


## 2026-10-26 RAG vector-store security remediation — candidate
- Replace ChromaDB with a local SQLite vector index and remove the Chroma integration package from the optional AI profile; do not hide upstream advisories behind ignore flags.
- The candidate adds deterministic tests for on-disk persistence, normalized cosine retrieval, stable-ID upsert/delete, collection separation, embedding-model/dimension consistency and malformed vector rejection. A CI static guard checks active dependencies/runtime do not reintroduce Chroma or unsafe pickle deserialization.
- Verification is pending full push/PR CI on the exact candidate SHA and an unignored AI/RAG dependency audit. The historic Chroma advisory IDs remain in the exception record only to explain why the dependency is being removed; they must not be ignored by the new pipeline.
