# Requirement-to-code backlog

| ID | Area | Current evidence | Status | Acceptance still required |
|---|---|---|---|---|
| R-01 | S1 offer discovery and traffic screening | `backend/tools/affiliate_api.py`, `backend/services/s1_research.py`, `backend/services/traffic_analyzer.py`, `POST /api/research/traffic-analyzer` | partial | Authorized live source/freshness, real provider contracts, verified analytics metrics and geo validation |
| R-02 | S2 content intelligence | `backend/services/s2_s3_content.py`, `backend/services/llm.py` | partial | Claim ledger and grounding evaluation |
| R-03 | S3 SEO/blog | `backend/services/s2_s3_content.py`, `backend/services/content_decay_detector.py`, `backend/services/content_moat_calculator.py`, the content-decay and content-moat API routes | partial | Search Console ingestion, validated competitor/page counts, keyword demand, technical crawl and publish UAT |
| R-04 | S4 landing/consent | `backend/services/s4_s5_landing.py`, `backend/services/email_delivery.py` | partial | Accessibility and full consent/unsubscribe tests |
| R-05 | S5 distribution | `backend/services/s4_s5_landing.py`, `backend/services/cms_publisher.py` | partial | OAuth scopes, remote success and idempotency |
| R-06 | S6 attribution/ledger | `backend/services/tracking_service.py`, `backend/models.py`, `POST /api/webhooks/conversions/{network}` | partial | Signed bounded webhook input, per-network secrets, workspace idempotency, row-locked reversals, Numeric(18,6) append-only ledger/backfill and a read-only evidence-separated finance UI are implemented; commit `67df5a275176ebda09fa2e2f7aec041928c4e126` passed push/PR CI including PostgreSQL trigger tests. Still required: provider reconciliation, partial-reversal semantics, provider-specific signature contracts, browser UAT and end-to-end provider evidence |
| R-07 | S7 operations/budgets | `backend/services/resource_budget.py`, `backend/core/state_machine.py` | partial | Durable worker lease and distributed budget locking |
| R-08 | S8 learning | `backend/services/s6_s8_analytics.py`, `ai_memory/rag_chain.py` | partial | Independent evaluation and reversible promotion |
| R-09 | Provider catalogue | `config.yaml`, `backend/services/integration_registry.py` | catalogued/partial | Per-provider live auth, scope, contract and health evidence |
| R-10 | Autopilot truth table | `backend/services/capability_matrix.py`, `GET /api/capabilities` | implemented, not environment-verified | UI/API end-to-end and provider state sync |
| R-11 | Responsive control center | `frontend/app/page.tsx`, `frontend/components/FlywheelVisualizer.tsx` | present, unverified | Multi-viewport browser and accessibility UAT |
| R-12 | Production schema | `migrations/versions/0001_initial_schema.py`; exact-SHA CI at `e6e6eb4e552b4887da252db0df172dd25ee79561` | PostgreSQL upgrade/downgrade/drift and reversal integration pass in push/PR runs | Production backup/restore rehearsal, rollback evidence and deployed database operations |
| R-13 | Tenant SaaS | `backend/models.py`, `backend/main.py` | major gap | Workspace schema, row-level scope and cross-tenant tests |
| R-14 | Platform Super Admin | requirements and current global admin gaps | not implemented end-to-end | Separate platform RBAC, tenant/incident/kill switch UI |
| R-15 | All 53 skills | `../skill-parity-matrix.csv` | 47 partial, 6 not implemented | Implement and verify each skill service/API/UI/provider path |
| R-16 | Production release | Actions + deployment docs | not release ready | All required CI, provider, security, staging and rollback gates |

| R-17 | Affiliate portfolio operations | `backend/services/multi_program_manager.py`, `POST /api/automation/multi-program-manager` | partial | Authorized network data and payout reconciliation, attribution quality, program-action UAT |

| R-18 | P0 — pinned skill source/traceability | `knowledge/affiliate-skills/upstream/SOURCE_MANIFEST.json`; 53 vendored skill documents; `scripts/verify_skill_registry.py`; repo-guard CI on `e6e6eb4e552b4887da252db0df172dd25ee79561` | source integrity and registry/status parity guard passed on exact push/PR SHA; runtime 47 partial / 6 not implemented | Per-skill service/API/UI/provider acceptance, retrieval evaluation and provider authorization remain independently required |

| R-19 | P0 — reproducible frontend dependencies | `frontend/package-lock.json` (npm lockfile v3, 141 packages); `npm ci` typecheck/build on exact SHA `e6e6eb4e552b4887da252db0df172dd25ee79561` | implemented and CI-verified on push/PR; lockfile-sync passed on push | Continue running `npm ci`; add SBOM/license/secret scans and keep dependency audit findings remediated |

