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


75. P0 hosted-LLM SDK egress is verified on `337e31ed9a964a7cdfcde56abb9ee9d379400265`: push [40360698617](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40360698617) and PR [40360704559](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40360704559) passed. Both ChatOpenAI call paths inject pinned sync + async clients; staging egress/proxy verification and authorized provider UAT remain separate release gates.


76. P0 hosted-LLM sync/async egress corrective work is complete and verified: the legacy `ai_memory/rag_chain.py` RetrievalQA factory and primary generation path both receive `http_client` + `http_async_client`. Sync/async transport tests pass on `337e31ed9a964a7cdfcde56abb9ee9d379400265`; see push [40360698617](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40360698617) and PR [40360704559](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40360704559). Keep the static guard strict; staging and provider UAT remain open.


77. Model-artifact local-only security change is verified on `393e12760762993e70a862af9b4c3ab61d308739`: push [40364123382](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40364123382) and PR [40364131533](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40364131533) both passed. The first SHA `47bd006c665ba490d2cbd0c0a87c57c8350ef0f4` exposed four invalid synthetic snippet fixtures (`\\n` literal text); the strict AST guard was kept, the tests were corrected to real newline escapes, and Python passed 377/3 skipped on the rerun. Artifact staging/license/retrieval evidence remains pending.


78. Next P0 after source-level model egress guard: record real staged model provenance/digest/license approval, demonstrate cache-only load from the release image and run retrieval-golden checks after re-ingestion. Never equate mocked local-only tests or CI imports with production model readiness.


80. Proprietary experiment-learning candidate generator is verified at `a9eebf989704b7d7d347ee9021572bd2d5ea4f03`; push [40365898032](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40365898032) and PR [40365904286](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40365904286) both passed. Python 385 passed/3 skipped; PostgreSQL, AI/RAG/SBOM/license, frontend, security audit, secret scan, 53-skill guard and lockfile-sync passed. Dataset remains review-required only: no visitor identifiers, no provider-attested ground truth, no training/fine-tuning/model promotion. Registry counts are 48 partial/5 not implemented. Next P0: staged model artifact manifest gate.


81. P0 staged-model provenance gate: `scripts/verify_model_artifact_manifest.py` must fail closed on manifest/application SHA mismatch, unsafe or symlinked paths, digest drift, mutable Hub revisions, missing license/acquisition approval evidence, timezone-naive timestamps, `local_files_only != true`, or `trust_remote_code != false`. Run against real staged artifacts before deployment promotion; fixture tests do not prove production staging. Candidate exact-SHA push and PR workflows are pending.



82. Staged model artifact manifest validator is source/CI verified on a3c2627d26a765ac88e4ef3c164b86e850a7c40c. Push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40367360162 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40367367483 passed; Python 396 passed/3 skipped and all required security, SBOM/license, PostgreSQL, frontend, repo-guard and lockfile jobs passed. The CLI validates a real staged directory against its manifest but does not prove the manifest's approval fields are genuine. Actual staged artifact, immutable revision, digest, license sign-off, cache-only runtime load and RAG retrieval evidence remain release gates.


