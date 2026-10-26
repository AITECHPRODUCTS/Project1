# Continuous-build thumb rules

Canonical project: https://github.com/AITECHPRODUCTS/Project1
Single implementation branch: build/omni-affiliate-os-production

These additive rules apply to every future Project1 build session.

1. Review prior chats and all available conversation/Library attachments relevant to the master prompt before coding. Read the source register and requirements contract. Note missing files explicitly and never claim to have inspected an unavailable ZIP.
2. Continue without another prompt. Do not ask the user to reissue the master command, select the next ordinary feature, or tell them to wait. Choose the highest-priority unblocked item from the traceability backlog.
3. Use only AITECHPRODUCTS/Project1 and build/omni-affiliate-os-production for code, tests, docs, repairs and workflow fixes. Do not create feature/fix/test branches, rewrite history, reset shared state or alter other repositories.
4. Implement small vertical slices with backend/schema/API/UI work where applicable, regression tests and traceability. Prefer additive changes and preserve existing endpoints, feature behavior and data.
5. After each push, inspect hosted Python tests and migration gate, AI/RAG verification, and frontend typecheck/production build for the exact commit SHA. Read failing logs, fix on the same branch and rerun. Queued, cancelled or in-progress is not a pass.
6. Report status with evidence. Distinguish implemented, partial, not implemented and blocked. CI success alone is not production certification; PostgreSQL migration tests, security review, provider authorization, browser UAT and deployment health remain separate gates.
7. Never commit credentials, customer data or private media. External publishing, paid spend, payouts, audience uploads and account mutations remain disabled until provider authorization, consent, idempotency, approval and kill-switch requirements are implemented and verified.
8. The 2026-10-25 upload affiliate-skills-main(1).zip was inspected and is an MIT-licensed source skill pack (53 definitions, registry/evals/docs/CLI). The content-decay-detector, content-moat-calculator, traffic-analyzer and multi-program-manager specs are used as source contracts; their data-provider gaps must remain explicit. This ZIP is not a deployable FastAPI/Next.js application. Also use the prior Library app-source snapshot OmniAffiliateOS_build.zip as reference only. For any additional live-app ZIP, inspect archive safety, license/provenance, secrets, dependencies, architecture, migrations, tests and workflows; compare with the current backlog and port only compatible, validated code. Never blindly replace Project1.
9. Update implementation status, requirements traceability, skill parity and blocker evidence after each slice. State each completion-stat denominator and never treat the 53-skill inventory as overall product completion.
10. The 25 October 2026 ZIP-reminder checkpoint has been met: a source package arrived. Continue implementation from all available materials and do not block on another prompt or reminder.

11. After each vertical slice is implemented and its hosted CI is checked, immediately continue to the next highest-priority unblocked requirement in the same session. Never stop to request an ordinary next command. At the start of each session, re-review prior chat requirements and relevant Library attachments, maintain a clear blocked/unblocked list, and keep progressing on independent work while external provider approvals or credentials remain pending.

12. Treat every instruction in the user's messages and every relevant attached source as additive, binding requirements. Review the actual text—not just filenames or a partial summary—preserve its terminology and constraints, map requirements to acceptance criteria, and update this rules file plus traceability/status records when the user adds a rule. Do not silently discard any instruction, and do not ask the user to repeat the master command or choose the next ordinary task.
13. Use the Full Blueprint v3 build sequence as the priority order: recover exact repository/branch/HEAD and CI evidence first; then complete P0 engineering, dependency/lockfile, security/tenancy and traceability gates before low-priority feature breadth. A source skill document or heuristic service is not end-to-end capability evidence; provider, implementation, testing and production readiness have separate statuses.


14. Current verified checkpoint: at HEAD `e6e6eb4e552b4887da252db0df172dd25ee79561`, push run 40213802242 and PR run 40213808545 passed, including npm ci, frontend typecheck/build, Python, PostgreSQL, AI/RAG and repo-guard; the push lockfile-sync job passed. The frontend lockfile is committed. The new security-audit job is pending exact-SHA evidence until its next hosted run completes; do not mark security scanning complete from configuration alone.