| R-20 | P0 — dependency security audits | `.github/workflows/ci.yml` `security-audit`; core/test and AI/RAG `pip-audit`; frontend `npm audit`; `docs/SECURITY_EXCEPTIONS.md` | Push run [40264037056](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264037056) and PR run [40264040473](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264040473) passed on `668b33670ea11e30f97ccc3c6e50180124609207`, including core/test audit, guarded AI/RAG audit, and frontend `npm audit --audit-level=high`. Next.js 16.4.3 and patched PostCSS/parser resolutions are locked. Four documented Chroma IDs remain conditionally excepted after local-only guard | Remove the Chroma exception after an upstream fix/vector-store replacement; add SBOM/license/secret-scan evidence and rerun every audit on each release candidate |


## P0 security acceptance follow-up (2026-10-26)
- Test addition: `tests/test_auth_tenancy_guards.py` covers session invalidation when workspace membership is revoked, denial of unscoped static bearer tokens for tenant data, and workspace member denial from admin authorization.
- Verification passed on exact SHA `e715878c76fb6f1876c2ff1769653fa72ad51396`: push run [40264570099](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264570099) completed successfully. Existing route coverage and DB tenant-filter tests do not replace these auth-contract assertions.


## P0 — WebSocket/event tenant isolation (2026-10-26)
- Finding: workflow/HITL events previously lacked workspace IDs, and EventHub broadcast them to every connected WebSocket. The endpoint also did not revalidate active workspace membership at connect time.
- Candidate fix binds event payloads to workspace scope, routes only to same-workspace sockets, rejects scope-less events, and validates membership on connect and recovery.
- Four regression tests added in `tests/test_websocket_tenant_isolation.py`. Verified on exact SHA `65a5a884acf0195a2720cb6de76a5279fd4e5dde`: push [40265255592](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265255592) and PR [40265259440](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265259440) both succeeded.


## P0 — workflow lifecycle tenant ownership (2026-10-26)
- Implemented explicit workspace context at workflow start and required workspace scope for status/resume. Status/resume verify the WorkflowRun and PausedSession belong to the requested workspace; internal paused recovery passes the stored owning workspace. Dashboard status aggregates run tenant queries under the authorized workspace scope.
- Added tests for auth on workflow/status endpoints, cross-workspace status/resume denial, and refusal to start a workflow without workspace context.
- Verified exact SHA 16eee55a6935e9afa1d5f2b020c867713754aa67: push [40265845238](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265845238) and PR [40265848400](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265848400) both succeeded.
- Next P0 audit: require Platform Super Admin for shared RAG knowledge-index ingestion; remove host-local absolute path from end-user status responses and test deny-by-default behavior.


## P0 — shared knowledge-index administration and path disclosure (2026-10-26)
- Shared doctrine ingestion now declares `Depends(require_platform_admin)`; a workspace owner/admin cannot mutate the shared RAG index using their workspace privilege.
- UI renders the ingestion button only to Platform Super Admin. Knowledge status returns only availability/configuration and collection/reference metadata, not the server's resolved filesystem path.
- Added `tests/test_knowledge_admin_access.py` for workspace-owner denial, explicit platform-admin allowed behavior (ingester stubbed), and path non-disclosure.
- Verified exact SHA `743e404e63b7c3a54423a18b1cf17af1338c5abf`: push [40266330644](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40266330644) and PR [40266336192](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40266336192) both succeeded.
- Remaining P0 security issue: four documented ChromaDB advisories remain behind a conditional local-only guard; remove the exception after an upstream fix or a verified vector-store replacement.
- Next: inspect resource-budget/learning summary access under workspace and background execution contexts, then add tests for any tenant leak.

## P0 — campaign/conversion workspace binding verified (2026-10-26)
- Verified on `4becae03e155fedc361e5b9fcdfc9fde66602f75`; push [40268073324](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268073324) and PR [40268078547](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268078547) both green.
- Campaign list/create/health fail closed without a selected workspace and scope reads/writes to the authenticated tenant. API conversion duplicate checks include workspace ID, and both Conversion and ConversionLedgerEntry are explicitly tenant-bound.
- Regression tests deny users without a workspace, prove cross-workspace campaigns are hidden and cross-workspace health is not found, and prove the same provider event ID can be recorded independently in separate workspaces. The older conversion-ledger test now stubs an authorized workspace rather than relying on development fallback while using a fake DB session.
- Next: audit remaining ContentAsset/Lead/ScheduledEmail routes and public lead-capture token binding.


## P0 — blog and lead/email tenant boundary verified (2026-10-26)
- Verified on `929035b6429f4a1fa9a0c9c31cbc35834ab72dc9`; push [40269971909](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40269971909) and PR [40269976725](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40269976725) both succeeded.
- Tenant-owned blog assets and lead/email sequences now require a concrete authenticated workspace or a valid signed public-capture workspace token. Lead and queued-email queries are scoped by workspace; unscoped email delivery is rejected.
- Six new regression tests passed with the full CI matrix, including workspace-specific subscriber identity and sequence idempotency.
- Next P0 audit: review the social-publish endpoint, landing-page token issuance, and other externally impactful provider operations for authentication, workspace ownership, approval and dry-run-by-default semantics.