83. 2026-10-27 merchant offer lifecycle is verified on exact SHA \`fd712d411269a251b5fc70c912e2731c55c39a0a\`: push run [40517947381](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40517947381) and PR run [40517953771](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40517953771) both succeeded. Python 406 passed / 3 skipped / 1 existing deprecation warning; PostgreSQL integration 3 passed; frontend production build/typecheck includes \`/merchant/offers\`; AI/RAG, secret scan, security audit, 53-skill source guard and push lockfile reproducibility passed. The temporary LGPL package exceptions are still release blockers; provider UAT, browser UAT and deployment/restore gates remain open.

84. Next unblocked P0: continue with the production release blockers without weakening tests or bypassing licensing. First determine whether \`sharp\`/the LGPL libvips components are actually required by the shipped Next.js runtime; if they are not required, remove them through a supported dependency/configuration change and rerun the full frontend build + dependency/license inventory. If they are required, do not disguise or suppress them: keep release blocked pending documented legal clearance or a validated replacement. In parallel, continue browser-UAT coverage and real staging evidence preparation on this same branch.



85. 2026-10-27 internal publisher marketplace is verified on exact SHA \`de8a59e2e86c6f318a7c9a789516d749debfb9ae\`: push [40522649663](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40522649663) and PR [40522660792](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40522660792) passed. Python 410 passed / 3 skipped / 1 existing deprecation warning; PostgreSQL integration 3 passed; SQLite/PostgreSQL migration drift, frontend build/typecheck, AI/RAG, security audit, secret scan, source/skill guard and push lockfile reproducibility passed. Listing is internal only; provider submission and external affiliate approval remain not configured.



86. Marketplace migration correction history: the first candidate \`4ed81112ad2b579ef88e720c5e4cdef9ce539cf8\` failed SQLite and PostgreSQL drift checks because the new \`marketplace_listed\` server default was absent from ORM metadata. The corrective commit declares matching \`server_default=false()\` and is verified on exact SHA \`de8a59e2e86c6f318a7c9a789516d749debfb9ae\`; push [40522649663](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40522649663) and PR [40522660792](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40522660792) both pass. Preserve failure history and keep migration tests strict.


87. Marketplace eligibility candidate (2026-10-27): enforce merchant region and traffic restrictions on the server before writing applications; normalize whitespace/hyphen/underscore variants and test both rejection/no-row behavior and compliant success. The UI's default values are convenience only; the backend rule is authoritative. Exact-SHA push and PR CI must pass before status is verified.



87. Paid-media guardrails are exact-SHA CI verified on 8a32bfb8c6b948c0b9221a984920183ff609de82: push 40525971292 and PR 40525978916 succeeded; Python 416 passed/3 skipped; PostgreSQL 3 passed; frontend/AI/security/secret/skill/lockfile jobs passed. Live provider mutations, spend authorization and automatic pause are not implemented. License inventory still blocks production release pending LGPL review.


88. Signed ad collector ingestion is exact-SHA CI verified on 13700e8076641ae3dca1244f37b878e890ec6723: push 40528436803 and PR 40528445045 succeeded; Python 420 passed/3 skipped; PostgreSQL 3 passed; migration 0017 drift and downgrade/re-upgrade passed; frontend/AI/security/secret/repo/lockfile jobs passed. HMAC keys remain workspace + platform scoped; only a separately authorized trusted collector can assert source verification, and the application explicitly does not claim a native platform signature. Production license review and real collector/platform UAT remain open.



89. Scheduled ad guardrail evaluation is verified at exact SHA 798d4f60d212ba8d86dbc7d48e72dead52423a93: push 40529623563 and PR 40529634466 both succeeded; Python 422 passed/3 skipped; PostgreSQL 3 passed; SQLite/PostgreSQL migration drift, frontend, AI profile, security, secret scan, repo guard and lockfile passed. The job runs every five minutes and latches verified breaches internally; it does not pause an external account.

90. Next P0 production-release item remains the frontend LGPL-3.0-or-later sharp/libvips license exception. Do not suppress the scanner or treat the temporary inventory exception as approval. Inspect whether the actual deployed frontend requires the native component, then either implement a tested, supported dependency/configuration replacement and regenerate the SBOM or obtain documented legal clearance. Verify exact install/build/production-image contents before closing the blocker.


91. Frontend runtime license remediation is verified at exact SHA bd103628f038401de73e14484088965fb29e0516: push 40536193799 and PR 40536200952 passed. Production runtime verifier and Docker smoke confirmed sharp and @img/sharp-* are absent; production SBOM reviewed 19 packages with no license findings and no exceptions. Full build/install SBOM's two exact libvips notices are build-only and never authorize distribution. Maintain the source guard against next/image, the separate production SBOM with no exception file, and the actual post-prune Docker image test. Overall app release remains separately gated by external provider/UAT, model-artifact, staging, monitoring and backup/restore evidence.


92. Signed ad-metrics collector deployment wiring is a candidate until exact-SHA CI passes. Keep AD_PERFORMANCE_WEBHOOK_SECRETS forwarded through the supported Compose API container environment; .env.example must carry only {} and documentation, never real secrets. Continue to validate per-workspace UUID/platform mapping and >=32-character secrets; this HMAC authenticates the configured collector only, never native provider identity.


93. **No unresolved GitHub Actions failures (standing rule, 2026-10-27):** For every code/documentation checkpoint, inspect push and pull-request Actions runs for the exact resulting SHA. A failure is not considered resolved merely because a later unrelated commit passes: identify the failed job and step from its logs, fix the root cause on this same branch, and rerun the failed job or complete workflow. Do not report a checkpoint as verified while required jobs are queued, running, failed, cancelled, or not inspected. Preserve a concise failure-to-fix-to-rerun evidence trail; if permissions, provider outage, or another external blocker prevents verification, state it explicitly and continue independent checks without claiming success.


94. Jurisdiction-compliance work is not a claim of a worldwide legal database. Record per-jurisdiction authoritative HTTPS source evidence for each required activity category; require current attestation and a separate human decision; expire approvals and re-evaluate evidence at action time; scope approvals to the workspace, activity, channel and every target jurisdiction; audit missing/stale/blocked attempts; and never gate drafts or dry-runs by default. A completed idempotency replay may return its prior result but must not execute a new provider action. Verify exact-SHA push and PR workflows before calling the slice complete; keep other live channels gated until they use the same approval service.


95. Current resume checkpoint (2026-10-28): branch HEAD was inspected as `a9a76b66586bf22b4d39762f2a894ae9eb3cef2f`. The latest push run `40628516136` and PR run `40628523691` failed in the Python job (529 passed, 3 skipped, one failure). Exact failure: `tests/test_content_research_brief.py::test_research_brief_records_hash_and_matches_only_quotes_from_fetched_sources` indexed an empty `observed_statistics` list because the source-stat regex required a word boundary after the percent sign. Fix the regex and add focused regression assertions on this same branch, then inspect exact-SHA push and PR runs, logs, and all required jobs before continuing to the next unblocked requirement. Never treat this candidate as verified before the reruns finish.


96. Verified checkpoint (2026-10-28): current branch head at inspection was `2677741f65aedc1c9c53a53fa5dd3c412abde273`. Exact-SHA push run [40634328707](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40634328707) and PR run [40634334600](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40634334600) completed successfully. Push all 8 jobs passed; PR all required jobs passed (push-only lockfile-sync was skipped on PR). Python 530 passed, 3 skipped, one existing warning. PostgreSQL migrations/drift and concurrency tests passed. Continue from this SHA on the same branch, inspect actual state before the next code change, and do not merge/deploy without authorization and release evidence.


97. Targeted-ad guardrail freshness slice (2026-10-28): inspect verified provider evidence freshness before any budget/ROAS/CPA stop recommendation. Candidate change adds a 24-hour maximum age for each creative/platform's latest observation and blocks materially future-dated observations (>5-minute clock skew). Historical daily snapshots remain usable for campaign totals when the latest point is fresh. No remote ad action is executed by the evaluator. Added stale/fresh-history/future-timestamp regression tests; do not call this verified until exact-SHA push and PR CI both finish. Continue on the existing branch only.


98. Verified targeted-ad freshness gate (2026-10-28): implementation commit `3bc5770f3c89561e13686ea9c0023dd1ebbf5d78`. Push [40636590192](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40636590192) and PR [40636595214](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40636595214) completed successfully. Push all 8 jobs passed; PR required jobs passed, push-only lockfile-sync skipped. Python 532 passed, 3 skipped, one warning; PostgreSQL, frontend build/container smoke, AI/RAG, security, secret scan and repo guard passed. The evaluator blocks stale (>24 h) and materially future-dated (>5 min) latest provider observations while retaining historical daily snapshots when a fresh latest point exists. It remains recommendation-only and does not mutate provider campaigns. Continue on the existing branch and re-verify exact SHA after every subsequent change.

13. Budget enforcement must be race-safe across application replicas: budget usage check and reservation insert must share a transaction-scoped, workspace-keyed PostgreSQL lock; SQLite-only tests do not count as proof of distributed concurrency. Keep provider spend and external campaign mutations disabled until explicit authorization and kill-switch acceptance.
14. The live `docs/skill-parity-matrix.csv` currently contains 53 rows, all marked `partial`; historical audit summaries showing 47 partial / 6 not implemented are stale and must not override the current CSV or `scripts/verify_skill_registry.py`. Update the status ledger and backlog to match the live matrix, and preserve the canonical status-count phrase expected by the parity guard.

15. Email opt-out is a durable suppression state. Re-subscription must require both fresh affirmative consent and an explicit confirmation flag, write a privacy-minimizing audit event, preserve old suppressed delivery history, and schedule a new idempotent sequence without reviving canceled messages.

16. Conversion reversal processing must preserve an append-only signed ledger, serialize against the original conversion row, allow explicit partial-refund events only when their offsets do not exceed the remaining original amounts, and make later full reversals offset only the remaining balance. Unmatched partial reversals must be rejected rather than guessed.

17. Financial reversal acceptance must include a real PostgreSQL ledger test: partial reversal then full reversal must offset only the remaining balance, preserve immutable ledger entries, and net both commission and revenue to zero. Mocked route tests alone do not establish database correctness.

18. Public landing pages must expose separate controls for consent to receive marketing emails and optional explicit re-subscription confirmation. Never make the re-subscribe checkbox required for first-time subscribers; server-side logic must still require it when the existing lead is unsubscribed.

19. Learning must not count reversal event rows as new conversions or train on fully reversed outcomes. For partially reversed original conversions, use the append-only ledger to calculate net commission; keep sample-size gates and human review/promotion safeguards in place.


## 2026-10-29 verified checkpoint — workspace offer shortlists

- Current exact code checkpoint: 3badf73a5c6eb25d8cdd06fd8e1d49ae7734e324.
- Workspace-scoped saved offer lists and comparison API/UI are implemented with migration, API regression tests and browser lifecycle UAT.
- Push 40822087405 and PR 40822092898 passed. Python 743 passed / 7 skipped / 5 warnings; browser UAT 12 passed in both; PostgreSQL, frontend/Docker, AI/RAG, security/SBOM, secret scan and repository guard passed. PR lockfile-sync skipped by the configured push-only condition.
- Earlier browser locator failure on 05323ad40bfe14c34bbf3b44da4931abbff37b4f was fixed by targeting the offer heading; the current exact SHA is green.
- This checkpoint does not establish official provider verification or production readiness. Continue to the next unblocked traceability gap without creating a branch.


## 2026-10-29 follow-up — shortlist note entry in the catalog UI

- The offer catalog now provides an optional per-offer review-note input when a saved list is selected and persists the note through the existing shortlist item API. Notes are shown in the saved list detail. Browser UAT now enters a note, saves the offer, and verifies that the note appears before removing the item and deleting the list.
- Exact code-and-test SHA: 267dd5c489b92c0d6b02c1229e4162d9736a7cd4. Push [40822952573](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40822952573) and PR [40822958502](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40822958502) passed all configured jobs. Python 743 passed / 7 skipped / 5 warnings; browser UAT 12 passed in both. PostgreSQL integration/migration, frontend typecheck/build/Docker smoke, AI/RAG, security/SBOM, secret scan and repository guard passed. Push lockfile-sync passed; PR lockfile-sync was skipped by its configured condition.
- Provider verification, offer qualification, live marketplace contracts and production readiness remain separate gaps.


## 2026-10-29 verified increment — workspace offer qualification review

- Added the S1 qualification queue and workspace-specific review record for account eligibility, geography, traffic-source policy, program terms, landing-page review and disclosure readiness. Workspace owners/admins can record a decision, reviewer identity, timestamp, policy/checklist version, notes and evidence URLs.
- A “qualified” decision requires all six checklist fields to be operator-attested pass plus at least one HTTPS evidence URL. Private/non-public IP evidence URLs are rejected. This is internal planning status only; provider authenticity, account eligibility, offer approval and terms are not independently verified and no publishing/activation is enabled.
- Added migration 0029_offer_qualification_reviews, request validation, bounded status-filtered queue API, role-gated save API, a dedicated qualification review page, regression tests for checklist/evidence requirements and workspace isolation, and Chromium acceptance for the operator review journey.
- Exact verified code SHA: 03bdbb6f60a6e8b9f86472a86f17d0156214dadc. Push [40824127725](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40824127725) and PR [40824132752](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40824132752) passed all configured jobs. Python 744 passed / 7 skipped / 5 warnings; browser UAT 13 passed in both. PostgreSQL migration/integration, frontend typecheck/production build/Docker smoke, AI/RAG, security/SBOM, secret scan and repository guard passed. Push lockfile-sync passed; PR lockfile-sync was skipped by its configured condition.
- The S1 skill remains partial because official marketplace integrations, provider-attested evidence, account eligibility verification and live provider contract acceptance remain open. Production release gates remain open.


## 2026-10-29 qualification queue pagination follow-up (verification pending)

- The qualification queue API already supported bounded limit/offset, but the UI exposed only the first 50 results. The latest additive change adds Previous/Next controls, current-range/total display, preserves the active filter when paging, resets to page one on filter change, and reloads the current page after saving a decision.
- Added Chromium acceptance for a 52-offer queue, next/previous navigation, filter preservation and error-free rendering. The qualification decision and evidence contracts are unchanged.
- Candidate SHA: fe86be600d4c526fa9226cef1b424726fa9d27e0 (parent 03bdbb6f60a6e8b9f86472a86f17d0156214dadc). The immediately preceding code checkpoint 03bdbb6f60a6e8b9f86472a86f17d0156214dadc passed push 40824127725 and PR 40824132752, including 744 Python tests and 13 browser tests. Workflows for the pagination candidate were canceled while concurrent workflow attempts were in flight; do not treat those canceled runs as passing. Exact-head push and PR verification is pending for the current candidate.
- Product status remains NOT RELEASE READY; pagination improves access to the queue but does not establish provider verification or production acceptance.

## 2026-10-29 — immutable comparison draft revision acceptance

- Continue from exact verified branch head `62dfa336dfa4c617359f01588037611ec93be899`; never overwrite an existing saved comparison `ContentAsset` to revise it.
- Revision source IDs must be looked up by authenticated active workspace ID and the comparison-post asset type; return 404 for absent/foreign source assets and reject non-draft sources. Verify the source before network/model work, and create a separate revision asset with parent/root lineage and an audited `content_comparison_post.revised` event.
- Root lineage must be persisted by assigning a fresh JSON dictionary after flush, not by mutating a dictionary already attached to SQLAlchemy. Keep a regression that reads the committed database row to catch JSON mutation tracking mistakes.
- Test a real branch on draft history: load a saved draft, change fields, save a revision, assert original body/title unchanged, assert revision parent/root and audit record, and assert cross-workspace revision requests fail before invoking the generation service.
- Exact-SHA push [40858629542](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40858629542) and PR [40858638120](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40858638120) passed: Python 787 passed/7 skipped/5 warnings; browser UAT 25 passed; PostgreSQL, frontend/Docker, AI/RAG, security/SBOM, secret scan and repo guard passed. Push lockfile-sync passed; PR lockfile-sync skipped by configured push-only condition.
- The verified slice does not prove merchant claims, affiliate eligibility, legal compliance or live publication. Production release remains blocked by provider UAT, full 53-skill acceptance, staged deployment, observability and backup/restore/rollback gates.

99. Verified 2026-10-30 — Platform Super Admin read-only operations overview added at `6519c00e6188cc20473069e76722972fa3245c76` on the existing `build/omni-affiliate-os-production` branch. Push 41038731067 and PR 41038737403 both passed; Python 843 passed/9 skipped/5 warnings and Chromium UAT 36 passed on each. PostgreSQL, frontend production build/Docker smoke, security/SBOM, AI/RAG, secret scan, repo guard and push lockfile-sync passed. The new page uses existing protected read-only APIs; it does not add provider authorization or queue recovery. Do not interpret configuration/runtime values as provider connectivity or deployment proof. Preserve tenant and emergency-pause controls.

100. Verified 2026-10-30 — Capability gate corrections delivered at `d905ab59b3721d7ee31a87cf1b81a3a4ce44bb84` on the existing `build/omni-affiliate-os-production` branch. Configured-but-unverified providers/offers and the existing limited Super Admin foundation are classified `partially_available`; Admin renders the protected capability matrix read-only. Push 41040130228 and PR 41040137164 passed: Python 845 passed/9 skipped/5 warnings; Chromium UAT 36 passed on each; PostgreSQL, frontend build/container smoke, AI/RAG, security/SBOM/license/dependency audit, secret scan, repo guard and push lockfile-sync passed. PR lockfile-sync skipped by its push-only condition. This does not prove account connectivity, authorize external provider writes or certify production deployment.


101. Verified 2026-10-30 — merchant approval counts are shown without conflating internal and external approval. `frontend/app/merchant/page.tsx` displays an explicit “Approved internally” metric and keeps “Marked network-approved” separate. Browser fixture adds an internally approved / network-pending offer and asserts the two counts independently. Final SHA `9e199232e41d1a1be3e19128fe365bf169cc20a9`: push [41046673153](https://github.com/AITECHPRODUCTS/Project1/actions/runs/41046673153) and PR [41046682202](https://github.com/AITECHPRODUCTS/Project1/actions/runs/41046682202) passed; Python 845 passed/9 skipped/5 warnings; browser UAT 36 passed each; PostgreSQL, frontend/Docker, AI/RAG, security/SBOM/license/dependency, secret scan, repo guard and push lockfile-sync passed (PR lockfile-sync push-only skip). Initial locator ambiguity and its test-only fix are retained in commit history. This verifies the dashboard distinction only; it does not prove a real affiliate-network approval or overall production readiness.

102. Verified 2026-10-30 — newline-separated evidence URLs and webinar agenda items corrected on existing build/omni-affiliate-os-production branch at code/test SHA c313521f0f818533aea5473d5e6bce73d086b571. frontend/app/page.tsx now correctly splits LF/CRLF input for affiliate-program evidence URLs and webinar agenda rows. Browser tests capture actual POST payloads for /api/research/program-applications and /api/webinars; provider program submission stays manual-handoff-only and webinar provider/email remain not configured. Exact push 41064823079 and PR 41064833717 completed successfully: Python 845 passed/9 skipped/5 warnings; PostgreSQL 9 passed; Chromium UAT 39 passed; frontend/Docker, AI/RAG, security/SBOM, secret scan and repo guard passed. Push lockfile-sync passed; PR lockfile-sync skipped by push-only condition. This does not prove live account integrations or production readiness.