15. Dependency scanning is a fix gate, not a report-only decoration. When pip-audit/npm audit report an available fixed version, adjust compatible dependency ranges, preserve app constraints, rerun the full CI matrix, and record remaining findings with evidence. Never suppress or label the scan green before exact-SHA results prove it.


16. When upgrading an audited dependency, update conflicting plugin/test-runner constraints based on upstream compatibility evidence, then prove dependency resolution and run the entire regression matrix. A successful audit tool install alone is not a pass.


17. A dependency advisory with no upstream fix must not be silently suppressed or described as clean. Any temporary exception requires exact advisory IDs, source links, an explicit exploitability boundary, enforceable compensating controls, a regression test, an explicit CI warning, and a release blocker until the exception is removed or formally re-evaluated.


18. Resume checkpoint dated 2026-10-26: the current next action is to repair the verified npm audit failure on the existing `build/omni-affiliate-os-production` branch; do not restart/rebase/branch-switch. Pre-repair SHA `565c76bd7d6931721ce66cb0a84fc25129997c52` has passing Python, PostgreSQL, AI/RAG, skill-parity and frontend build jobs but failing `npm audit` (five advisories reported). Preserve all passing areas, regenerate the lockfile through the guarded one-shot workflow, inspect logs, and rerun the full matrix before advancing to the next P0 backlog item.


19. 2026-10-26 lockfile checkpoint: the temporary `dependency-remediation` workflow job passed `npm audit`, `npm ci`, frontend typecheck and production build, then committed the patched lockfile as `0180f2f0fd84445ff76131d4ca04389676043b8a`. That bot commit did not give a normal full-matrix push run; do not count it as a full CI pass. The temporary lock-refresh job has been removed. The next regular commit must trigger the full matrix on the committed Next.js 16.4.3 lockfile; inspect and fix failures before selecting another P0 task.


20. 2026-10-26 verified checkpoint: full push run [40264037056](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264037056) and PR run [40264040473](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264040473) passed on exact SHA `668b33670ea11e30f97ccc3c6e50180124609207`. The frontend npm audit and standard/AI-RAG audits passed, with only the four precisely documented Chroma advisories conditionally excepted by the embedded-only guard. Preserve this as a verified checkpoint. Next: move GitHub Actions dependencies off retired Node 20 releases to current Node 24-capable action majors, then rerun the full matrix; production is still blocked by the Chroma exception and provider/UAT/deploy/restore gates.


21. P0 tenant-auth regression tests: signed sessions with deactivated workspace membership are rejected and cleared (403); static bearer API tokens are denied for workspace-scoped access (403); workspace members are denied workspace-admin permissions. Verified on exact SHA `e715878c76fb6f1876c2ff1769653fa72ad51396` by successful push run [40264570099](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264570099). This does not substitute for broad route-by-route authorization, WebSocket/export/background-job tests, or production release gates.


22. P0 WebSocket tenant isolation: workflow/HITL events must never be globally broadcast. Workflow events require workspace scope; EventHub delivers only to sockets for the same verified workspace and drops unscoped/legacy payloads. WebSocket connection setup revalidates active membership instead of trusting cached session role. Tests in `tests/test_websocket_tenant_isolation.py` passed on exact SHA `65a5a884acf0195a2720cb6de76a5279fd4e5dde`; push [40265255592](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265255592) and PR [40265259440](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265259440) both succeeded. Next audit workflow run status/pause/resume/retry ownership checks.


23. P0 workflow lifecycle ownership: workflow starts require an authorized workspace; workflow status/resume must use the owner workspace; background pause recovery must pass the persisted workspace explicitly; dashboard totals must be workspace-scoped. Verified on exact SHA 16eee55a6935e9afa1d5f2b020c867713754aa67 by push [40265845238](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265845238) and PR [40265848400](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265848400), both successful. Next: gate global knowledge-index mutation to platform operations and avoid leaking host paths in ordinary status responses.