## P0 — social/CMS external-publish authorization and landing-token issuance (2026-10-26)
- Source audit at `31826a37d7494050457606c963aefba3421dceb9` found unauthenticated social publishing, ambient-only landing token issuance, and CMS publishing authorized by workspace admin despite global provider credentials.
- Candidate requires platform-super-admin plus selected workspace for global provider writes; live social/CMS actions require `confirm_live_publish=true`; success/failure outcomes are written to workspace audit logs; landing token issuance uses the authenticated workspace explicitly.
- Six new regression tests and full exact-SHA CI passed at `6f3994096e502911b23fb54e8cb94c3f2181a16d`: push [40270795625](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270795625) and PR [40270800499](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270800499) both green.


## P0 — external-publishing authorization and landing token binding verified (2026-10-26)
- Verified at `6f3994096e502911b23fb54e8cb94c3f2181a16d`, push [40270795625](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270795625) and PR [40270800499](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270800499) both passed.
- Social and CMS writes with shared global credentials require Platform Super Admin and active workspace; live publishing requires `confirm_live_publish=true`; CMS also preserves the `CMS_PUBLISH_EXECUTE` gate. Success/failure metadata is audited under the selected workspace.
- Landing-page token issuance requires an authenticated active workspace and explicit workspace scope. Six new tests cover the auth/role/workspace/approval/audit behavior; Python reported 250 passed and 2 skipped.
- Next P0: audit workflow runner step handlers and remaining provider mutation endpoints for approvals, idempotency, audit evidence and dry-run enforcement. ChromaDB advisories and release/UAT evidence remain open.

## P0 — workflow-stage publishing and conversion-import isolation verified (2026-10-26)
- At `ccbd4a821707f7d95b9a7cce3911dfa2735d3138`, S5 directly calls `social_media_scheduler` and could bypass route authorization when global publishing is enabled. S6 conversion imports use the runner's ambient scope without an explicit workspace predicate/row field.
- Candidate binds live publishing to authenticated Platform Super Admin plus top-level confirmation and selected workspace, records attempt/outcome audit rows, and makes conversion dedup/insert explicitly workspace-specific.
- Five regression tests passed. Corrected implementation SHA `64a2d30af5dddb79150428936993ef1811b4419f`: push [40275131255](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275131255) and PR [40275135461](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275135461) both completed successfully. Python suite: **255 passed, 2 skipped**, one existing deprecation warning. SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG import profile (**9 imports**), frontend typecheck/production build, dependency security audit, 53-skill repository guard and push lockfile reproducibility all passed.
## Workflow S5/S6 candidate — failed first verification and correction
- Initial candidate `9dcc5f0c842eddaeca86c40ed13d2997c1eddebe`: push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40274907786 reported 2 failures, 253 passed, 2 skipped. One revealed missing explicit workspace in the route-passed metadata (runner added it later); the other was an invalid direct-call fixture supplying forged positive authorization values rather than testing absent authorization.
- Follow-up stamps workspace in trusted API metadata and changes the direct S5 test to ensure untrusted/missing authorization is denied. Corrected SHA `64a2d30af5dddb79150428936993ef1811b4419f` then passed push [40275131255](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275131255) and PR [40275135461](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275135461); Python reported 255 passed, 2 skipped. The initial failure remains recorded above for traceability.
## P0 — scheduled-email duplicate delivery and worker lease verified (2026-10-26)
- The existing due-email worker can race because the status change is committed only after the provider call. Candidate uses conditional atomic claim updates scoped by workspace/status, a migration-backed claim timestamp, and stable Resend idempotency keys.
- Recover claims after 15 minutes only within 23 hours; older ambiguous claims become `delivery_unknown` because Resend documents a 24-hour idempotency-key window. Three regression tests passed. Verified implementation SHA `fedd1f74dbaa33e210b0587c774bc2ad63d92b8d`: push [40276085004](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40276085004) and PR [40276090006](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40276090006) both succeeded. Python suite: **258 passed, 2 skipped**, one existing Starlette/httpx deprecation warning. SQLite upgrade/drift, PostgreSQL migration upgrade/downgrade/drift and concurrency, AI/RAG profile (**9 imports**), frontend typecheck/production build, dependency security audit, 53-skill guard and push lockfile reproducibility all passed.
## Email worker correction trace
- First SHA `7c1b6bab08924a077aa790cbf39130e5eece0aad` failed one stable unsubscribe header assertion (257 passed, 2 skipped; push [40275990654](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275990654), PR [40275995997](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275995997)). Corrected regex at `fedd1f74dbaa33e210b0587c774bc2ad63d92b8d`; push [40276085004](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40276085004) and PR [40276090006](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40276090006) both passed.



