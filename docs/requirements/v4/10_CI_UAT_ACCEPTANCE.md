# CI, UAT and acceptance gates

## GitHub workflow
`.github/workflows/ci.yml` runs on pushes to main/build/**, pull requests to main and manual dispatch. Python verification, Alembic empty SQLite upgrade/drift check, compilation and tests are the backend checks; the frontend uses the committed npm lockfile and `npm ci`, followed by TypeScript typecheck and Next.js production build. A separate `security-audit` job runs `pip-audit` on core/test and optional AI/RAG requirements plus `npm audit --audit-level=high`; its findings must be remediated rather than waived without documented review.

## Required full release gates
- Exact candidate SHA has clean backend test run, front-end typecheck/build, migration graph/upgrade/drift, and dedicated PostgreSQL integration tests.
- API tests cover auth, positive/negative permission, cross-tenant denials, consent, error paths, idempotency and webhook state transitions.
- RAG gold-query/retrieval and generated claim/evidence metrics meet thresholds; prompt injection/poisoned source tests pass.
- Provider tests use authorized sandboxes/accounts, never fake successful connection responses.
- Browser UAT at all specified viewports; accessibility, keyboard/screen reader, performance and responsive table checks.
- Security, dependency licenses, SBOM, secret scan, backup/restore, rollback and staging smoke tests pass.
- Attach actual commit SHA, workflow links/artifacts and result. Missing/no run is `NOT RUN`, not PASS.


## Last verified dependency baseline
- Exact candidate SHA: `e6e6eb4e552b4887da252db0df172dd25ee79561`.
- Push: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40213802242 (success).
- Pull request: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40213808545 (success).
- The successful candidate's regular frontend job used `npm ci`, passed typecheck and production build, and the push-only lockfile sync job passed. Security-audit was added after this checkpoint and needs fresh exact-SHA CI evidence.


## Dependency audit findings — remediation required
- Initial scan of candidate `f129ecf4576f1d35229525669613ecebcf17d65b` reported Pillow 12.3.0 advisories fixed in 13.0.0 and pytest 8.4.2 advisory fixed in 9.0.3. The repository now requires Pillow 13.0.0+ and pytest 9.0.3+; this is not considered resolved until the full Python regression suite and all audit profiles pass on the new exact SHA.
- Because the first Python audit failed early, it did not complete the optional AI/RAG scan or npm audit. Those outcomes must come from a subsequent full run; do not infer a clean result.

- Follow-up dependency resolver finding: the repository previously restricted pytest-asyncio to `<1.0`, which conflicts with the fixed pytest 9.0.3 range. The declared plugin range is now `>=1.3.0,<2.0`; verify installation, test compatibility and audit results on the next candidate SHA.


## AI/RAG dependency-audit exception
- The current ChromaDB 1.5.9 advisory records identify four unpatched IDs and no fixed PyPI release at the time of review. The only permitted temporary CI exception is enumerated in `docs/SECURITY_EXCEPTIONS.md` and is conditional on `scripts/verify_chroma_security_boundary.py` passing. This is not a clean dependency scan or production approval. Replace Chroma or remove the exception after an upstream fix, then rerun audits and full RAG retrieval evaluation.


## 2026-10-26 exact-SHA full matrix
- Candidate `668b33670ea11e30f97ccc3c6e50180124609207`: push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264037056 and PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264040473 both passed.
- Confirmed: repository guard/53-skill parity, Python suite, SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG imports, frontend `npm ci`/typecheck/build, core/test and AI/RAG audits, frontend `npm audit --audit-level=high`, and lockfile sync.
- The ChromaDB temporary exception remains a release blocker; these successful runs must not be presented as complete production release approval.

## 2026-10-26 CI runtime maintenance
- Workflow actions were using old releases with Node 20 runtime warnings. Node 20 was removed from GitHub-hosted Actions on 23 September 2026; action releases must support Node 24. This checkpoint updates those action versions; validate the exact updated workflow before advancing.


## 2026-10-26 CI runtime update verified
- Exact SHA `70dd041a8c27607467f8605d1eabad09f815d2bf`: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264278741 — success using Node 24-compatible `checkout@v7`, `setup-python@v7`, `setup-node@v7`, `upload-artifact@v7`, and `download-artifact@v8`.
- Next: the newly added auth/tenancy regression tests are not yet verified; require full CI on their commit. The Chroma exception remains a production security blocker.


## 2026-10-26 WebSocket tenancy P0 regression gate
- Require passing tests showing workflow/HITL events reach only sockets registered to the matching workspace, scope-less event payloads reach no client, and a connection using a revoked workspace membership is rejected.
- This candidate source fix and tests are not complete until the full Python, PostgreSQL, AI/RAG, frontend, repository guard and security-audit jobs pass on the exact new commit SHA.


## 2026-10-26 WebSocket tenant isolation — exact-SHA verification
- Verified fix and tests on `65a5a884acf0195a2720cb6de76a5279fd4e5dde`: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265255592 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265259440 both passed.
- Required test assertions include workspace-matched event delivery only, scope-less event dropping, workflow emitter scope propagation, and denied connection for revoked membership.
- Next: workflow run status/pause/resume/retry/cancel must verify actor and workspace ownership, with negative cross-tenant tests.


## 2026-10-26 workflow lifecycle ownership — verified
- Candidate SHA 16eee55a6935e9afa1d5f2b020c867713754aa67: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265845238 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265848400 both completed successfully.
- Checks include Python suite with workflow/tenant tests, PostgreSQL migrations and concurrent reversal test, AI/RAG imports, frontend checks/build, 53-skill source guard, audits and lockfile verification.
- Remaining conditional exception: four documented ChromaDB advisories still prevent a clean AI/RAG security result and production approval.
- Next P0 review: gate shared knowledge-index ingestion to platform operations and remove internal absolute path leakage.


## 2026-10-26 shared knowledge-index permission — verified
- Exact SHA `743e404e63b7c3a54423a18b1cf17af1338c5abf`: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40266330644 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40266336192 both succeeded.
- Checks include the new knowledge-index admin/path tests; Python suite, PostgreSQL migration/concurrency, AI/RAG imports, frontend checks/build, repository source and skill parity guard, security audit, and lockfile reproducibility.
- Keep production release blocked by the four documented ChromaDB advisory exceptions and outstanding provider authorization, browser/UAT, SBOM/license/secret scanning, deployment smoke, and backup/restore gates.
- Next: verify resource-budget and learning aggregate scoping under tenant and scheduled execution.

## 2026-10-26 campaign/conversion workspace binding — verified
- Candidate SHA `4becae03e155fedc361e5b9fcdfc9fde66602f75`: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268073324 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268078547 both passed.
- Tests prove unscoped users are denied campaign and conversion routes; workspace A cannot see or operate on workspace B's campaign; conversion idempotency is per workspace; and Conversion plus immutable ledger entries use the selected workspace.
- Continue source audit of remaining tenant-owned asset, lead, scheduled-email and public-capture routes before release. The four documented ChromaDB advisory exceptions remain a separate P0 production blocker.


## 2026-10-26 blog/lead/email workspace boundary — verified
- Candidate SHA `929035b6429f4a1fa9a0c9c31cbc35834ab72dc9`: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40269971909 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40269976725 both passed.
- The Python job passed the six new tenant-boundary tests. PostgreSQL, SQLite migration/drift, AI/RAG, frontend, dependency security audit, 53-skill parity and lockfile checks also passed.
- Next release gate: explicit authorization and approval coverage for social publishing/other external side effects, plus the documented ChromaDB advisory exception and broader production UAT/deployment/backup evidence.



## 2026-10-26 external publishing authorization — candidate
- Base `31826a37d7494050457606c963aefba3421dceb9` passed push [40270284075](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270284075) and PR [40270289947](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270289947).
- Candidate regressions cover missing authentication, workspace-admin denial for global credentials, live-confirmation enforcement, audit persistence and explicit workspace binding for landing tokens. The candidate is not verified until its own push and PR runs both pass.


## 2026-10-26 external-publishing authorization — verified
- Exact SHA `6f3994096e502911b23fb54e8cb94c3f2181a16d`; push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270795625 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270800499 both passed.
- Six new route tests prove authentication and role restriction for global social/CMS provider credentials, explicit workspace binding for landing token issuance, live confirmation, and workspace-scoped audit persistence.
- Existing `PUBLISHING_DRY_RUN=true` default and `CMS_PUBLISH_EXECUTE=false` default remain in force; live operations additionally require the explicit request confirmation.
- Next: review workflow step execution and remaining provider mutation endpoints. The four ChromaDB advisory exceptions, broader provider UAT, deployment smoke and backup/restore remain open release gates.

## 2026-10-26 workflow-stage side-effect boundary — verified
- Based on `ccbd4a821707f7d95b9a7cce3911dfa2735d3138`, where the previous auth/token/publishing hardening had passed CI. The verified change adds five tests covering S5 live side-effect authorization, audit events, S6 tenant dedup, and missing workspace denial.
- Verified corrected SHA `64a2d30af5dddb79150428936993ef1811b4419f`: push [40275131255](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275131255) and PR [40275135461](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275135461) both passed. Python 255 passed/2 skipped, SQLite and PostgreSQL migration checks/concurrency, AI/RAG 9 imports, frontend production build, dependency/security audit, repo guard and push lockfile reproducibility passed.
## 2026-10-26 scheduled-email delivery idempotency — verified
- Exact SHA `fedd1f74dbaa33e210b0587c774bc2ad63d92b8d`; push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40276085004 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40276090006 both passed.
- Alembic revision `0008_scheduled_email_delivery_claims` adds a nullable claim timestamp and workspace/status/claim index. Conditional update claims ensure only one worker transitions a due row from scheduled/retry into sending. Provider requests use stable idempotency keys and stored unsubscribe links.
- Python passed 258 tests with 2 skipped; PostgreSQL migration/concurrency, SQLite migration/drift, AI/RAG 9 imports, frontend build, security audit, repo guard and push lockfile sync passed. Stale ambiguous sends outside the 23-hour automatic retry window require manual reconciliation.

## 2026-10-26 workflow side-effect retry safety — verified
- Exact SHA `3dc01b9b954bf0ec392aafed522c4ec968faffa9`; push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40277040070 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40277047842 both passed.
- Python 260 passed/2 skipped, SQLite and PostgreSQL migrations/drift/concurrency passed, AI/RAG 9 imports, frontend production build, dependency audit, repository guard and push lockfile sync passed.
- Regression test verifies a side-effecting S5 timeout/connection failure is attempted once, produces the durable `workflow.side_effect_outcome_unknown` audit event, and instructs reconciliation. A read-only stage still retries transient connection failures per configuration.
- Production remains blocked by documented ChromaDB advisory exceptions and outstanding comprehensive provider UAT, SBOM/license/secret checks, deployment smoke, and backup/restore evidence.

## 2026-10-26 external-action idempotency — candidate
- Validate migration 0009, database idempotency key uniqueness, payload fingerprint mismatch conflicts, completed-response replay, 428 for missing live-write key, and ambiguous-result quarantine under same and alternate keys.
- Do not mark verified until exact-SHA push/PR Python, SQLite/PostgreSQL migration/drift/concurrency, AI/RAG, frontend, security, repo guard and lockfile jobs pass.


## Provider-write idempotency candidate — CI correction
- Corrected an existing live-social authorization test to supply `Idempotency-Key`, which is now required for live external provider writes. The initial candidate run failed only this fixture expectation (1 failed, 263 passed, 2 skipped); exact-SHA CI rerun pending.


## 2026-10-26 provider-write idempotency — verified
- SHA `1cc839bbf80d1a66e35b9e36f244b4fa13cb68af`: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40278503530 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40278508177 both passed.
- Four idempotency regressions passed; total Python suite 264 passed, 2 skipped. Migration 0009, PostgreSQL migration/concurrency, SQLite drift, AI/RAG 9 imports, front-end build, security audit, repository guard and lockfile sync all passed.
- Next: include S5 workflow provider writes in the durable registry; verify manual workflow resubmissions cannot bypass direct-route idempotency.


## 2026-10-26 workflow S5 request idempotency — verified
- Exact implementation SHA `e7ca02df933c3028489e8c3ba1abbfba3d82ae90`; push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279412060 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279416167 both passed.
- Python 267 passed/2 skipped; PostgreSQL migration/concurrency, SQLite drift, AI/RAG 9 imports, frontend build, dependency audit, 53-skill guard and push lockfile sync all passed.
- S5 shares the tenant-scoped ExternalAction registry, requires live workflow keys at both API and service boundaries, derives stable per-item keys, replays completed actions and blocks unknown outcomes until reconciliation.


## 2026-10-26 global offer sync authorization — verified
- Exact SHA `498c0b595a8dd158b06eae2924f87d3897a8525b`; push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279967742 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279972611 both passed.
- Four route tests verify ordinary workspace members and platform admins lacking an active workspace cannot trigger the upstream sync, successful sync updates the global catalog and audits the actor's workspace, and provider failure is audited with a 502 response.
- Python 271 passed/2 skipped; SQLite, PostgreSQL migration/concurrency, AI/RAG profile, frontend production build, dependency audit, repository guard, and push lockfile sync passed.

## 2026-10-26 OpenAffiliate outbound URL validation — verified
- Exact SHA `49043acd6e71841c7d365a97a9d8ca31168cc8da`: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40280504806 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40280508646 both passed.
- Two new URL-safety tests passed. Python 273 passed/2 skipped; frontend, security, repository guard, SQLite/PostgreSQL migration/concurrency, AI/RAG and push lockfile jobs all passed.
- The OpenAffiliate client validates its composed URL before opening an HTTP client on cache misses and retains redirects disabled. Four ChromaDB advisory exceptions and production release gates remain open.