24. P0 shared knowledge-index mutation: the shared RAG ingestion endpoint is platform-admin-only; non-platform workspace owners receive 403, the UI hides the action unless `isPlatformAdmin` is true, and knowledge status does not disclose an absolute filesystem path. Verified on exact SHA `743e404e63b7c3a54423a18b1cf17af1338c5abf` by successful push [40266330644](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40266330644) and PR [40266336192](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40266336192). Keep the documented Chroma advisory exception as a production blocker; next audit resource-budget and learning aggregates for tenant scope.


25. P0 resource-budget / learning tenant boundary: `ResourceUsage` and `PerformanceMemory` are tenant-scoped. Resource-budget reserve/finalize/status and performance-learning helpers fail closed without an authorized workspace, reject a mismatched requested workspace, and scope database reads/writes. API routes and scheduled jobs pass tenant identity explicitly. Verified on exact SHA `3322babb2865019e6a94bc5dc946cc700cd301f7` by successful push [40267076940](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40267076940) and PR [40267081364](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40267081364).


26. P0 scheduled-worker tenant scoping: campaign-health, email-delivery and payout-threshold jobs must enumerate workspace IDs, then query and mutate only within each concrete `workspace_scope`. Email delivery must pass the explicit workspace ID to `send_due_emails`; do not run tenant-scoped reads from the scheduler's default unscoped context. Verified on exact SHA `45e4243faf3c3f48756da8dd45157c3654e67a43` by successful push [40267402032](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40267402032) and PR [40267407457](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40267407457); Python, PostgreSQL, AI/RAG, frontend, security audit, repository guard and lockfile sync all passed.


27. P0 campaign/conversion handler workspace binding: campaign list/create/health and API-submitted conversions must check `user.workspace_id`, run under an explicit `workspace_scope`, and assign `workspace_id` consistently to tenant rows and conversion ledger entries. Duplicate checks must include workspace ID so two tenants can use the same provider event ID without cross-tenant disclosure. Verified on exact SHA 4becae03e155fedc361e5b9fcdfc9fde66602f75 by passing push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268073324 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268078547.


28. The initial campaign/conversion candidate CI failed one legacy fixture: `test_conversion_create_api_records_decimal_but_unverified_evidence` expected development fallback authentication with no workspace, but the handler intentionally denies missing workspace. The test fixture is corrected to provide a selected authorized workspace and to assert both rows are tenant-bound. The rerun of the full matrix passed at 4becae03e155fedc361e5b9fcdfc9fde66602f75; push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268073324 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268078547 are both green.

29. P0 campaign/conversion tenant binding is verified at `4becae03e155fedc361e5b9fcdfc9fde66602f75`; push [40268073324](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268073324) and PR [40268078547](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268078547) both passed. The Python suite now proves no-workspace denial, cross-tenant campaign hiding/health denial, workspace-specific duplicate conversion identity, and correct workspace assignment to both the Conversion row and append-only ledger entry. Next audit remaining ContentAsset, Lead, ScheduledEmail, and public-capture access paths.


30. P0 blog/lead/email workspace boundary verified on `929035b6429f4a1fa9a0c9c31cbc35834ab72dc9`: push [40269971909](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40269971909) and PR [40269976725](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40269976725) both passed. `/content/blog` requires an authenticated workspace and persists its ContentAsset under that tenant. Private `/leads/capture` requires authentication/workspace; public signup requires the signed purpose-bound `lead_capture` token. Lead/email lookups and sequence idempotency are workspace-scoped, and `send_due_emails` fails closed with no workspace. Six regression tests passed. Next audit: the social-publish endpoint, landing-page token issuance, and remaining external-impact provider operations.



32. P0 external publishing/landing-token boundary is verified on `6f3994096e502911b23fb54e8cb94c3f2181a16d`; push [40270795625](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270795625) and PR [40270800499](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270800499) both passed. Social/CMS writes require Platform Super Admin + selected workspace; live actions require `confirm_live_publish=true`; workspace-scoped audit records capture outcome; landing capture token issuance is explicitly bound to the authenticated workspace. Six regression tests passed.


33. Next P0: inspect workflow runner step handlers and any remaining provider-integration endpoints for external mutations. Confirm human approval, idempotency, durable audit events, explicit provider scopes and dry-run behavior. The four documented ChromaDB advisory exceptions and remaining release evidence remain blockers.