## P0 — workflow side-effect retry safety verified (2026-10-26)
- Runner currently retries timeout/connection errors generically, including external publishing in S5; an ambiguous provider result could be duplicated.
- Candidate marks S5 as side-effecting, suppresses transient automatic retries and writes a tenant-scoped reconciliation event. Read-only retry behavior should remain unchanged.
- Two regression tests pending exact-SHA push/PR.

- At `3dc01b9b954bf0ec392aafed522c4ec968faffa9`, the workflow runner marks S5 as side-effecting and suppresses automatic retries after timeout/connection errors that may have occurred after an external provider accepted a post. It persists `workflow.side_effect_outcome_unknown` scoped to the workspace and requires reconciliation before any manual re-submit. Read-only transient retries remain.
- Two regression tests passed and full exact-SHA CI is green. Verified implementation SHA `3dc01b9b954bf0ec392aafed522c4ec968faffa9`: push [40277040070](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40277040070) and PR [40277047842](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40277047842) both passed. Python suite: **260 passed, 2 skipped**, one existing Starlette/httpx deprecation warning. SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG profile (**9 imports**), frontend typecheck/production build, dependency security audit, 53-skill guard and push lockfile reproducibility all passed.

## P0 — manual provider-write idempotency verified (2026-10-26)
- Verified SHA `1cc839bbf80d1a66e35b9e36f244b4fa13cb68af`: push [40278503530](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40278503530) and PR [40278508177](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40278508177) both succeeded.
- Migration 0009 and the tenant-scoped ExternalAction registry ensure direct social/CMS provider claims are durable before the provider call; identical completed requests replay, changed key payloads return 409, missing keys return 428, and ambiguous network/5xx outcomes block same-key and alternate-key repeats until reconciliation.
- Four regression tests passed with Python 264 passed / 2 skipped; full CI passed. Initial CI exposed one stale fixture without an Idempotency-Key; the fixture was corrected without weakening production enforcement.
- Next P0: workflow S5 currently invokes the social adapter directly and must participate in the same idempotency registry to prevent duplicate posts from manually restarted/re-submitted workflows.


## CI correction — live social confirmation test now supplies the idempotency key
- Initial candidate `b3495a58202f944621f43063efbe9d293323ee24` had one test-only failure because the older authorization regression test omitted `Idempotency-Key`; the endpoint's 428 response is intended and the test must exercise the complete provider-write contract.
- Corrected the fixture, keeping production enforcement unchanged. Full exact-SHA push and PR CI are pending.


## P0 — S5 workflow idempotency verified (2026-10-26)
- Verified on `e7ca02df933c3028489e8c3ba1abbfba3d82ae90`; push [40279412060](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279412060) and PR [40279416167](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279416167) both passed.
- S5 uses the shared tenant-scoped ExternalAction registry and stable per-item keys derived from the workflow-level `Idempotency-Key`. Completed actions replay; changed payloads or in-progress/unknown outcomes return conflict and block duplicate side effects.
- Three new workflow S5 tests passed (Python 267 passed / 2 skipped). Full SQLite/PostgreSQL migration/concurrency, AI/RAG, frontend, dependency audit, repo guard, and push lockfile checks passed.
- Next: review remaining provider adapters and externally impactful workflow/worker paths for authorization, idempotency and safe retries.


## P0 — global offer registry sync — verified (2026-10-26)
- Verified at `498c0b595a8dd158b06eae2924f87d3897a8525b`: push [40279967742](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279967742) and PR [40279972611](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279972611) both green.
- `/api/offers/sync` calls OpenAffiliate and updates the global shared `Offer` catalog; it now requires Platform Super Admin and an active workspace used for audit accountability. Unauthorized callers cannot trigger the upstream provider call.
- Audit records include provider, created/updated counts or error type, request limit and query-presence metadata. Four regression tests passed; Python suite 271 passed/2 skipped and full required CI passed.
- Next: review remaining global provider integration/configuration routes for equivalent authorization and audit controls.

## P0 — OpenAffiliate SSRF/network boundary verified (2026-10-26)
- Verified SHA `49043acd6e71841c7d365a97a9d8ca31168cc8da`: push [40280504806](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40280504806) and PR [40280508646](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40280508646) both passed.
- OpenAffiliate now uses `validate_public_http_url` before HTTP-client creation on cache misses and keeps redirects disabled; the existing response byte cap and JSON schema handling remain intact.
- Two regressions passed: private/loopback endpoint is rejected before a client can open; valid provider requests use the validated URL. Python 273 passed / 2 skipped and all required CI jobs passed.
- Next P0 audit: other API routes and provider-configuration/public-read surfaces.



## P0 — shared commission mailbox import authorization verified
- The IMAP host/user/password and sender allowlist are global config. The endpoint previously relied on `require_admin`, which permits workspace admins, and would import messages from the shared mailbox into the caller-selected workspace.
- Verified on exact SHA `0ea1735648ce408fb831abc51179544facd3ed69` via push [40281363532](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40281363532) and PR [40281370173](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40281370173); Python 277 passed/2 skipped and every required CI job passed. Platform Super Admin and selected workspace are required; success/failure audit contains counts/error type only, never mailbox content.


