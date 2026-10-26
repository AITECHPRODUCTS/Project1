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


## P0 — global offer registry sync — candidate
- Source-derived gap: `/api/offers/sync` mutates shared catalog rows and performs provider calls while only relying on router-level authentication. Offer is a global Base model, not a tenant-owned table.
- Candidate requires Platform Super Admin and an active audit workspace; adds success/failure AuditLog records and tests denial before provider invocation plus success/failure audit paths.
- Exact-SHA CI pending.