34. P0 workflow-side-effect boundary verified at `64a2d30af5dddb79150428936993ef1811b4419f` (push [40275131255](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275131255), PR [40275135461](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275135461), both success; Python 255 passed/2 skipped; AI/RAG 9 imports passed). S5 must not bypass the social publishing authorization. Live workflow publish requires Platform Super Admin identity from the authenticated request, a top-level explicit `confirm_live_publish=true`, and selected workspace; do not trust client-provided authorization metadata. Record per-workspace attempt and result/error audit metadata without storing post bodies. S6 conversion imports must explicitly scope duplicate lookup and new Conversion rows to `metadata.workspace_id`. Five regression tests passed in the full exact-SHA matrix.
35. Workflow boundary CI correction history: first candidate `9dcc5f0c842eddaeca86c40ed13d2997c1eddebe` failed 2 tests (push run 40274907786; 253 passed, 2 skipped). The follow-up stamped workspace into server-controlled start metadata and corrected the direct-handler fixture. The resulting SHA `64a2d30af5dddb79150428936993ef1811b4419f` passed push [40275131255](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275131255) and PR [40275135461](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275135461). Keep the failed run as regression history rather than hiding it.
36. P0 scheduled-email side-effect idempotency is verified at `fedd1f74dbaa33e210b0587c774bc2ad63d92b8d`: push [40276085004](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40276085004) and PR [40276090006](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40276090006) both passed; Python 258 passed/2 skipped and AI/RAG 9 imports passed. Workers atomically claim due rows per workspace, use a stable per-message `Idempotency-Key`, retry stale claims only within the provider's 24-hour idempotency window, and quarantine older ambiguous sends as `delivery_unknown`. Migration, drift and concurrency tests passed. Resend's documented idempotency behavior: https://resend.com/changelog/idempotency-keys.
37. Email worker correction history: the first candidate `7c1b6bab08924a077aa790cbf39130e5eece0aad` failed the stable unsubscribe URL assertion (257 passed, 2 skipped; push [40275990654](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275990654), PR [40275995997](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275995997)). The regex was corrected at `fedd1f74dbaa33e210b0587c774bc2ad63d92b8d`; both push and PR runs then passed.



38. P0 workflow retry safety is verified at `3dc01b9b954bf0ec392aafed522c4ec968faffa9`: push [40277040070](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40277040070) and PR [40277047842](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40277047842) both passed; Python 260 passed/2 skipped; AI/RAG 9 imports passed. S5 is marked side-effecting. A timeout/connection failure records a workspace-scoped `workflow.side_effect_outcome_unknown` event and fails closed without automatic retry; read-only transient failures preserve the configured retries. Two regression tests passed.

39. Next P0: durable request-level idempotency for manually retried live social/CMS publishing requests. Workflow retry suppression protects the runner's automatic retry, but does not yet prevent duplicate external writes when an operator/client repeats a live request.

40. P0 provider-write idempotency is verified at `1cc839bbf80d1a66e35b9e36f244b4fa13cb68af`; push [40278503530](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40278503530) and PR [40278508177](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40278508177) both passed. Four regression tests passed (Python 264 passed/2 skipped); migration 0009 adds the durable tenant-scoped `ExternalAction` claim/replay/unknown-outcome registry for direct social/CMS routes. Next P0: apply the same durable registry to workflow S5 distribution, which currently calls the provider adapter directly.


41. CI correction follow-up for provider-write idempotency: base `b3495a58202f944621f43063efbe9d293323ee24` correctly returned 428 because the legacy live-social confirmation test omitted `Idempotency-Key` (PR [40278241892](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40278241892): 1 failed, 263 passed, 2 skipped). Fixture now supplies a valid key; rerun full push/PR CI before marking P0 complete.


42. P0 workflow S5 ExternalAction registry integration is verified at `e7ca02df933c3028489e8c3ba1abbfba3d82ae90`; push [40279412060](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279412060) and PR [40279416167](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279416167) both passed. Python: 267 passed/2 skipped; PostgreSQL, SQLite drift, AI/RAG (9 imports), frontend, security audit, repo guard, and push lockfile passed. S5 now shares the durable action registry and derives stable per-item keys from a required workflow `Idempotency-Key`; completed results replay and unknown outcomes block same/alternate-key retry. Next P0 audit: remaining provider adapters and externally impactful workflow/worker paths.