## P0 — shared IMAP commission import verified (2026-10-26)
- Exact SHA `0ea1735648ce408fb831abc51179544facd3ed69`; push [40281363532](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40281363532) and PR [40281370173](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40281370173) succeeded.
- Four tests passed: workspace-admin denied before importer call, platform admin without workspace denied, successful import scoped/audited with only counts, and failure audited by error type/502 without mailbox contents in audit metadata.
- Python 277 passed/2 skipped; full backend, PostgreSQL, AI/RAG, frontend, security audit, repository guard and push lockfile matrix passed.
- Next: global provider/configuration access review. Production is not release-ready while ChromaDB advisories and live-provider/UAT/SBOM/license/secret/deployment/restore evidence remain unresolved.


## P0 — global provider readiness/capability access verified (2026-10-26)
- Candidate changes restrict `/api/integrations` and `/api/capabilities` to Platform Super Admin + active workspace because responses reveal global provider/model/email/CMS/social readiness and missing configuration variable names.
- Existing response status meanings remain unchanged; only access is tightened. Raw credential values are not returned and are covered by sentinel-redaction tests.
- Verified on exact SHA `a0bb0ff23f86b29e7e4a9072d2109e77d0328d40`; push [40282793722](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40282793722) and PR [40282799345](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40282799345) passed; Python 281 passed/2 skipped and all required jobs passed.


## Next P0 — public route abuse/rate limiting
- Audit public tracking, public lead-capture and draft-generation routes for per-IP/token quotas, payload-size limits, budget consumption, bot abuse and trusted-proxy assumptions.
- Inspect existing middleware/edge controls first; make no assumption that a missing route decorator means there is no upstream limit. Add bounded route-level controls and tests only if no existing defense exists.
- Keep release blocked until the ChromaDB advisories and production UAT/SBOM/license/secret/deployment/restore gates are closed.


## P0 — public-route abuse controls and generation budgets verified (2026-10-26)
- Baseline verified at `96402915bc857035a859e068810f5d23f58ecca7` in push [40283105487](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40283105487) and PR [40283111955](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40283111955).
- Candidate hardens the existing signup/login/public-lead limiter with Redis atomic fixed windows in production, fails closed on Redis failure, adds workspace/IP budgets for LLM and video generation, requires authenticated workspace on expensive generation endpoints, caps keyword clustering at 500 values and public capture bodies at 32 KiB, and caps stateless tracking input at 8,192 characters.
- Regression tests and exact-SHA CI pending.


## Next P0 — outbound fetch and render abuse/SSRF boundaries
- Review all public outbound requests in research URL fetch, OpenAffiliate offer discovery, generic provider adapters and Pexels video download. Confirm safe DNS/IP resolution on every connection, redirects disabled or revalidated, byte caps, timeouts and rate budgets.
- Existing `backend/services/url_safety.py` and `backend/services/video_engine.py` already have controls; inspect their exact semantics and add only verified regression gaps. Note trusted proxy behaviour explicitly.
- Production remains blocked by ChromaDB advisories and provider/UAT/SBOM/license/secret/deployment/restore evidence.


## P0 — public outbound fetch, proxy and video asset safety (2026-10-26)
- Finding: URL validation blocked non-public DNS answers but the actual HTTP request resolved the hostname again, so the socket destination was not pinned. Campaign health probes had the same pattern; Pexels asset downloads lacked media Content-Type/declared-size checks and a source-duration cap.
- Candidate shared transport pins requests to a vetted public IP while preserving Host/SNI, disables redirects and proxy environment variables, applies total deadlines, and checks both declared and streamed response size. It is reused by HTML research fetches, configured OpenAffiliate requests, link-health probes and Pexels search/media downloads.
- Added limits: 2 MiB Pexels search JSON, 150 MiB media download, 180 seconds source/narration, 500 MiB rendered output, and 2 MiB / 12 seconds for default public HTML fetches.
- Competitor research now requires authentication and a selected workspace, applies the existing distributed IP/workspace quota, and limits each URL to 2,048 characters.
- Exact-SHA CI and new regression tests are pending. Staging must still validate ingress sanitization and Uvicorn trusted-proxy configuration; do not use wildcard forwarded-header trust.


## P0 — public outbound-fetch/video safety verified (2026-10-26)
- Source and tests verified on `f2d232f7ce5efaea2e3d1abca8a6ba7e47cf339c`; push [40288412469](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40288412469) and PR [40288420524](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40288420524) both passed.
- Implemented DNS-pinned public fetch with preserved Host/SNI, no redirects or env proxy use, request deadline and size/MIME limits; reused in research/affiliate API/health probes. Pexels B-roll is type-, size- and duration-bounded; generated output directory and size bounded. Competitor fetching is authenticated, workspace scoped and distributed-rate-limited.
- CI evidence: Python 301 passed/2 skipped; Postgres migration/concurrency, SQLite migration/drift, 9 AI/RAG imports, front-end, audit, skill parity and lockfile sync passed.
- Staging still needs to prove exact trusted-proxy config; four ChromaDB advisory exceptions and further release checks remain open.


## P0 — configured CMS endpoints and credentialed POST SSRF (2026-10-26)
- Audit finding: WordPress/Ghost `SITE_URL` was checked with DNS validation, then the site was resolved again by HTTPX when sending the authenticated POST. That is a check-then-connect DNS-rebinding gap on a global-credential integration.
- Candidate fix: extend the shared public-URL transport to allow only the fixed GET/HEAD/POST methods used by the application, preserve Host/SNI with the actual socket pinned to a validated public IP, disable redirects and environment proxies, and enforce a 2 MiB response cap on CMS JSON.
- Four tests cover WordPress/Ghost POST endpoints, selected JSON payloads/auth headers, redirects, and oversized response rejection. Status: pending exact-SHA CI.


## P0 — CMS configured-host DNS rebinding fix verified (2026-10-26)
- Exact SHA `13ec393d0897c4ba75ed83ba6bed8ce8690f7c06`: push [40290026088](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290026088) and PR [40290033400](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290033400) both passed.
- CMS endpoints no longer validate DNS and then use a second independent resolution when sending global WordPress/Ghost credentials. They use the shared pinned HTTP helper, preserve Host/SNI, disable redirects and environment proxies, apply total timeout and enforce a 2 MiB JSON response cap.
- Four CMS tests pass. The first CI failure was five test-double incompatibilities and was corrected without weakening production assertions. Final Python result: 305 passed, 2 skipped.
- Next: review remaining configurable direct HTTP calls and prove trusted proxy configuration in staging; keep Chroma advisories and release/UAT evidence gates open.


## P0 — remaining fixed-provider direct HTTP (2026-10-26)
- Source scan identified direct clients for Resend emails, Reddit OAuth and search, X trends, Pinterest/Reddit post submission, and Meta campaign pause. These are fixed provider endpoints, not arbitrary URL fetches, but credentials and external writes should use the same pinned IP/no-proxy/no-redirect transport.
- Candidate adds a JSON/form request helper with response cap and migrates callers; retains stable per-email Idempotency-Key, workspace tenant logic, publication dry-run and Meta automation execution gate. Three focused tests added. Pending exact-SHA full CI.


## P0 — final configurable affiliate adapter pinned transport (2026-10-26)
- Finding at base `868fbbc25d3d8dde5e5d772e1abeec9b3a4a16a4`: the broad backend/AI Python source scan found `backend/adapters/factory.py::ConfiguredJSONAdapter.fetch_offers` as the only remaining standalone provider HTTP client outside the shared `url_safety.py` transport. It performed DNS admission validation, then a separate unpinned client request.
- Candidate routes through `request_public_json`, which re-resolves the target for the actual request, pins its socket to the vetted public IP, disables environment proxies and redirect following, and caps JSON response size at 2 MiB. Existing adapter limit and configured item-path behavior are retained.
- Tests updated for loopback denial through the real helper and request contract/normalization via a fake helper. Verified at `aa3a0e175c09df3572f077b1c76d565ec2776207` by push [40301426819](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40301426819) and PR [40301436060](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40301436060); Python 321 passed, 2 skipped.
- Separately, the trusted proxy setting is implemented and syntax-tested, but actual proxy-header stripping and trusted-source behavior need proof from the real staging ingress.

## P0 — final configurable affiliate adapter transport verified (2026-10-26)
- Exact SHA `aa3a0e175c09df3572f077b1c76d565ec2776207`: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40301426819 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40301436060 both passed.
- Scan across 59 Python modules found the generic configured adapter as the final standalone outbound client outside `url_safety.py`. Replaced its unpinned HTTPX client with the pinned helper, bounded response size at 2 MiB, and preserved result parsing/limits.
- Real-loopback test confirms private literal destinations fail before connecting; mocked helper contract covers method, query, auth, response cap and normalization.
- Release gates still open: actual proxy behavior in staging, four ChromaDB advisory exceptions or reviewed vector-store replacement, live provider UAT, SBOM/license/secret scans, deployment smoke, backup/restore.


## P0 — Remove ChromaDB from optional AI/RAG (2026-10-26; candidate)
- Base `38a7b0ff6399d4702f8e8f798cdee81567a5c45d` passed the previous full push/PR matrix.
- Candidate uses `ai_memory/local_vector_store.py` (SQLite, normalized float32 embedding blobs, JSON metadata, stable IDs/upserts, collection and embedding-model checks, cosine similarity); ingestion/retrieval now use that storage; active AI requirements remove `chromadb` and `langchain-chroma`; CI removes four advisory ignore arguments.
- Five tests cover persistent reopen/search ranking, stable-ID update and delete, collection isolation, model identity mismatch and invalid vector rejection.
- Status: **CI verified** on exact SHA `3ba90e4cb2fcb72494c0fda71e1d535398229c22`; push [40304270245](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304270245) and PR [40304278972](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304278972) passed, including clean unignored AI audit and 10 AI/RAG imports. Existing Chroma files are not migrated automatically; rebuild with `python -m ai_memory.ingester` during rollout.