43. P0 global offer sync is verified at `498c0b595a8dd158b06eae2924f87d3897a8525b`; push [40279967742](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279967742) and PR [40279972611](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279972611) both passed. Python 271 passed/2 skipped, PostgreSQL/SQLite migration gates, AI/RAG imports, frontend build, dependency audit, repo guard, and push lockfile passed. `/api/offers/sync` requires Platform Super Admin + active audit workspace and records workspace-scoped success/failure events for the global shared `Offer` registry. Four route tests passed.


44. Next P0: continue the remaining integrations/configuration route audit, especially global provider registry operations and role/audit/rate-limit coverage. Keep production blocked until four documented ChromaDB advisories and release/UAT/SBOM/license/secret/deployment/backup evidence are resolved.


45. P0 OpenAffiliate URL safety is verified at `49043acd6e71841c7d365a97a9d8ca31168cc8da`; push [40280504806](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40280504806) and PR [40280508646](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40280508646) both passed. Python 273 passed/2 skipped; SQLite/PostgreSQL migration gates, AI/RAG imports, frontend, security audit, repo guard, and push lockfile passed. `_get` now validates the composed URL before HTTP client creation on cache misses, rejects private/loopback destinations, and preserves disabled redirects. Two URL-safety regressions passed.


47. P0 global IMAP import is verified on `0ea1735648ce408fb831abc51179544facd3ed69`; push [40281363532](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40281363532) and PR [40281370173](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40281370173) both passed. Python 277 passed/2 skipped; all required CI jobs passed. The endpoint requires Platform Super Admin plus selected workspace and audits counts/error type without storing mailbox content. Four regression tests passed.


48. Next P0: inspect remaining global provider/configuration and integration routes for role boundaries, tenant ownership, audit trails, rate limits and safe network access. Do not relax shared-resource permissions to make tests pass; update the tests to express the intended authorization contract.


49. P0 global provider readiness/capability confidentiality is verified on `a0bb0ff23f86b29e7e4a9072d2109e77d0328d40`; push [40282793722](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40282793722) and PR [40282799345](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40282799345) passed. Python 281 passed/2 skipped, full required CI green. Both endpoints require Platform Super Admin plus selected workspace; four regressions cover authentication, workspace role, absent workspace, and raw credential redaction.


50. Next P0: examine abuse controls on public endpoints that perform generation or create tracking/lead records. Identify whether a trusted proxy/API layer already rate-limits them; avoid double-limiting; add route-level request limits and regression tests only for verified gaps.


51. P0 public-route abuse controls/generation authorization is verified on `e3fb2fd8e159bae71f84fdd1bb3c4df50bc9d96a`; push [40283974722](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40283974722) and PR [40283978789](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40283978789) passed. Python 289 passed/2 skipped; all required jobs green. Production quotas are Redis-backed atomic fixed windows and fail closed with 503 when Redis is unavailable. Expensive generation/video routes require selected workspace and per-IP/workspace limits; public lead body, keyword list and tracking string lengths are capped. Eight regression tests passed.


52. Next P0: review every public outbound-fetch/render route and its URL safety boundaries. Verify DNS rebinding/redirect handling, private/reserved-address rejection, byte/time/response caps, Pexels download caps, and whether trusted-proxy assumptions are documented and configured. Do not duplicate existing SSRF protections; identify and test gaps only.


53. P0 public outbound-fetch/video hardening candidate on base `bba6b736b43a525f41723fef84dd72cb2a77e6f2`: existing code validates DNS but re-resolves during HTTP fetch; pin the actual connection to a vetted public IP, preserve original Host/SNI, disable ambient proxy/redirect behavior, enforce total time and body caps, cap Pexels source/output duration/size, and authenticate/rate-limit competitor fetches. Verified on exact SHA `f2d232f7ce5efaea2e3d1abca8a6ba7e47cf339c`: push [40288412469](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40288412469) and PR [40288420524](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40288420524) passed. Trusted proxy must be explicitly configured for exact proxy IPs/CIDRs; never trust arbitrary client `X-Forwarded-For` or use wildcard forwarded-header trust.