## P0 — AI profile verifier path correction (2026-10-26)
- First candidate `6a24ed5e73181bc190e6da391e6b4df040ebb49c` passed all jobs except AI import verification. The only reported error was `ModuleNotFoundError: No module named 'ai_memory'` from executing the verifier file path directly.
- Candidate correction adds the repository root to `sys.path` before import checks. Needs full push/PR CI re-verification.


## P0 — ChromaDB dependency removal CI evidence (2026-10-26)
- Exact SHA `3ba90e4cb2fcb72494c0fda71e1d535398229c22`, push [40304270245](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304270245) and PR [40304278972](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304278972) both passed.
- Removed `chromadb` and `langchain-chroma` from active AI requirements, replaced the retrieval index with local SQLite storage, removed the four dependency-audit ignores, and guarded against package/runtime reintroduction.
- The candidate's first AI-profile failure was a verifier import-path issue and was fixed without weakening the check. The new verifier reports 10 successful AI/RAG imports; unignored `pip-audit -r requirements-ai.txt` is green.
- Deployment still needs a preserved-index backup, re-ingestion with `python -m ai_memory.ingester`, count/source/retrieval validation in staging, and separate release UAT/security/backup evidence.


## P1 — durable workflow lease/recovery candidate (2026-10-26)
- Models/migration: `WorkflowRun.lease_owner`, `lease_expires_at`, `heartbeat_at`, `attempt_count`; Alembic migration `0010_durable_workflow_leases`.
- Runtime: process-unique worker ID, periodic heartbeat, expired lease claim with PostgreSQL row locking, recovery loop for queued/running/paused workflow checkpoints.
- Safety: only a read-only checkpoint is resumed after lease expiry; expired live S5 publication is marked `unknown` and requires manual provider reconciliation. No automatic duplicate external write is attempted.
- Tests: four SQLite recovery tests plus a PostgreSQL-only concurrent claim test added to the explicit integration job.
- Status: **CI verified** on exact SHA `03d967e97b1993b80f853cc2fec72cf9e6b5f392`: push [40306591424](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40306591424) and PR [40306596350](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40306596350) passed; PostgreSQL migration/drift and the concurrent lease claim test passed. Multi-replica HITL response routing remains unverified; response payload is not persisted and may need resubmission after interruption.


## P1 — durable workflow leases/restart recovery verified (2026-10-26)
- Exact SHA `03d967e97b1993b80f853cc2fec72cf9e6b5f392`; push [40306591424](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40306591424) and PR [40306596350](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40306596350) both passed.
- Four SQLite recovery/lease tests passed as part of Python (330 passed, 3 skipped). PostgreSQL job applied migration `0010_durable_workflow_leases`, ran drift checks through downgrade/re-upgrade, and passed 3 integration tests including concurrent workflow claim.
- Expired worker leases are claimed through PostgreSQL row locks. Read-only work resumes from the persisted current-step checkpoint. Potentially accepted live S5 publication is marked unknown and requires manual reconciliation.
- Remaining limitation: HITL response data is not persisted and must be re-submitted after a process death; multi-replica response routing, durable outbox/queue semantics, crash/fault load tests and production operational validation remain open.


## P1 — durable encrypted HITL response and multi-worker resume (2026-10-26)
- The previous recovery checkpoint acknowledged resume requests while the response existed only in process memory. This meant process loss or a different API replica could drop an acknowledged response.
- Candidate migration adds `paused_sessions.verification_response_encrypted`; Fernet encryption uses a key derived from the stable shared `APP_SESSION_SECRET`. The scheduler loop polls for resume requests for its own lease and wakes the local task. Recovery retains encrypted queued responses and consumes them before emitting a new HITL alert.
- Regression tests cover a non-owner API instance submitting the response and the lease owner waking, as well as process restart, lease claim and response consumption. Verified on exact SHA `92af1c5d06544e4870c8c550176fd19a25084d06`; push [40333566763](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40333566763) and PR [40333573375](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40333573375) both passed.


## HITL response encryption dependency audit correction (2026-10-26)
- The first candidate CI reported seven cryptography 46.0.7 advisories; that range is rejected and not waived.
- Change `requirements.txt` to `cryptography>=50,<51` and rerun the full exact-SHA CI. Release status remains pending until `pip-audit -r requirements-dev.txt` and all other required jobs pass.


## P1 — durable encrypted HITL response verified (2026-10-26)
- Exact SHA `92af1c5d06544e4870c8c550176fd19a25084d06`; push [40333566763](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40333566763) and PR [40333573375](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40333573375) both passed all required jobs.
- The migration-backed `PausedSession.verification_response_encrypted` uses Fernet derived from stable `APP_SESSION_SECRET`; response data never enters plain workflow state or audit detail.
- Two end-to-end tests cover an API request arriving at a non-owner instance and waking the lease owner, plus a response being consumed by a fresh worker after restart/lease claim. SQLite and PostgreSQL migration/drift/concurrency, Python, AI/RAG, frontend, dependency audit, repository guard and lockfile sync passed.
- An initial audit failure found cryptography 46.0.7 had advisories; requirement was tightened to `cryptography>=50,<51` and the follow-up audit passed. No advisory exception was used.
- Production remains pending remaining provider/UAT, comprehensive security testing, SBOM/license/secret scan, deployment and backup/restore evidence.


## P0 — outbound transport boundary guard (2026-10-26; candidate)
- The current approved transport pins each actual outbound connection to a verified public IP, maintains TLS hostname validation/SNI, disables redirects and ambient proxies, and bounds responses.
- Added `scripts/verify_outbound_transport_boundary.py`, a standard-library AST check for raw provider HTTP client creation outside `backend/services/url_safety.py`; CI runs it in the fast repository guard.
- Added regression tests for aliased HTTPX/requests/aiohttp/urllib/urllib3 clients, the allowed transport module, helper-based requests and syntax errors.
- Status: pending exact-SHA push/PR CI. This does not close the live staging proxy trust gate.


## P0 — outbound transport boundary guard verified (2026-10-26)
- Exact SHA `1725afcfc17acc8b890d8ccbc4bf04114638458d`; push [40338107674](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40338107674) and PR [40338115729](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40338115729) both green.
- Six regression tests and fast CI guard pass. Runtime code in `backend/` and `ai_memory/` may not create raw HTTP clients outside the DNS-pinned approved transport. Transport SNI/pinning/redirect/proxy invariants are checked.
- Python 338 passed, 3 skipped, 1 warning; AI/RAG profile verified 10 imports; SQLite/PostgreSQL migration/concurrency, frontend, security audit, skill parity and lockfile sync passed.
- Still open: real staging ingress test for spoofed `Forwarded`/`X-Forwarded-For`; authorized provider UAT, SBOM/license/secret scans, deployment smoke, backup/restore, monitoring/SLO evidence.

## P0 — Uvicorn trusted-proxy middleware compatibility (2026-10-26; candidate)
- Raised uvicorn[standard] lower bound from 0.30 to 0.31 because the app validates CIDR trust configuration and needs a Uvicorn version with IP-network parsing support.
- Added tests/test_trusted_proxy_middleware.py using the real Uvicorn middleware for untrusted spoof attempts, trusted CIDR forwarding and multi-hop chains.
- Pending exact-SHA full push and PR CI. A live staging request through the real reverse proxy remains mandatory to prove it strips/replaces incoming forwarding headers.


## P0 — automated SBOM, license-policy and secret scanning (2026-10-26) — verified
- Exact SHA `f254ec0d998fa6541fba8415d0ed059fda7e4a23`: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40348612494 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40348624953 both succeeded.
- CI produces reproducible CycloneDX SBOM artifacts for Python core/test, optional AI/RAG and frontend; emits license inventory JSON keyed to `GITHUB_SHA`; runs full-history Gitleaks with redaction; and uploads report artifacts with candidate SHA in their names.
- Verification: Python **361 passed, 3 skipped, 1 existing warning**; all 8 push jobs and all 7 required PR jobs passed. The secret scan reported zero findings after the one exact-fingerprint ordinary-text false positive was narrowly ignored under regression test.
- Python core/test (76 packages) and AI/RAG (90 packages) license reports have zero findings; frontend (109 packages) has two exact, expiring LGPL items marked release blockers, with `release_approved=false`. Legal review or replacement is mandatory before production distribution.
- Remaining independent release gates: actual staging proxy spoof/identity behavior, authorized provider live UAT, deploy smoke, monitoring/SLO, production data/RAG re-ingestion validation and backup/restore.


## P0 — hosted LLM SDK bypass of outbound transport (2026-10-26)
- Finding on `7a2626094c370ba12b8f10249e44dd02abd5d1e0`: raw HTTP call sites used the pinned transport, but `ChatOpenAI` constructed the OpenAI SDK-managed HTTP client independently.
- Candidate adds an injected DNS-pinned `http_async_client`, request-time HTTPS/public-address validation, connection-IP pinning, Host/SNI preservation, no redirects and `trust_env=False`; SDK auto-retries are disabled to reduce ambiguous duplicate model spend. Static guard now enforces the injected client for ChatOpenAI/OpenAI SDK constructors.
- New tests cover transport behavior and static policy. **Pending** exact-SHA full push/PR CI. Staging deployment, actual proxy ingress and authorized provider UAT must still be evidenced separately.