54. P0 public outbound-fetch/video safety is verified on `f2d232f7ce5efaea2e3d1abca8a6ba7e47cf339c`; push [40288412469](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40288412469) and PR [40288420524](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40288420524) both passed. Python 301/2 skipped, PostgreSQL migration/concurrency, 9 AI/RAG imports, frontend build, dependency audit, 53-skill parity and lockfile sync all green. Trusted proxy ingress still needs staging proof; four Chroma advisories and release/UAT/SBOM/backup gates remain unresolved. Next: validate actual proxy trust and verify any remaining direct HTTP integrations use the pinned transport where caller-supplied URLs enter.


55. P0 CMS provider requests: WordPress/Ghost site URLs are operator-configured but carry global write credentials. Do not validate DNS then perform a second unpinned resolution. Use the shared pinned-IP transport, preserve Host/SNI, disable redirects/proxy env, cap response bodies, and retain the `CMS_PUBLISH_EXECUTE` gate. Verified on exact SHA `13ec393d0897c4ba75ed83ba6bed8ce8690f7c06`: push [40290026088](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290026088) and PR [40290033400](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290033400) both passed.

56. CMS transport candidate `186d149be9f99707095a1515db14ce26211db0eb` initial CI failed 5 tests (4 CMS fake-response class-scope `NameError`, 1 fake client's `build_request()` did not accept `json`). Fix is in the test fixtures, not a relaxation of the production transport; rerun full push+PR CI before marking #55 complete.


57. P0 CMS credentialed POST transport is verified on `13ec393d0897c4ba75ed83ba6bed8ce8690f7c06`; push [40290026088](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290026088) and PR [40290033400](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290033400) both green. Python 305/2 skipped, PostgreSQL migration/concurrency, AI/RAG imports, frontend, dependency audits, 53-skill parity and push lockfile-sync all passed. Next: audit remaining direct HTTP integrations and validate actual trusted-proxy ingress in staging; Chroma advisories and other release gates remain open.


58. P0 fixed credentialed provider HTTP is verified on `15edaf7ea7103150295098754ae8a64166120e3d`; push [40292024351](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40292024351), PR [40292030798](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40292030798), and later clean HEAD runs passed. Resend, Reddit/X research, Pinterest/Reddit publishing and Meta pause use `request_public_json`; stable email idempotency/claim, `PUBLISHING_DRY_RUN`, `AD_AUTOMATION_EXECUTE` and Meta ID validation are preserved.


59. P0 final configured affiliate adapter transport is verified on exact SHA `aa3a0e175c09df3572f077b1c76d565ec2776207`; push [40301426819](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40301426819) and PR [40301436060](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40301436060) both passed. A 59-module source scan found the generic adapter's validate-then-connect client as the last bypass; it now uses the pinned helper with a 2 MiB cap, and loopback + request-contract tests passed in Python (321 passed, 2 skipped). Staging trusted-proxy verification remains a separate external release gate.


60. P0 trusted-proxy runtime validation: `FORWARDED_ALLOW_IPS` accepts exact IPs/CIDRs and rejects wildcard/default-route/hostname values; Compose defaults to loopback-only. Actual reverse-proxy header stripping/replacement, trusted-peer behavior and rate-limit client-IP identity are **not** proven by CI. Run the documented spoofed-`X-Forwarded-For` staging checks and record deployed SHA/image digest, proxy source addresses and sanitized results before marking complete. Do not claim staging without a real endpoint.


61. P0 Chroma advisory elimination — candidate: replace ChromaDB/`langchain-chroma` with a SQLite-persisted local vector index, preserve RAG APIs, remove all audit ignores, guard active runtime/dependency files against reintroduction, and test persistence/upsert/cosine ranking/model compatibility/collection isolation. Base `38a7b0ff6399d4702f8e8f798cdee81567a5c45d` passed its previous matrix; verified on exact SHA `3ba90e4cb2fcb72494c0fda71e1d535398229c22`: push [40304270245](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304270245) and PR [40304278972](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304278972) passed all required jobs, including the clean unignored AI audit and 10 AI/RAG imports. Old index data needs explicit re-ingestion; don't delete the prior index as part of the code upgrade.


62. The first Chroma-removal candidate `6a24ed5e73181bc190e6da391e6b4df040ebb49c` failed only because CI invokes `python scripts/verify_ai_profile.py` and that script lacked the repository root on `sys.path` (`ModuleNotFoundError: ai_memory`). The core tests, PostgreSQL, frontend, repo guard, clean audit and lockfile sync passed; the verifier path was fixed in commit `3ba90e4cb2fcb72494c0fda71e1d535398229c22`; both push [40304270245](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304270245) and PR [40304278972](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304278972) are green. The Chroma package replacement is verified in CI; on-disk index re-ingestion and production rollout verification remain required.


63. P0 Chroma dependency removal verified on `3ba90e4cb2fcb72494c0fda71e1d535398229c22`: push [40304270245](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304270245) and PR [40304278972](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304278972) passed. The local SQLite vector index, no-Chroma static guard, unignored AI dependency audit and 10-import AI/RAG check are green. Do not delete old Chroma index files; back up and re-ingest from the approved sources, then verify retrieval in staging before switching production.


64. P1 durable workflow queue/recovery candidate: keep workflow checkpoints in PostgreSQL and add lease owner, lease expiry, heartbeat, attempt counter, PostgreSQL `FOR UPDATE SKIP LOCKED` claims, periodic restart recovery for queued/running work, and paused-session recovery. Resume read-only stages from the persisted checkpoint. An expired live-publication stage must be stopped for manual reconciliation rather than automatically replayed. Verified exact SHA `03d967e97b1993b80f853cc2fec72cf9e6b5f392`: push [40306591424](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40306591424) and PR [40306596350](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40306596350) passed. Python reported 330 passed/3 skipped; SQLite and PostgreSQL migration/drift passed; the dedicated PostgreSQL concurrent lease claim test passed. HITL response payload persistence/redistributed resume remains a separate limitation until explicitly solved.


65. Durable workflow lease/recovery verified at `03d967e97b1993b80f853cc2fec72cf9e6b5f392`. No automatic replay of a potentially accepted live external write; a live S5 stage with an expired lease is marked unknown and sent to manual reconciliation. Keep the limitation visible: HITL response payloads are not persisted, multi-replica resume routing is not yet verified, and this is not a replacement for the remaining durable queue/outbox and release-readiness work.


66. P1 durable HITL response: persist human verification responses encrypted at rest (Fernet, key derived from shared stable `APP_SESSION_SECRET`), never in workflow JSON or audit details. Any API replica can durably submit; the lease owner polls and wakes its in-process task; a new owner consumes an encrypted pending response during recovery. Clear only after the retried stage checkpoint is persisted. Decryption/configuration mismatch fails closed with a workspace audit event. Verified exact SHA `92af1c5d06544e4870c8c550176fd19a25084d06`: push [40333566763](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40333566763) and PR [40333573375](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40333573375) both passed. Python, SQLite/PostgreSQL migrations and concurrency, AI/RAG, frontend, repo guard, dependency audit and lockfile sync all passed.


67. HITL encryption dependency security correction: the first hosted audit found seven vulnerabilities in cryptography 46.0.7 from the range `>=44,<47`. The requirement is tightened to `>=50,<51` using the audit's fixed-version data. Do not waive this scan; require a new full push + PR matrix and confirm the resolved installed version plus a clean `pip-audit`.


68. Encrypted HITL persistence verified on `92af1c5d06544e4870c8c550176fd19a25084d06`: push [40333566763](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40333566763) and PR [40333573375](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40333573375) both green. `cryptography>=50,<51` passes the current core/test dependency audit. Active cross-worker delivery, durable response across worker restart, and clearing encrypted response only after stage checkpoint are covered by passing regressions. Keep stable shared `APP_SESSION_SECRET` across replicas. This does not certify the entire product for production; remaining deployment/provider/UAT and documented release gates still apply.


69. P0 outbound transport boundary guard: all runtime provider HTTP must use `backend/services/url_safety.py`; new raw HTTP clients in `backend/` or `ai_memory/` are rejected by `scripts/verify_outbound_transport_boundary.py` and its tests. CI runs the guard before package installation. Candidate status remains pending exact-SHA push/PR CI. Live trusted-proxy ingress spoofing verification is still an external staging gate.


69. P0 outbound transport guard verified at `1725afcfc17acc8b890d8ccbc4bf04114638458d`; push [40338107674](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40338107674) and PR [40338115729](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40338115729) both passed all required jobs. Python 338 passed/3 skipped/1 warning; AI/RAG 10 imports passed; PostgreSQL and frontend gates passed. The AST guard blocks raw provider HTTP clients outside `backend/services/url_safety.py`. Actual staging-proxy spoofing/client-IP verification remains open and cannot be inferred from CI.

70. P0 Uvicorn trusted-proxy compatibility verified on exact SHA `da36211099ba27732510706189a267e9860b090e`: push [40341045895](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40341045895) and PR [40341061656](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40341061656) both passed. The actual Uvicorn ProxyHeadersMiddleware regression tests cover non-allowlisted spoof rejection, trusted CIDR parsing and trusted-chain selection; runtime requires uvicorn[standard]>=0.31,<1.0. Real deployed proxy header stripping/replacement remains an external staging gate and must not be counted complete from CI.


71. P0 release-evidence automation: add CI SBOM generation, license-policy reporting/enforcement, and secret scanning with exact-SHA artifacts and no secret-value output. Keep external trusted-proxy ingress tests, authorized provider UAT, deployment smoke, monitoring/SLO and backup/restore evidence as separate gates.


72. P0 SBOM/license/secret scan automation: workflow candidate adds Python core/test and AI/RAG CycloneDX SBOMs, frontend CycloneDX SBOM, package license reports and strict blocked/unknown-license enforcement, plus full-history Gitleaks using pinned image digest and redacted findings. All artifacts are keyed to `github.sha`. Do not mark verified until exact-SHA push and PR workflows pass and the artifact reports are checked. The actual staging ingress, provider UAT, deploy, monitoring and backup/restore remain separate open release gates.


73. 2026-10-26 supply-chain first-run finding correction: exact-SHA candidate `4331d2c5f848d5580dc93990191fc01a7c80b2cb` failed Gitleaks on ordinary phrase “conversational tone” at the preserved upstream skill file line 68 and failed the license gate on exactly two `@img/sharp-libvips-*` 1.3.4 components under LGPL-3.0-or-later. Ignore only the exact historical fingerprint `513bbaacd9441024ef191472c95dd80289c6ea31:knowledge/affiliate-skills/upstream/skills/content/viral-post-writer/SKILL.md:linkedin-client-id:68`. License exceptions are exact package + version + license, expire 2026-11-02, are emitted as `release_approved=false`, and do not grant legal or production approval. Tests and new push/PR CI pending.


74. Production release remains blocked until the two LGPL exception items are legally reviewed or replaced and actual external staging/provider/deployment/restore evidence is recorded. The scan artifact URLs and exact SHA are recorded in `docs/IMPLEMENTATION_STATUS.md`; exception expiration must fail closed.


75. P0 hosted-LLM SDK egress: every LangChain/OpenAI-compatible SDK client must inject the DNS-pinned async HTTP client from `backend.services.url_safety`. That client must validate/pin each HTTPS destination, preserve Host/TLS SNI, reject non-HTTPS requests, disable redirects and ignore ambient proxies. SDK constructors without the required safe-client injection must fail the static transport guard. New implementation/test candidate is pending exact-SHA push and PR CI; real staging and provider UAT remain separate release gates.


76. P0 hosted-LLM sync/async egress corrective work is complete and verified: the legacy `ai_memory/rag_chain.py` RetrievalQA factory and primary generation path both receive `http_client` + `http_async_client`. Sync/async transport tests pass on `337e31ed9a964a7cdfcde56abb9ee9d379400265`; see push [40360698617](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40360698617) and PR [40360704559](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40360704559). Keep the static guard strict; staging and provider UAT remain open.
