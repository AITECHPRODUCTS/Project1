# Implementation status — Project1 / OmniAffiliateOS
Updated: 2026-10-26

## Repository/build
- Canonical repository: https://github.com/AITECHPRODUCTS/Project1 (public).
- Implementation branch: `build/omni-affiliate-os-production`.
- Release gate: NOT RELEASE READY until current GitHub Actions checks pass on one candidate SHA and migrations/security/UAT are verified.
- CI workflow: `.github/workflows/ci.yml`; push to `build/**`, pull request to main, and manual workflow_dispatch.

## Implemented code present in this branch
FastAPI endpoints, SQLAlchemy persistence models, S1–S8 workflow runner, workflow checkpoints and human review pauses, RAG ingestion/retrieval path, offer directory adapter, provider-readiness registry, measured offer scoring, source-backed content draft helpers, campaign tracking primitives, consent-based lead/email queue, CMS boundaries, video rendering helper, cost estimate reservations, commission observations, protected financial operations, responsive Next.js dashboard, frontend API client, Docker/Compose, and focused tests.

## Capability distinctions
A provider being catalogued does not mean the account is connected. A configured secret does not prove approved scope or successful authentication. Current adapter coverage is a mixture of directory adapter, operator-configured boundary and catalog-only entries. No provider is marked production verified by configuration alone. Automated public publishing, KYC/application approval and paid-ad operations require authorized provider access and policy-compliant scopes.

## Skill parity
See `skill-parity-matrix.csv`: 53 skill rows are explicitly traced. Current matrix is 48 partial and 5 not implemented, 0 fully implemented end-to-end. These 53 rows are a skill inventory only, not overall product-completion percentages. That is a gap ledger—not a claim that reference skill text equals working runtime behavior.

## Evidence
The GitHub Actions run linked from the repository is the authoritative check result. Local static source checks do not replace provider tests, browser UAT, backup/restore tests, PostgreSQL migration testing, or deployment health verification.

## 2026-10-24 implementation update — AI ad planning slice
- Added draft-only `POST /api/ads/plan` with a typed request model and an audit event.
- Added `backend/services/ad_planner.py`: structured audience hypotheses, platform-specific creative variants, disclosure included in every creative, unverified fact/evidence states, equal exploratory budget allocation, and null KPI forecasts until real campaign data exists.
- Optional configured-model enrichment uses the existing LLM service; failures preserve the structured baseline and are reported as warnings. No publishing or ad spend is performed by this endpoint.
- Tests: `tests/test_ad_planner.py` covers variants, disclosures, safe defaults, cent-accurate budget split, unknown KPI values, evidence/fact statuses, unsupported platforms, and URL validation.
- Release status remains **NOT RELEASE READY** until the new exact commit's hosted CI, PostgreSQL tenant isolation, browser UAT, provider authorization/contract tests, security scans, and deployment/restore gates are verified.

## 2026-10-24 implementation update — platform operations access boundary
- Added a separate `require_platform_admin` dependency that requires `is_admin is True`; workspace owner/admin roles alone receive HTTP 403.
- Added read-only, cross-tenant overview, tenant inventory, workflow-history and high-level audit endpoints under `/api/admin/*`. Global reads use an explicit global scope and avoid returning raw workflow inputs, result payloads or audit detail JSON.
- Added a role-gated Operations section in the dashboard. It is hidden unless `/api/auth/me` or login returns the explicit global admin flag.
- Tests cover the separation between workspace roles and the platform role. This is a partial operations surface; lifecycle mutation, durable queue controls, kill switches and release/deployment verification remain unimplemented or unverified.

## 2026-10-24 implementation update — persisted ad planning
- Added tenant-scoped `AdCampaignPlanRecord` and Alembic revision `0003_ad_campaign_plans` with Decimal/Numeric daily budget storage, platform list, structured plan JSON and draft status.
- `POST /api/ads/plan` now persists the plan and an audit event in one transaction.
- Added `GET /api/ads/plans` and `GET /api/ads/plans/{plan_id}`; database queries inherit the active workspace scope.
- Added persistence/API tests for creation, listing/detail retrieval, zero external side effects, decimal budget round-trip and missing-plan 404 behavior. Dashboard Ad studio includes a saved-plans control.
- External publication and ad spend remain disabled. PostgreSQL migration/tenant isolation, browser UAT and provider contract verification remain release gates.

- Tenant-isolation regression: `tests/test_tenant_isolation.py::test_ad_plan_rows_are_scoped_to_active_workspace` verifies that persisted ad plans inherit their workspace and are invisible to other workspace queries.

## 2026-10-24 implementation update — ad performance evidence
- Added tenant-scoped `AdPerformanceObservation` and Alembic revision `0004_ad_performance_observations` to store reported impressions, clicks, conversions, spend, commission, source type/reference and observation time.
- Added validated `POST /api/ads/observations`, `GET /api/ads/observations`, and `GET /api/ads/performance`. User-provided records are always marked `operator_supplied_unverified`; the submitted source type is not treated as provider attestation.
- Performance summaries calculate reported CTR, CPC, conversion rate, CPA and commission-to-spend ratio but explicitly block optimization eligibility while provider evidence is unverified. Even verified-data recommendations are review-only; the API does not perform external actions.
- Added negative-money/unsafe-URL validation and API persistence/summary tests. Dashboard includes a reported-results form and a performance-summary action.
- Remaining gate: implement an authorized provider ingestion/verification path, then evaluate verified KPI sample-size, attribution and stop-loss logic before enabling any remote campaign mutation.


## 2026-10-25 implementation update — finance evidence isolation and currency-safe ledger
- Added read-only evidence-based commission reconciliation candidates; matches remain unverified and never confirm a payout.
- Explicitly scoped reconciliation and commission-email imports to the active workspace. Email import uses per-message savepoints so a concurrent duplicate does not discard unrelated messages in the batch.
- The finance ledger now reports totals grouped by currency across the full active-workspace ledger, separately from its bounded 500-row detail feed; the legacy total field is explicitly USD.
- Hosted CI evidence is tracked by exact commit and workflow URL. This does not certify production deployment, provider authorization, PostgreSQL restore/UAT, or live affiliate revenue.


## 2026-10-25 implementation update — tenant-scoped conversion idempotency
- Provider conversion identity is now unique per workspace, rather than globally across all tenants. This prevents one workspace's provider event ID from blocking another workspace's legitimate event.
- Added an Alembic migration and a cross-workspace regression test. The migration must pass the hosted upgrade/downgrade/drift gate before this schema change is considered validated.


## 2026-10-25 implementation update — finance review controls
- Added a workspace-admin review endpoint for commission email evidence with candidate validation, explicit decisions, and an audit event. Accepting a conversion match does not confirm payment or initiate a transfer.
- Added the Measurement console in the Next.js dashboard for the workspace ledger, currency-separated totals, reconciliation queue, email evidence, payout thresholds, and gated review actions.
- Hosted frontend typecheck/build, Python tests, and AI/RAG dependency checks are required on the exact resulting commit before treating this change as validated.


## 2026-10-25 implementation update — deterministic A/B assignment and posterior analysis
- A visitor now receives the same variant for a given experiment regardless of aggregate conversion counts; historical performance no longer randomly changes a returning visitor's headline.
- Added deterministic Beta-Binomial posterior probability estimation and a minimum-sample gate for recommendations. Results are explicitly decision support, not a p-value or proof of causation.
- A durable impression/conversion assignment ledger remains pending; this slice does not claim end-to-end experiment tracking.


## 2026-10-25 implementation update — persisted A/B experiment ledger
- Added workspace-scoped experiment assignments with immutable headline snapshots and a unique experiment/visitor key.
- Added idempotent impression/conversion event ingestion keyed by a workspace event ID. A/B analysis now derives counts from persisted events instead of trusting caller-supplied aggregate metrics.
- Migration `0006_experiment_assignment_ledger` and regression tests cover stable assignment, repeated events, duplicate event IDs and workspace isolation. Experiment UI, provider-side event attestation and held-out evaluation remain pending.


## 2026-10-25 implementation update — A/B experiment dashboard
- Added an Experiments navigation section with stable browser visitor ID, immutable experiment headline snapshots, persisted variant assignment, manual impression/conversion event recording, and posterior recommendation display.
- The dashboard labels event recording as manual and does not claim that this console is a production website tracking SDK. Production site instrumentation and held-out evaluation remain gaps.


## 2026-10-25 implementation update — platform-native content atomizer
- Added `POST /api/content/atomize` to generate source-grounded drafts for blog, LinkedIn, X, X threads, Reddit, Pinterest, TikTok, YouTube Shorts and email.
- LLM output is parsed defensively, source quotes are checked against supplied text, disclosure is enforced, and a deterministic fallback is used when the provider fails or returns invalid JSON.
- Each output is persisted as a workspace-scoped draft `ContentAsset`; publishing is not started and human review is required.

## 2026-10-25 implementation update — platform-specific AI ad targeting hypotheses
- Extended POST /api/ads/plan with channel-specific targeting strategies for all supported planning platforms, recommended non-sensitive signals, three audience-test cells, objective-to-event measurement hypotheses, and cent-exact per-audience draft budget allocations.
- Provider feature availability and authorization are explicitly unverified; event readiness is not assumed; targeting requires policy and measurement review; sensitive traits and proxies are excluded; first-party list use requires appropriate permission and consent.
- Automated launch, audience upload, pause and scale remain disabled. No CTR, conversion, CPA or ROAS forecasts are fabricated.
- Ad Studio now captures optional product context and landing-page URL. The planner does not crawl or approve the destination.
- Added regression tests for channel-specific guidance, audience budget conservation, unset budgets, event hypotheses and safety gates.
- Hosted CI must pass on the resulting exact candidate SHA before this slice is considered verified. Live provider policies, verified event ingestion, stop-loss execution and browser UAT remain pending.

## 2026-10-25 hardening update — ad analytics authorization
- Closed an access-control gap in ad plan listing/detail, observations, performance summary and ROAS evaluation routes: they now require an authenticated identity with an active workspace before reading or calculating ad data. Ad plan creation and observation ingestion also reject users without a selected workspace.
- Added `tests/test_ad_route_access.py` for both unauthenticated access and authenticated-but-no-workspace attempts across the ad routes.
- New candidate must pass hosted CI on the exact SHA. Production session/cookie settings, PostgreSQL tenant-isolation coverage and real-provider integration still require release-stage verification.

## 2026-10-25 implementation update — internal-link opportunity finder
- Added `POST /api/research/internal-links` for authenticated, same-origin sets of 2–12 user-supplied public pages.
- Page retrieval reuses outbound public-host validation, limits each HTML body to 1 MB, uses bounded concurrency, does not follow redirects or fetch discovered links, and returns individual page failures without losing the rest of the batch.
- Deterministic topic-overlap scoring suggests missing source-to-destination links and anchor text from the destination headings. It is review-only; no links are inserted and no ranking or traffic impact is predicted.
- Added regression coverage for topical recommendations, skipping existing links, partial fetch failure, minimum successful page count, same-origin/private URL rejection and the API response.
- CMS-wide crawl index, auto insertion, client-rendered page coverage and browser UAT remain pending.

## 2026-10-25 implementation update — verified-data ad optimization review signals
- Added provider-verified sample gates (minimum 1,000 impressions and 30 clicks) before ROAS-based stop-loss or scale review. Insufficient or unverified evidence cannot trigger either recommendation.
- A scale review requires ROAS at least 1.25× the existing review threshold plus at least 10 reported conversions. Stop-loss and scale outcomes remain human review suggestions only; no provider API is called to pause or increase spend.
- A creative-fatigue signal requires four distinct provider-verified observation dates, at least 1,000 impressions and 30 clicks in each two-day comparison window, and a 30% or greater CTR decline. This is a heuristic review flag, not proof of fatigue.
- Regression tests cover insufficient sample, stop-loss review, scale review, fatigue detection and blocking unverified reports.
- Trusted provider ingestion, attribution-window maturity, production instrumentation and browser UAT remain pending.

## 2026-10-25 security hardening — finance, leads, email queue and audit
- Finance threshold balances and commission-email evidence, lead PII, scheduled-email queue details, and audit-log reads now require an authenticated active workspace and explicit workspace filtering.
- Threshold creation and funds-received annotations now bind to the active workspace; a threshold lookup cannot mutate another tenant's record.
- The user-triggered email worker now requires a workspace owner/admin, filters queued messages by that workspace, and checks the matching lead record before sending. The internal scheduler keeps its existing system-level behavior when no workspace is supplied.
- Added route-level regression tests for unauthenticated and no-workspace access across the eight protected endpoints.
- Hosted tests must pass on the exact candidate SHA. Session/cookie review, production PostgreSQL cross-tenant tests, Resend/provider contract tests and live UAT remain release gates.

## 2026-10-25 implementation update — source-grounded X thread writer
- Added a dedicated dashboard workflow for generating X thread drafts from operator-supplied source text and optional public reference URLs. Drafts reuse the existing workspace-scoped content-atomizer persistence path.
- X thread output is normalized into numbered posts with a 280-character maximum per post and a final disclosure reminder. Source facts and claim-review notes are retained; the operation never publishes and does not assume X account access or policy approval.
- Added regression tests for model-generated long posts, deterministic fallback, numbering, disclosure and per-post length, plus the persisted API path.
- X publishing authorization, platform-policy/format verification and browser UAT remain pending. Hosted CI on the exact resulting SHA is the acceptance gate.

## 2026-10-25 implementation update — Purple Cow differentiation audit
- Added typed request validation and an authenticated workspace-gated research endpoint that compares a proposed positioning statement only against alternatives supplied by the operator.
- The score exposes lexical distinctiveness, audience-language fit, clarity, optional evidence readiness and risk penalties. Missing proof is marked as missing; supplied notes and alternative statements are not treated as verified.
- Added a dashboard form, API and service regression tests, and updated the skill parity and requirement traceability records.
- Market validation, primary-source evidence review, buyer interviews and browser UAT remain pending; no competitor crawl or external action is performed by this feature.

## 2026-10-25 implementation update — searchable skill finder
- Added a workspace-authenticated read-only search endpoint and dashboard panel for the 53-row skill parity inventory, with stage and implementation-status filters and relevance-ranked results.
- The inventory CSV is copied into the Docker runtime image. Missing or malformed inventory data fails explicitly rather than returning fabricated capability results.
- Updated the parity matrix, implementation status, requirement traceability and v4 backlog counts. The inventory is a progress ledger, not an end-to-end production readiness certificate.
- Full upstream skill source coverage, service-level acceptance tests for each skill, provider authorization and browser UAT remain open gates.

## 2026-10-25 implementation update — deterministic SVG infographic drafts
- Added a typed, authenticated workspace-scoped infographic endpoint that creates a self-contained 1080×1350 SVG using three to six operator-supplied points, line-wrapping and fixed safe colors.
- The SVG is XML-escaped, contains no embedded images, scripts or remote resources, and is persisted as a draft ContentAsset. The dashboard previews and downloads the SVG.
- Added regression and API tests for markup escaping, layout bounds, unsafe source-reference rejection and draft persistence.
- Licensed imagery, generated raster/image models, brand templates, accessibility/browser UAT and publication remain pending; source URLs are retained as references and not fetched.

## 2026-10-25 implementation update — merchant-terms-based guarantee drafts
- Added a typed, authenticated workspace-scoped guarantee-copy endpoint and dashboard form. The requested guarantee type and duration must appear in the operator-supplied terms text before a draft is generated.
- Draft wording lists operator-supplied eligibility, exclusions and claim process, stores the generated copy as a reviewable ContentAsset and marks terms unverified. A supplied source URL is retained as metadata only; it is not fetched and does not prove the offer is current.
- Added service/schema/API regression tests for invented-period/type rejection, source URL safety, missing exclusions and draft-only persistence.
- Independent merchant verification, legal/policy review, terms change monitoring and browser UAT remain pending; no guarantee is published automatically.

## 2026-10-25 implementation update — category taxonomy designer
- Added a typed, authenticated workspace-scoped taxonomy endpoint using only operator-supplied topic candidates and optional current category labels. It creates deterministic slugs, draft descriptions and lexical overlap flags, then stores the proposal as a ContentAsset draft.
- The API/UI explicitly state that search volume, user demand, taxonomy quality and canonical/navigation impact have not been evaluated; no live pages are changed or published.
- Added service/schema/API regression tests and updated the parity, traceability and backlog records. The existing guarantee draft now stores a SHA-256 fingerprint of submitted merchant terms rather than a duplicate full-text copy.
- Category performance evaluation, user research, live crawl/CMS application and browser UAT remain pending.


## 2026-10-25 implementation update — content decay detector
- Added a typed, authenticated workspace-scoped POST /api/research/content-decay workflow that compares operator-supplied previous/current click, impression and average-position data and explicit content/competitor/SERP observations.
- The service calculates transparent decline deltas, queues evidence-backed refresh candidates using revenue impact, severity, effort and competitor-threat inputs, produces concrete review actions and an optional monthly priority schedule, and persists the report as a draft asset.
- Added schema constraints for public same-origin page URLs, paired measurement windows, nonnegative metrics and publish/update dates. Age alone is only a preliminary freshness prompt and does not label a page as decaying.
- No Search Console connection, live crawl, search/competitor lookup, traffic-recovery forecast or publishing action is performed; all submitted evidence is marked operator-supplied and unverified.
- Added service, validation and API regression tests. Search Console provider ingestion, competitor/SERP evidence acquisition, end-to-end browser UAT and real post-refresh outcome evaluation remain pending.


## 2026-10-25 implementation update — content moat calculator
- Added a typed, authenticated workspace-scoped POST /api/research/content-moat workflow that calculates a 1.5× benchmark from operator-supplied competitor topic-page counts, current page inventory and weekly publishing capacity.
- Added transparent average/target/gap/timeline arithmetic, feasibility bands, a phased page roadmap and evidence/quality/freshness caveats. Competitor domains, quality labels and freshness notes are stored as unverified inputs; the page-count model is not a ranking prediction.
- The report is persisted as a review-only workspace ContentAsset and can be exported as JSON from the responsive dashboard panel.
- Added schema, service and API regression tests. Live competitor discovery, domain crawling, search-volume/demand validation and browser UAT remain pending.


## 2026-10-25 implementation update — traffic analyzer
- Added a typed, authenticated workspace-scoped POST /api/research/traffic-analyzer workflow for 1–5 supplied domains, with traffic-volume/rank/engagement/source-mix score components, optional comparison, risk flags and focus-specific interpretation.
- Missing score components are excluded and remaining weights normalized; insufficient data remains explicitly unscored. The report is persisted as a review-only ContentAsset and can be exported from the dashboard.
- Added validation for public domain inputs, unique domains, non-negative and bounded metrics, and plausible traffic-source percentages. No SimilarWeb/API request, website crawl, external search, conversion verification or publishing occurs.
- Added schema, service and API regression tests; also aligned content-moat phase week totals with the overall modeled publishing timeline.
- Authorized analytics provider connection, live-source verification, location-specific estimates and browser UAT remain pending.


## 2026-10-25 implementation update — multi-program portfolio manager
- Added an authenticated workspace-scoped POST /api/automation/multi-program-manager endpoint. It calculates EPC, revenue share, concentration, niche overlap, recurring-revenue share, metric completeness and cautious per-program actions from explicitly supplied inputs.
- Added goal-specific portfolio guidance, traceable recommendations and a weekly action plan whose hour allocation sums to the provided budget. Output persists as a review-only workspace ContentAsset.
- Missing clicks/revenue remain unknown; phase-out is only a candidate when measured low-EPC evidence crosses conservative thresholds. Program status, tracking, official terms and payouts are not automatically changed or independently verified.
- Added schema, service and API tests plus the responsive dashboard panel and JSON export. Live affiliate-network connections, payout reconciliation and browser UAT remain pending.


## 2026-10-25 security hardening — bounded affiliate conversion webhook bodies
- Added a 256 KiB maximum request-body limit on the signed affiliate conversion webhook. An oversized declared Content-Length is rejected before reading the body; streamed/chunked requests are bounded while bytes are consumed so a missing/misleading length cannot bypass the guard.
- Oversized events fail with HTTP 413 before signature parsing, database lookup or persistence. The endpoint remains provider-signature gated, and no publishing or payout behavior was enabled.
- Added route regression tests for declared-length and streamed oversized payloads, including assertions that no database access or writes occur.
- Verification status: implementation is committed on the existing branch; the new exact-SHA Actions jobs are the acceptance gate. PostgreSQL production ingress/proxy body limits and provider contract tests remain separate release gates.


## 2026-10-25 implementation update — reversal concurrency protection
- Affiliate conversion webhook reversal lookup now requests a database row lock (SELECT ... FOR UPDATE) on the original conversion before testing/updating its reversal status. On PostgreSQL this serializes competing full-reversal attempts for the same original event, preventing two distinct callback IDs from both applying the same full commission offset under normal READ COMMITTED transaction isolation.
- Added regression tests for reversal amount/sign, source-event linkage, row-lock query construction and a second reversal against an already reversed conversion.
- This does not claim support for partial reversals or certify PostgreSQL concurrency behavior; a real PostgreSQL integration test and append-only ledger redesign remain release gates. The existing conversion row status is still updated as a summary state while a reversal observation is recorded separately.
- Acceptance gate: hosted Python tests/migration check, AI/RAG dependency verification and frontend typecheck/build on the exact new SHA.


## 2026-10-25 test infrastructure — PostgreSQL integration acceptance
- Added a dedicated GitHub Actions PostgreSQL 16 service job. It runs the actual Alembic upgrade, drift check, downgrade/upgrade cycle, and a concurrent signed-conversion reversal API test against PostgreSQL (not SQLite).
- The integration test creates isolated test workspace/campaign/click/conversion fixtures, sends two distinct full-reversal events concurrently, asserts exactly one offset is recorded and one is ignored, verifies ledger totals/statuses, and removes its test rows.
- Verified on commit `da5c0c76286df5a7f4ff2fc67d10cd3f3b44fee4`: hosted PostgreSQL 16 migration/drift/rollback/upgrade and concurrent-reversal test passed (`1 passed`); SQLite/Python suite, frontend typecheck/build, and AI/RAG import job also passed in both push and pull-request runs. This does not certify production schema restore/backups, load behavior, partial reversals, external provider scopes or deployed ingress settings.


## 2026-10-25 PostgreSQL CI repair — foreign-key identifier length
- The first PostgreSQL 16 run exposed an existing migration identifier that exceeded PostgreSQL's 63-character identifier limit: `fk_ad_performance_observations_campaign_plan_id_ad_campaign_plans`.
- Applied the same stable short constraint name `fk_ad_perf_obs_campaign_plan` to both Alembic revision 0004 and the ORM model metadata. This preserves the FK target and ON DELETE SET NULL behavior.
- Verified on `da5c0c76286df5a7f4ff2fc67d10cd3f3b44fee4`: the PostgreSQL 16 migration gate completed upgrade through revisions 0001–0006, reported no schema drift, completed downgrade/upgrade and passed the concurrent reversal test.


## 2026-10-25 PostgreSQL CI repair — Alembic revision storage width
- The next PostgreSQL 16 run exposed a second SQLite-invisible migration defect: Alembic's default `alembic_version.version_num VARCHAR(32)` could not store the existing revision identifier `0005_workspace_scoped_conversion_identity`.
- Revision 0005 now widens that internal bookkeeping column to VARCHAR(255) on PostgreSQL before Alembic attempts to stamp the revision. SQLite continues on its existing path because its schema does not enforce the VARCHAR length; no business table data or revision identifiers are changed.
- Verified on `da5c0c76286df5a7f4ff2fc67d10cd3f3b44fee4`: PostgreSQL accepted the revision identifiers after the bookkeeping column was widened; migration upgrade/downgrade/upgrade and schema drift checks passed. The initial failure remains in Actions history as evidence of the fixed issue.


## 2026-10-25 continuation — per-network affiliate webhook secrets
- Added optional `AFFILIATE_WEBHOOK_SECRETS` JSON mapping, normalized by network name (trimmed, lowercase) and validated so each mapped secret is at least 32 characters.
- When the map is non-empty, only the secret for the route's network is accepted and a missing mapping fails closed; the legacy shared `AFFILIATE_WEBHOOK_SECRET` is used only when the map is empty. Production configuration may use either a sufficiently strong shared secret or one or more valid per-network secrets.
- Added tests for settings normalization, weak secret rejection, rejection of a shared-secret-signed event when a per-network key exists, fail-closed behavior for unmapped networks, and successful persistence with a network-specific key.
- Verified on `c8030ed68c7136fb8977b6dd9f9d5f2afa54ae23`: push and PR runs passed all four jobs (Python, frontend, AI/RAG and PostgreSQL). The Python run recorded 207 passed and 1 skipped. The existing conversion webhook remains bounded, HMAC verified, workspace-resolved, idempotent and covered by PostgreSQL concurrent-reversal CI. Production provider-specific signing formats and account-authenticated APIs remain unverified.


## 2026-10-25 S6 finance increment — append-only decimal conversion ledger
- Added `ConversionLedgerEntry` as a separate immutable observation record using `Numeric(18,6)` commission/revenue amounts, currency, source event evidence, conversion/reversal event type, original event linkage and explicit evidence status.
- Alembic revision `0007_conversion_ledger` backfills existing conversion rows as `legacy_unverified` historical snapshots rather than falsely upgrading their evidence quality. New signed webhook events are recorded as `signed_webhook_verified`; the compatibility conversion intake endpoint records `api_submitted_unverified`.
- Added database-level PostgreSQL/SQLite triggers that reject ledger updates/deletes plus an ORM guard, idempotency constraint, workspace-scoped read-only `GET /api/finance/conversion-ledger` and currency/evidence-separated totals emitted as decimal strings.
- Updated webhook tests to verify that a conversion summary and its immutable ledger observation are committed together. Added API/ORM ledger tests and expanded the PostgreSQL test to verify direct SQL mutation is rejected.
- Verified on commit `67df5a275176ebda09fa2e2f7aec041928c4e126`: push and PR workflows both passed all four jobs. The SQLite and PostgreSQL migration upgrades, schema drift and downgrade/upgrade checks passed; PostgreSQL reversal concurrency/append-only trigger tests passed; Python regression suite, frontend typecheck/production build, and AI/RAG dependency imports passed. Partial reversals, external provider contract reconciliation and production backup/restore remain open requirements.


## 2026-10-25 finance UI continuation — immutable ledger panel
- Added a separate `Immutable evidence ledger` control beside the existing commission ledger so the original finance UI remains intact.
- The panel reads `GET /api/finance/conversion-ledger`, displays read-only exact decimal strings and currency/evidence-separated totals, lists recent conversion/reversal observations, and visibly distinguishes signed-webhook evidence from legacy unverified and operator/API submitted observations.
- Includes empty and read-only states, accessible table headings and evidence status text. Browser accessibility and workspace-role end-to-end UAT remain pending; this increment's CI is pending on the next SHA.


## 2026-10-25 implementation update — blueprint v3 source parity gate
- Reviewed the attached Full Product/Engineering/Integration/Release Blueprint v3 and recorded its SHA-256 in docs/SOURCE_REGISTER.md.
- Vendored 53 upstream SKILL.md definitions, the upstream registry/evaluation set, source guidance/template and 12 shared references under knowledge/affiliate-skills/upstream/, pinned to Affitor/affiliate-skills commit f4cb063a0ee83b1b9e5167e396ab46cc9123dadc. The upstream README claim of 52 skills is explicitly surfaced; the registry and filesystem count is 53.
- Added a source-manifest verifier and an independent repo-guard workflow job. These verify pinned source blobs, registry/matrix coverage and status-ledger consistency; they do not promote partial skills to implemented.
- Current skill matrix remains 47 partial, 6 not implemented, 0 fully end-to-end complete. Latest previously verified baseline c7ee98e1... passed push/PR workflows, including PostgreSQL migration/reversal checks. The newly added guard/vendor changes need exact-SHA hosted workflow confirmation.
- P0 work still open: generate and commit a reproducible frontend lockfile; strengthen tenant/RBAC/security tests across all active endpoints and workers; add dependency/security scans and Playwright UAT; prove provider contracts, staging/deployment, backup/restore and operational budgets. The local package registry was not reachable for lockfile generation, so CI is not yet switched to npm ci.


## 2026-10-25 resumed checkpoint — deterministic frontend install and security gate
- Re-inspected the live branch before continuing: `build/omni-affiliate-os-production`, HEAD at `e6e6eb4e552b4887da252db0df172dd25ee79561`. No branch was created and `main` was not changed.
- The committed `frontend/package-lock.json` is npm lockfile v3 with 141 dependency packages and 141 resolved package entries. Its root dependency/devDependency declarations match `frontend/package.json`.
- On exact SHA `e6e6eb4e552b4887da252db0df172dd25ee79561`, push workflow [40213802242](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40213802242) and PR workflow [40213808545](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40213808545) both completed successfully. Verified successful jobs: Python/source tests and SQLite migrations; PostgreSQL 16 upgrade/downgrade/drift and conversion-reversal integration; AI/RAG dependency imports; repository/source-syntax and pinned 53-skill registry guard; frontend `npm ci`, TypeScript typecheck and Next.js production build. The push-only lockfile sync job also passed; the PR correctly skipped that write-capable job.
- Runtime skill parity remains 47 partial, 6 not implemented and 0 fully end-to-end complete out of 53 tracked skills. The 53-source inventory is not an overall product completion percentage.
- Added a dedicated `security-audit` workflow job for pip-audit across core/test and optional AI/RAG requirements, plus npm audit at the high-severity threshold. This scan is newly configured; its status is pending until the exact candidate's Actions run completes.
- Next P0 actions: remediate any audit findings, then expand endpoint/worker tenant/RBAC coverage, add secret scanning/SBOM and Playwright accessibility/viewport UAT, and verify backup/restore, provider contracts, staging and rollback. Product remains NOT RELEASE READY.


## 2026-10-25 dependency-audit remediation in progress
- The first exact-SHA security-audit run on `f129ecf4576f1d35229525669613ecebcf17d65b` failed on the core/test dependency graph, finding advisories against the resolved Pillow 12.3.0 and pytest 8.4.2 versions. The scanner listed Pillow 13.0.0 and pytest 9.0.3 as fixed versions. These were not ignored or allowlisted.
- Updated the declared ranges to require `Pillow>=13.0.0,<14.0` and `pytest>=9.0.3,<10.0`. This changes version constraints only; compatibility remains unverified until the Python regression suite, optional AI/RAG imports, PostgreSQL integration, and both dependency-audit profiles pass on the new SHA.
- npm-audit outcome was not reached in the failed core scan and must be reported from a run that gets to that step.


## 2026-10-25 dependency resolver compatibility correction
- After raising pytest to the scanner-listed fixed line `pytest>=9.0.3,<10.0`, the next `pip-audit` run could not resolve the graph because `requirements-dev.txt` still constrained `pytest-asyncio<1.0`. This is a resolver conflict, not evidence that the test suite itself passed or failed.
- Updated the plugin constraint to `pytest-asyncio>=1.3.0,<2.0`; upstream release notes state 1.3.0 added pytest 9 support. Compatibility and audit status remain pending the next exact-SHA full CI run.


## 2026-10-25 AI/RAG security audit — unpatched ChromaDB advisories
- The core/test `pip-audit -r requirements-dev.txt` graph passed after the Pillow/pytest/pytest-asyncio dependency updates. The optional AI/RAG graph then found fixable LangChain advisories and four ChromaDB 1.5.9 advisories for which no fixed PyPI version was available in the reviewed upstream records.
- Raised LangChain packages to compatible fixed/current 1.x lines and moved legacy `RetrievalQA` to the `langchain-classic` compatibility package. ChromaDB remains used through local persistent storage; no standalone Chroma service or Chroma HTTP client is configured.
- Added a static local-only guard and regression test; the AI dependency audit will except only the four exact, documented unpatched Chroma PYSEC IDs after the guard passes. This is a temporary mitigation, not a clean scan. The next exact-SHA run must pass all remaining dependency checks; npm audit outcome is still unverified.
- See `docs/SECURITY_EXCEPTIONS.md`. Production readiness remains NOT RELEASE READY until the Chroma exception can be removed/replaced, plus outstanding secret/SBOM, UAT, provider, deployment and restore gates.


## 2026-10-26 resume checkpoint — dependency audit repair
- Recovered from the latest live GitHub state; canonical repo is `AITECHPRODUCTS/Project1`, existing working branch is `build/omni-affiliate-os-production`, and the verified pre-repair HEAD is `565c76bd7d6931721ce66cb0a84fc25129997c52`. No new branch was created.
- Latest push run [40215636414](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40215636414) and pull-request run [40215641152](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40215641152) both passed repository guard/53-skill parity, Python tests, SQLite migration checks, PostgreSQL migration and concurrent conversion reversal tests, AI/RAG imports, frontend typecheck and production build.
- Both runs failed only at `security-audit` step `npm audit --audit-level=high`. The hosted log reports a high-severity PostCSS dependency path through Next.js (nested PostCSS 8.4.31) plus a moderate `postcss-selector-parser` finding; the reported total was five vulnerabilities. The Python core audit passed; the optional AI/RAG scan passed with its separately documented four-Chroma-advisory exception and local-only guard.
- Repair plan on this same branch: pin Next.js's transitive PostCSS to the already-resolved patched 8.5.31 line, raise the direct PostCSS range to >=8.5.23, and resolve `postcss-selector-parser` to the advisory-fixed 7.1.6 line. A one-shot, commit-message-gated workflow job regenerates the npm lockfile, requires `npm audit` to pass, and checks clean-install/typecheck/build before committing the lockfile to this branch only.
- Status remains NOT RELEASE READY until the resulting exact-SHA CI run passes and independent provider, security exception, browser UAT, deploy, backup/restore and operational gates are closed.


## 2026-10-26 frontend dependency audit repair — lock generated
- The temporary GitHub Actions repair job successfully regenerated and committed `frontend/package-lock.json` to the existing branch as commit [0180f2f0fd84445ff76131d4ca04389676043b8a](https://github.com/AITECHPRODUCTS/Project1/commit/0180f2f0fd84445ff76131d4ca04389676043b8a).
- The resulting lock records Next.js `16.4.3`, resolved PostCSS `8.5.31`, and `postcss-selector-parser` `7.1.6`. The guarded dependency-repair job's `npm audit`, clean `npm ci`, frontend typecheck, and production build all passed before it pushed that lockfile.
- The broad workflow on the earlier pre-lock commit is not counted as green: its parallel frontend job had started with a stale lockfile and failed `npm ci`. The GitHub Actions bot's lockfile commit did not provide a successful full-matrix run on the lockfile SHA; a PR run was marked `action_required`. The temporary repair job has therefore been removed, and a normal follow-up commit on this branch will trigger the complete matrix against the committed lockfile.
- CI/security result still to verify on the new exact SHA: standard frontend `npm ci`, `npm audit --audit-level=high`, full tests/migrations, Postgres integration, AI/RAG, and skill parity. The separate ChromaDB exception remains an explicit production-release blocker.


## 2026-10-26 verified full CI — dependency repair complete
- Exact candidate SHA: `668b33670ea11e30f97ccc3c6e50180124609207`.
- Push run: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264037056 (**success**).
- Pull-request run: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264040473 (**success**).
- Passed on the exact SHA: repository/source inventory and 53-skill parity; Python compile and full pytest suite; SQLite migration upgrade/downgrade/drift; PostgreSQL migration upgrade/downgrade/drift and concurrent conversion reversal; AI/RAG dependency import; frontend `npm ci`, TypeScript typecheck and Next.js production build; core/test and AI/RAG dependency audit; frontend `npm audit --audit-level=high`; and clean lockfile sync.
- The frontend dependency fix includes Next.js `16.4.3`, PostCSS `8.5.31`, and postcss-selector-parser `7.1.6`. The previous dependency-audit failure is resolved in this full matrix.
- Explicit outstanding security limitation: the four ChromaDB advisory IDs documented in `docs/SECURITY_EXCEPTIONS.md` are still temporary exceptions behind the local-only guard; this is not a clean AI/RAG scan or production release approval.
- Current next P0 hygiene action: migrate workflow actions off retired Node 20 releases, then rerun the complete matrix on the new exact SHA. Provider live authorization, SBOM/license/secret scans, browser UAT, deployment smoke and backup/restore remain separate release gates.


## 2026-10-26 P0 auth/tenant regression tests added
- Previous checkpoint SHA `70dd041a8c27607467f8605d1eabad09f815d2bf` has a fully successful push workflow: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264278741. The workflow now uses Node 24-capable first-party actions.
- Added `tests/test_auth_tenancy_guards.py` to pin three existing security contracts: a session whose workspace membership was revoked is invalidated (HTTP 403 and session cleared), a static bearer API token cannot be used for workspace-scoped access, and a workspace member cannot call workspace-admin authorization.
- Verified on exact SHA `e715878c76fb6f1876c2ff1769653fa72ad51396`; push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264570099 and PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264573970 both passed. They supplement—not replace—the broader route-by-route IDOR, WebSocket, exports and worker authorization tests in the release gate.
- Production remains blocked by the conditional ChromaDB audit exception and by external provider authorization, browser UAT, SBOM/license/secret scan, deployment smoke, and backup/restore evidence.


## 2026-10-26 WebSocket tenant-isolation remediation added
- The auth-guard regression test slice is verified on exact SHA `e715878c76fb6f1876c2ff1769653fa72ad51396`: push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264570099 completed successfully.
- Source audit found a P0 tenant data-isolation defect: `EventHub` delivered workflow/HITL events to every connected socket; workflow event payloads lacked workspace identifiers, and the WebSocket endpoint did not revalidate active workspace membership.
- Candidate remediation binds workflow event metadata to the workspace, routes events only to sockets subscribed to the same verified workspace, drops unscoped/legacy events, restores tenant metadata after paused-workflow recovery, and rechecks active membership before accepting WebSocket connections.
- Added `tests/test_websocket_tenant_isolation.py` for scoped delivery, scope-less event dropping, workflow event scope, and revoked-membership denial. Verified on exact SHA `65a5a884acf0195a2720cb6de76a5279fd4e5dde`: push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265255592 and PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265259440 both completed successfully. All seven push jobs passed.


## 2026-10-26 WebSocket tenant-isolation verified
- Exact candidate SHA: `65a5a884acf0195a2720cb6de76a5279fd4e5dde`.
- Push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265255592: **success**. PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265259440: **success**.
- Seven push jobs passed: Python suite including all four new WebSocket isolation tests; SQLite migration/drift; PostgreSQL migration/concurrency; AI/RAG imports; 53-skill repository guard; frontend `npm ci`, typecheck and production build; security audit; lockfile reproducibility.
- The WebSocket tenant isolation issue is addressed by this patch and test suite. This does not establish production readiness: the four ChromaDB advisory IDs remain a conditional exception; authorized live provider verification, broad route/worker/export/WebSocket UAT, SBOM/license/secret scans, deployment smoke and backup/restore remain.
- Next P0 candidate for code audit: verify that workflow run status/pause/resume/retry endpoints and background worker actions enforce actor + workspace ownership, not just session presence or a guessable run/session ID.


## 2026-10-26 workflow lifecycle ownership — verified
- Exact SHA: 16eee55a6935e9afa1d5f2b020c867713754aa67.
- Push CI: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265845238 — **success**. PR CI: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265848400 — **success**.
- Verified gates: all Python tests including new workflow authorization/ownership cases; SQLite migration/drift; PostgreSQL migration and concurrent reversal; AI/RAG imports; frontend clean install/typecheck/production build; repository source and 53-skill parity; core/AI-RAG/frontend security audits under the existing documented Chroma exception; and lockfile reproducibility.
- Changes include explicit workspace required at workflow start, workspace argument required for status/resume, owner-workspace checks on both the paused record and run, workspace-scoped recovery, and scoped /api/status plus /api/flywheel/status aggregates.
- Next P0 audit item: make shared knowledge-index ingestion platform-admin-only and minimize host filesystem disclosure in its status endpoint. This must be tested on the next exact SHA.


## 2026-10-26 shared knowledge-index admin boundary — verified
- Exact implementation SHA: `743e404e63b7c3a54423a18b1cf17af1338c5abf`.
- Push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40266330644 — **success**. PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40266336192 — **success**.
- All seven push jobs passed: Python suite including new knowledge-index authorization tests; SQLite migration/drift; PostgreSQL migration/concurrency; AI/RAG imports; 53-skill repository guard; frontend clean install/typecheck/production build; dependency audit; and lockfile reproducibility. The corresponding PR run also passed.
- Shared doctrine ingestion now requires the explicit Platform Super Admin permission, the UI hides the action from non-platform admins, and knowledge status no longer returns the server's absolute RAG storage path. The tests cover workspace-owner denial, platform-admin success, and path non-disclosure.
- Security boundary still outstanding: four explicitly documented ChromaDB advisories remain conditionally excepted by the embedded/local-only guard; this is not a clean optional-AI security scan or production approval.
- Next P0 review: tenant-scoping of resource-budget and self-learning summaries, including any scheduled/background calls that run without a request workspace context.


## 2026-10-26 resource-budget and performance-learning tenant boundary — candidate
- Resumed from verified head `a8cd236426a34ce8852b1e5ef4128e9c0199ca7b`; push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40266554499 and PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40266557903 both passed before this change.
- The resource-budget and self-learning service helpers could be invoked without an active workspace context. Because their models rely on ORM tenant filters driven by that context, an unscoped invocation could aggregate rows across tenants.
- Candidate changes now fail closed without an authorized workspace, explicitly scope budget reserve/finalize/status and self-learning queries, pass workspace identity from the API and scheduled learning job, and reject a requested workspace that conflicts with the active context.
- Added regression tests are intended to cover unscoped denial, cross-workspace aggregate isolation, self-learning isolation, and API denial when no authorized workspace is selected. This candidate remains **pending** until the exact-SHA push and PR CI runs are verified.


## 2026-10-26 resource-budget and self-learning tenant boundary — verified
- Exact SHA: `3322babb2865019e6a94bc5dc946cc700cd301f7`.
- Push CI: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40267076940 — **success**. PR CI: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40267081364 — **success**.
- All push jobs passed: Python suite with four new tests, migration/source checks, PostgreSQL migration and concurrent reversal, AI/RAG imports, 53-skill repository guard, frontend clean install/typecheck/build, security audit under the documented Chroma exception, and lockfile reproducibility.
- Budget reserve/finalize/status and self-learning now require a concrete authorized workspace, reject mismatched context, and scope all reads/writes. API and scheduled-learning callers provide workspace identity explicitly.
- Next P0 audit found three additional scheduled workers (campaign health, email delivery, payout threshold) were relying on implicit/global ORM context. The following commit scopes each tenant operation explicitly and adds worker regression tests; that change remains pending CI.


## 2026-10-26 campaign/conversion workspace binding — candidate
- Audit found campaign list/create/health and API-submitted conversion handlers relied on ambient workspace context instead of validating and passing the authenticated workspace explicitly.
- Candidate fix checks the selected workspace, scopes campaign reads/writes, includes workspace ID in conversion duplicate checks, and assigns the same workspace ID to both Conversion and ConversionLedgerEntry.
- Added `tests/test_campaign_conversion_workspace_routes.py` for no-workspace denial, cross-tenant campaign hiding/health denial and same provider event IDs being independent per workspace. Verified on exact SHA 4becae03e155fedc361e5b9fcdfc9fde66602f75; push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268073324 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268078547 both passed.


## 2026-10-26 campaign/conversion route test-fixture correction — pending re-verification
- The first hosted run for candidate `5cf7d3305b33e003fefaf4c1e56c25d8c0cc0834` exposed one regression in the pre-existing `tests/test_conversion_ledger.py::test_conversion_create_api_records_decimal_but_unverified_evidence`: it returned 403 because the test stubbed the DB session (including the development workspace lookup) but did not stub an authenticated workspace. The new handler's 403 was the intended fail-closed behavior; weakening the handler would be incorrect.
- Updated the pre-existing test to provide an explicit authorized workspace through `require_auth` and assert both Conversion and ConversionLedgerEntry carry that workspace ID.
- Fixture fix verified on exact SHA 4becae03e155fedc361e5b9fcdfc9fde66602f75: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268073324 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268078547 both passed the full required CI matrix.

## 2026-10-26 campaign/conversion workspace binding — verified
- Exact SHA: `4becae03e155fedc361e5b9fcdfc9fde66602f75`.
- Push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268073324 — **success**. PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268078547 — **success**.
- Both runs passed Python tests (including campaign/conversion route tests and the corrected conversion-ledger fixture), SQLite migrations/drift, PostgreSQL migrations/concurrency, AI/RAG imports, repository and 53-skill guard, frontend clean install/typecheck/build, security audit, and push lockfile sync.
- Campaign list/create/health requires an active workspace and isolates reads/writes. API-submitted conversion idempotency is scoped to `(workspace_id, network, external_event_id)`, and both Conversion and ConversionLedgerEntry receive the authenticated workspace ID. Cross-tenant campaign health returns not found; the same event ID can be independently recorded by different tenants.
- Production remains blocked by the documented four ChromaDB advisory exceptions and outstanding provider verification, broader endpoint/worker/export UAT, SBOM/license/secret scans, deployment smoke, and backup/restore.
- Next P0 audit: remaining tenant-owned endpoints, especially content assets, leads/email queue/worker controls, and public lead-capture token binding.


## 2026-10-26 blog and lead/email tenant boundary — verified
- Exact SHA: `929035b6429f4a1fa9a0c9c31cbc35834ab72dc9`.
- Push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40269971909 — **success**. PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40269976725 — **success**. All seven push jobs and all required PR jobs passed.
- Python tests, SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG import checks, frontend production build, security audit, repository/53-skill guard, and push lockfile reproducibility all passed.
- `/content/blog` now requires an authenticated active workspace and holds the explicit scope through generation and ContentAsset persistence. Private `/leads/capture` requires authentication and an active workspace. Public capture continues to validate the signed, expiring `lead_capture` workspace token before invoking lead creation.
- Lead lookup and scheduled-sequence idempotency include workspace identity; both Lead and ScheduledEmail rows are explicitly tenant-bound. Email delivery fails closed without workspace context and restricts both queued-message and lead reads to the same workspace.
- Six new regression tests cover cross-workspace subscriber isolation and sequence idempotency, no-workspace denial, blog asset ownership, private capture denial, public-token rejection and acceptance, and unscoped email helper denial.
- Next P0 audit: review remaining externally impactful routes, especially the social-publish endpoint, landing-page token issuance, and any direct publishing/provider writes. Production remains blocked by the four documented ChromaDB advisory exceptions and outstanding release/UAT gates.

## 2026-10-26 external-publishing and landing-token boundary — verified
- Base SHA: `31826a37d7494050457606c963aefba3421dceb9`. The base push [40270284075](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270284075) and PR [40270289947](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270289947) both passed; that SHA was documentation-only after the verified blog/lead/email change.
- Audit confirmed `/social/publish` can make live Reddit/Pinterest writes when `PUBLISHING_DRY_RUN=false`, yet had no direct auth/workspace guard. `/landing/page` issued a signed token from ambient context without an explicit authenticated workspace check. CMS credentials are global settings but CMS publish only used the workspace-admin role guard.
- Candidate gates social/CMS writes behind platform-super-admin and selected workspace; requires `confirm_live_publish=true` for live publication; creates workspace-scoped audit records for success/failure; and issues landing-page capture tokens only for an authenticated workspace.
- Six regression tests cover authentication, workspace-admin denial for global credentials, selected-workspace token issuance, live-confirmation gating and audit persistence. Exact-SHA push [40270795625](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270795625) and PR [40270800499](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270800499) both passed.


## 2026-10-26 external-publishing and landing-token boundary — verified
- Exact implementation SHA: `6f3994096e502911b23fb54e8cb94c3f2181a16d`.
- Push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270795625 — **success**. PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40270800499 — **success**. All seven push jobs and all required PR jobs passed.
- Python suite: **250 passed, 2 skipped**, one existing Starlette/httpx deprecation warning. SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG imports (9 imports), frontend typecheck/build, dependency security audit, 53-skill repository guard and push lockfile reproducibility all passed.
- `/social/publish` and `/cms/publish` now require explicit Platform Super Admin authorization and an active workspace because their provider credentials are global configuration. Live social/CMS publishing requires `confirm_live_publish=true`; CMS also keeps the existing `CMS_PUBLISH_EXECUTE` configuration gate. Success/failure provider results are recorded in workspace-scoped AuditLog events without storing post bodies or credentials.
- `/landing/page` now requires an authenticated user with an active workspace and generates the signed `lead_capture` token against that explicit workspace under `workspace_scope`.
- Six regression tests prove unauthenticated denial, workspace-admin denial for shared global provider credentials, missing-workspace token issuance denial, workspace-bound token issuance, explicit live-confirmation enforcement, and audit event persistence.
- Production remains **not release-ready**: the documented four ChromaDB advisory exceptions remain unresolved, as do remaining provider authorization verification, comprehensive external-side-effect UAT, SBOM/license/secret checks, deployment smoke and backup/restore evidence.
- Next P0 audit: workflow runner step implementations and remaining provider integration routes for external mutations, explicit approvals, idempotency, audit recording and dry-run behavior.

## 2026-10-26 workflow-stage side-effect boundary — verified
- Rechecked base SHA `ccbd4a821707f7d95b9a7cce3911dfa2735d3138`; checkpoint push [40271100102](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40271100102) and PR [40271104015](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40271104015) both passed.
- Audit found S5 invokes the publishing adapter directly, bypassing route-level live-publish confirmation and Platform Super Admin checks. S6 conversion import relied on ambient query scope and did not state workspace identity in its duplicate predicate/row construction.
- Candidate adds a typed workflow-start confirmation, server-derived authorization metadata, fail-closed S5 live-publish checks, per-tenant attempt/outcome audit events, and explicit S6 workspace filters and tenant-bound Conversion rows.
- Five new regression tests cover live workflow role/confirmation, spoofed metadata rejection, S5 audit persistence, workspace-specific S6 dedup, and missing-workspace rejection. Corrected implementation SHA `64a2d30af5dddb79150428936993ef1811b4419f`: push [40275131255](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275131255) and PR [40275135461](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275135461) both completed successfully. Python suite: **255 passed, 2 skipped**, one existing deprecation warning. SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG import profile (**9 imports**), frontend typecheck/production build, dependency security audit, 53-skill repository guard and push lockfile reproducibility all passed.
## CI correction follow-up — workflow side-effect candidate
- First candidate SHA `9dcc5f0c842eddaeca86c40ed13d2997c1eddebe` had a Python job failure in push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40274907786: 2 failed, 253 passed, 2 skipped. Failures were a test double expecting `workspace_id` before the runner added it, and a direct S5 unit test incorrectly prefilled spoofed authorization metadata that is explicitly overwritten by the API route.
- Correction: the API route now stamps the selected workspace into its server-controlled metadata before calling the runner; the direct S5 test now represents missing authorization and fails closed. The route test continues to verify client-forged authorization metadata is overwritten.
- Verification evidence: Corrected implementation SHA `64a2d30af5dddb79150428936993ef1811b4419f`: push [40275131255](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275131255) and PR [40275135461](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275135461) both completed successfully. Python suite: **255 passed, 2 skipped**, one existing deprecation warning. SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG import profile (**9 imports**), frontend typecheck/production build, dependency security audit, 53-skill repository guard and push lockfile reproducibility all passed.
## 2026-10-26 scheduled-email duplicate-send prevention — verified
- Source audit found that two worker instances can select the same due ScheduledEmail before either commits a status change, then both call Resend. This is an external side-effect race even though lead/queue queries are workspace-scoped.
- Candidate adds a nullable claim timestamp and Alembic revision 0008; worker claims use a conditional workspace/status-scoped UPDATE; interrupted claims younger than 23 hours are safely retried with a stable per-message Resend `Idempotency-Key`; claims older than the 24-hour provider idempotency window move to `delivery_unknown` for manual reconciliation instead of blind resend.
- Three new tests cover concurrent-worker single send, stale-lease recovery, stable provider idempotency, and quarantine after the safe retry window. Verified implementation SHA `fedd1f74dbaa33e210b0587c774bc2ad63d92b8d`: push [40276085004](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40276085004) and PR [40276090006](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40276090006) both succeeded. Python suite: **258 passed, 2 skipped**, one existing Starlette/httpx deprecation warning. SQLite upgrade/drift, PostgreSQL migration upgrade/downgrade/drift and concurrency, AI/RAG profile (**9 imports**), frontend typecheck/production build, dependency security audit, 53-skill guard and push lockfile reproducibility all passed.

## Email worker CI correction history
- Initial implementation SHA `7c1b6bab08924a077aa790cbf39130e5eece0aad` failed one of the new tests in push [40275990654](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275990654) and PR [40275995997](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40275995997): 257 passed, 2 skipped. The double-escaped unsubscribe regex caused `List-Unsubscribe` to use a generated fallback URL rather than the stored URL.
- Correction at `fedd1f74dbaa33e210b0587c774bc2ad63d92b8d` reuses the persisted unsubscribe target, keeping the provider payload stable across retries. Verified implementation SHA `fedd1f74dbaa33e210b0587c774bc2ad63d92b8d`: push [40276085004](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40276085004) and PR [40276090006](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40276090006) both succeeded. Python suite: **258 passed, 2 skipped**, one existing Starlette/httpx deprecation warning. SQLite upgrade/drift, PostgreSQL migration upgrade/downgrade/drift and concurrency, AI/RAG profile (**9 imports**), frontend typecheck/production build, dependency security audit, 53-skill guard and push lockfile reproducibility all passed.

## 2026-10-26 workflow external-side-effect retry guard — verified
- Source review found WorkflowRunner automatically retries `TimeoutError`/`ConnectionError` from any stage. S5 publishes externally; retrying a timed-out POST can duplicate an action if the provider accepted it but the response was lost.
- Candidate adds an explicit `side_effecting` marker to workflow steps, marks S5 as external-side-effecting, suppresses automatic transient retries for such stages, and writes a tenant-scoped `workflow.side_effect_outcome_unknown` audit event directing reconciliation before resubmission. Read-only stages retain configured retries.
- Two regression tests cover no-retry + durable unknown-outcome audit for S5 and preserve retries for a read-only transient failure. Exact-SHA CI pending.

- The runner marks S5 as side-effecting. If a timeout/connection error leaves provider outcome ambiguous, it fails the stage without automatic retry and persists a workspace-scoped `workflow.side_effect_outcome_unknown` event with manual-reconciliation required. Read-only stages retain transient retries.
- Two regression tests prove no retry + durable unknown-outcome audit for side-effecting stage failures and preserve configured retries for read-only stages. Verified implementation SHA `3dc01b9b954bf0ec392aafed522c4ec968faffa9`: push [40277040070](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40277040070) and PR [40277047842](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40277047842) both passed. Python suite: **260 passed, 2 skipped**, one existing Starlette/httpx deprecation warning. SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG profile (**9 imports**), frontend typecheck/production build, dependency security audit, 53-skill guard and push lockfile reproducibility all passed.

## 2026-10-26 manual provider-write idempotency — verified
- Implementation SHA: `1cc839bbf80d1a66e35b9e36f244b4fa13cb68af`.
- Push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40278503530 — **success**. PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40278508177 — **success**. All seven push jobs and all required PR jobs passed.
- Python suite: **264 passed, 2 skipped**, one existing Starlette/httpx deprecation warning. SQLite migration/drift and PostgreSQL migration/concurrency, AI/RAG import profile (**9 imports**), frontend typecheck/production build, dependency security audit, 53-skill repository guard and push lockfile reproducibility passed.
- Added migration `0009_external_action_idempotency` and tenant-scoped `ExternalAction` registry. Live social publishing and every CMS write require a valid `Idempotency-Key`; the route commits a claim before contacting the provider, hashes the normalized request, replays a completed response for identical key/payload, returns 409 for changed payload or in-progress/unknown outcome, and blocks alternate-key retries for the same unresolved request hash. Network/timeouts and HTTP 5xx outcomes become `unknown` rather than being blindly retried.
- Four new tests cover social replay/no duplicate, required keys, CMS draft replay, and unknown-outcome protection. The first candidate run had one test-fixture failure because an older social confirmation test omitted the mandatory key (1 failed, 263 passed, 2 skipped); production correctly returned 428. The fixture was corrected at `1cc839bb...`, and both exact-SHA workflows passed without weakening the endpoint.
- Next P0: S5 workflow distribution currently calls `social_media_scheduler` directly, bypassing the route's durable `ExternalAction` claim/replay registry. Extend the same registry semantics to workflow-driven live publishing and add regressions for duplicate workflow submission/manual retry, preserving fail-closed authorization and the unknown-outcome/no-blind-retry policy.



## CI correction follow-up — provider-write idempotency
- Initial implementation SHA `b3495a58202f944621f43063efbe9d293323ee24` exposed a stale social-publish regression fixture: it tested the newly confirmed live request without the now-required `Idempotency-Key`. PR run [40278241892](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40278241892) Python suite reported **1 failed, 263 passed, 2 skipped**. The failing test expected 200 but correctly received 428 Precondition Required.
- The route's 428 is the intended contract; the regression fixture is being corrected to supply a valid key. No production auth/idempotency guard is weakened. Full push and PR CI for the correction remain pending.




## P0 — workflow S5 external-action registry integration — candidate
- Base SHA `06f185a16f364ce297dc194df01c34b33b28caa8` includes verified direct social/CMS idempotency and passing push [40278503530](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40278503530) / PR [40278508177](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40278508177). Docs checkpoint verification is in progress at [40278868656](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40278868656) and [40278873241](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40278873241).
- Source audit found S5 calls `social_media_scheduler` directly and bypasses the direct-route `ExternalAction` registry. Automatic runner retry suppression does not cover a workflow restarted by its caller.
- Candidate extracts claim/finish/fingerprint helpers into `backend/services/external_action_registry.py`, derives a stable per-item key from a workflow-level `Idempotency-Key`, replays completed results without a second provider call, and records failed/unknown outcomes in the shared tenant-scoped registry. Live workflow publishing without a valid key is denied at both API and S5 service boundaries.
- New regressions cover missing-key denial, completed S5 replay/no duplicate, and unknown-outcome rejection for same/alternate keys. Exact-SHA CI pending.


## P0 — workflow S5 external-action registry integration — verified
- Implementation SHA: `e7ca02df933c3028489e8c3ba1abbfba3d82ae90`.
- Push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279412060 — **success**. PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279416167 — **success**. All seven push jobs and all required PR jobs passed.
- Python suite: **267 passed, 2 skipped**, one existing Starlette/httpx deprecation warning. SQLite migration/drift and PostgreSQL migration/concurrency, AI/RAG import profile (**9 imports**), frontend typecheck/production build, dependency security audit, 53-skill repository guard and push lockfile reproducibility all passed.
- The provider-write claim/hash/replay helpers are now shared in `backend/services/external_action_registry.py`. Live workflow publishing requires a valid `Idempotency-Key` at the API and S5 service boundaries, in addition to Platform Super Admin authorization and explicit confirmation. Each S5 item derives a stable per-item idempotency key. Completed actions replay the stored response without a second provider call; key/payload conflicts and in-progress/unknown actions fail closed; timeouts/network/5xx outcomes remain `unknown` for reconciliation.
- Three new S5 regressions prove missing-key denial, completed-result replay without duplicate provider execution, and same/alternate-key rejection after an ambiguous provider outcome. Existing route regression now checks the mandatory workflow Idempotency-Key.
- Next P0 source audit: review the remaining provider adapters and externally impactful workflow/worker paths for approval gates, idempotency, tenant-scoped audit outcomes, and safe retry semantics. Production remains **not release-ready** while the four documented ChromaDB advisories and remaining provider/UAT/SBOM/license/secret/deployment/backup gates are open.



## P0 — global offer catalog sync authorization — candidate
- Source audit at `c29150409170cae8548bbe66c8dc7f2534fdc72b` found `/api/offers/sync` performs an upstream OpenAffiliate request and inserts/updates the shared global `Offer` catalog while requiring only ordinary authentication.
- Candidate requires Platform Super Admin and an active audit workspace; records provider sync success/failure and count metadata in the workspace audit log without storing credentials or offer payloads. Shared Offer rows remain global as defined by the model.
- Four regression tests cover workspace-member denial before provider invocation, no-workspace denial, successful sync/global catalog update with audit, and provider-failure audit/502 response. Exact-SHA CI pending.


## P0 — global offer catalog sync authorization — verified
- Implementation SHA: `498c0b595a8dd158b06eae2924f87d3897a8525b`.
- Push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279967742 — **success**. PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40279972611 — **success**. All seven push jobs and all required PR jobs passed.
- Python suite: **271 passed, 2 skipped**, one existing Starlette/httpx deprecation warning. SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG import profile, frontend typecheck/production build, dependency security audit, 53-skill repository guard, and push lockfile reproducibility passed.
- `/api/offers/sync` now requires explicit Platform Super Admin authorization and an active workspace. This is deliberately a platform-level operation because `Offer` is the shared global catalog, not a tenant-owned model. Non-admin/no-workspace callers are denied before calling OpenAffiliate.
- Success and failure paths write workspace-scoped `offers.sync` AuditLog metadata including provider, error type or created/updated counts, requested limit, and whether a query was supplied; full provider payloads and credentials are not logged. Four regression tests cover member denial, no-workspace denial, successful catalog refresh plus audit, and provider failure audit/502.
- Next P0 audit: inspect global provider/catalog configuration operations and other integration routes for appropriate role boundaries, audit trails, request limits, and safe failure behavior. Production remains **not release-ready** due to the four documented ChromaDB advisories and remaining provider/UAT/SBOM/license/secret/deployment/backup gates.

## P0 — OpenAffiliate outbound URL safety — verified
- Implementation SHA: `49043acd6e71841c7d365a97a9d8ca31168cc8da`.
- Push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40280504806 — **success**. PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40280508646 — **success**. All seven push jobs and all required PR jobs passed.
- Python suite: **273 passed, 2 skipped**, one existing Starlette/httpx deprecation warning. SQLite migration/drift and PostgreSQL migration/concurrency, AI/RAG import profile, frontend typecheck/production build, dependency security audit, 53-skill repository guard and push lockfile reproducibility all passed.
- `OpenAffiliateClient._get` now calls the existing `validate_public_http_url` before opening an HTTP client on cache misses. This rejects private, loopback, link-local, multicast and reserved destinations, while preserving `follow_redirects=False`, response byte caps, JSON validation and the existing TTL cache.
- Two regressions prove a loopback/private base URL is rejected before HTTP client construction, and valid-provider requests use the validated URL with redirects disabled.
- Next P0 audit: review remaining API routes and provider-configuration surfaces for public-read leaks, unsafe network destinations, global write authorization, and shared catalog/tenant boundaries. Production remains **not release-ready** because the four documented ChromaDB advisories and remaining provider/UAT/SBOM/license/secret/deployment/backup gates remain unresolved.




## P0 — shared IMAP commission import authorization — verified
- Source audit at `11aa932e469b33d299b09a3dca5e5dfe56b1c821` found `/api/finance/email-import` uses global deployment-level IMAP credentials and an allowlist but only required workspace-admin permission. A workspace admin could trigger reads of the shared mailbox and import matching evidence into their selected tenant.
- Candidate replaces workspace-admin authorization with Platform Super Admin, requires a selected workspace for accountability, and records success/failure audit metadata under that operator workspace without storing message bodies, subjects or credentials.
- Four regressions cover workspace-admin denial before mailbox import, platform-admin-without-workspace denial, successful import/audit, and provider failure audit/502. Verified on exact SHA `0ea1735648ce408fb831abc51179544facd3ed69`. Push [40281363532](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40281363532) and PR [40281370173](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40281370173) both passed. Python suite: **277 passed, 2 skipped, 1 existing Starlette/httpx deprecation warning**. SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG import profile, frontend typecheck/production build, dependency audit, 53-skill repository guard, and push lockfile sync passed.


## 2026-10-26 shared IMAP commission import — verified
- `/api/finance/email-import` requires Platform Super Admin and a selected workspace because the IMAP mailbox credentials and sender allowlist are global configuration. Workspace admins cannot trigger a shared mailbox read.
- Success/failure metadata is audited to the selected workspace. Audit values contain provider/mailbox, matched/created counts or error type only; message bodies, subjects, credentials and raw mailbox responses are not added to the audit record.
- Verified on exact SHA `0ea1735648ce408fb831abc51179544facd3ed69`. Push [40281363532](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40281363532) and PR [40281370173](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40281370173) both passed. Python suite: **277 passed, 2 skipped, 1 existing Starlette/httpx deprecation warning**. SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG import profile, frontend typecheck/production build, dependency audit, 53-skill repository guard, and push lockfile sync passed.
- Next P0: inspect remaining global provider/configuration and integration routes for authorization-role correctness, tenant ownership, audit outcomes, rate limits and safe network access. Release remains blocked by the four documented ChromaDB advisories and outstanding provider/UAT/SBOM/license/secret/deployment/backup gates.


## 2026-10-26 global provider readiness/capability confidentiality — verified
- The shared IMAP authorization fix is verified on `0ea1735648ce408fb831abc51179544facd3ed69` (push [40281363532](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40281363532), PR [40281370173](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40281370173); Python 277 passed/2 skipped).
- New audit finding: unauthenticated `GET /api/integrations` and `GET /api/capabilities` disclose deployment-wide provider/model/email/CMS/social readiness and missing environment-variable names. The existing builders do not appear to serialize raw credential values, but the configuration inventory itself is global sensitive operational metadata.
- Candidate gates both summaries behind Platform Super Admin plus selected workspace. The output schema/readiness classification is unchanged; no provider network request is added.
- Regression tests cover authentication denial, workspace-admin denial, platform-admin-without-workspace denial, and response redaction. Verified on exact SHA `a0bb0ff23f86b29e7e4a9072d2109e77d0328d40`. Push [40282793722](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40282793722) and PR [40282799345](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40282799345) both passed. Python suite: **281 passed, 2 skipped, 1 existing Starlette/httpx deprecation warning**. SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG import profile, frontend typecheck/production build, security audit, 53-skill repository guard and push lockfile sync passed.


## 2026-10-26 global provider readiness/capability confidentiality — verified
- Both `/api/integrations` and `/api/capabilities` now require Platform Super Admin and a selected workspace. Existing status classification and response shape are unchanged; no live provider request is performed.
- Four tests pass: unauthenticated denial, workspace-admin denial before builders run, admin-without-workspace denial, and authorized status response proving configured sentinel provider/model/social credentials are not serialized.
- Verified on exact SHA `a0bb0ff23f86b29e7e4a9072d2109e77d0328d40`. Push [40282793722](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40282793722) and PR [40282799345](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40282799345) both passed. Python suite: **281 passed, 2 skipped, 1 existing Starlette/httpx deprecation warning**. SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG import profile, frontend typecheck/production build, security audit, 53-skill repository guard and push lockfile sync passed.
- Next P0 source audit: rate-limit and abuse controls on unauthenticated public routes that invoke computation or create tracking/lead records, especially public tracking, content-draft generation and public lead-capture. Review existing edge/API limits first before adding duplicate infrastructure. Release remains blocked by the four ChromaDB advisory exceptions and external-provider/UAT/SBOM/license/secret/deploy/restore gates.

## 2026-10-26 public-route abuse controls and generation authorization — verified
- Last verified baseline SHA: `96402915bc857035a859e068810f5d23f58ecca7`; push [40283105487](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40283105487) and PR [40283111955](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40283111955) both passed.
- Audit found the current 20-per-hour public rate limit used an in-process dictionary only, allowing multiple workers/replicas to multiply the effective quota. Public lead-capture also parsed arbitrarily large bodies before validating the signed workspace token.
- The social-post, TikTok script, offer, value-ladder and video-render endpoints invoked LLM/provider/local-render work without a route-level authenticated workspace. Keyword clustering allowed unbounded list size despite an O(n²) comparison loop. The stateless tracking parser accepted an unbounded string.
- Candidate uses Redis atomic fixed-window quotas in production and fails closed with 503 when distributed rate limiting is unavailable; only development/test uses the in-process fallback. It adds per-IP and per-workspace generation limits, stricter video-render quotas, authentication/workspace scoping for expensive generation, a 500-keyword/size bound, a 32 KiB public lead request cap, and an 8,192-character tracking input cap.
- Eight regression tests and exact-SHA push/PR CI are verified. Verified on exact SHA `e3fb2fd8e159bae71f84fdd1bb3c4df50bc9d96a`: push [40283974722](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40283974722) and PR [40283978789](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40283978789) both completed successfully. Python suite: **289 passed, 2 skipped, 1 existing Starlette/httpx deprecation warning**. SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG imports, frontend typecheck/production build, dependency security audit, 53-skill repository guard and push lockfile sync passed. Production readiness remains blocked by the documented ChromaDB advisories and remaining external-provider/UAT/SBOM/license/secret/deploy/backup gates.


## 2026-10-26 public-route abuse controls — verified
- Public registration/login/lead-capture quota now uses Redis atomic fixed windows in production. A Redis outage yields HTTP 503 (fail closed) rather than silently using process-local rate limits; development/test keeps the local in-memory implementation.
- Authenticated workspace and per-IP/per-workspace quotas now protect LLM-backed social/TikTok drafts, offer and value-ladder generation, keyword clustering and video rendering. Video has stricter limits. Public lead capture rejects bodies over 32 KiB, keyword clustering is capped at 500 inputs of at most 500 characters each, and stateless tracking input is capped at 8,192 characters.
- Verified on exact SHA `e3fb2fd8e159bae71f84fdd1bb3c4df50bc9d96a`: push [40283974722](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40283974722) and PR [40283978789](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40283978789) both completed successfully. Python suite: **289 passed, 2 skipped, 1 existing Starlette/httpx deprecation warning**. SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG imports, frontend typecheck/production build, dependency security audit, 53-skill repository guard and push lockfile sync passed.
- Next P0: audit public outbound URL fetch/proxy and video asset handling for request/body/duration/redirect caps and abuse resistance, plus confirm if trusted-proxy configuration is documented. Remaining release blockers: four ChromaDB advisory exceptions; live provider authorizations/UAT; SBOM/license/secret scans; deployment smoke and backup/restore evidence.


## 2026-10-26 public outbound-fetch/video hardening — candidate
- Verified base SHA: `bba6b736b43a525f41723fef84dd72cb2a77e6f2`; push [40284327947](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40284327947) and PR [40284335127](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40284335127) both passed.
- Candidate fixes DNS rebinding by pinning each validated public request to a resolved public IP while retaining the original Host/TLS SNI, disables ambient proxy settings and redirects, bounds total time and response bytes, and reuses the boundary in research fetches, configured OpenAffiliate requests, campaign health probes and Pexels downloads.
- Pexels assets require supported media types, a 150 MiB download limit and 180-second duration cap; rendered output is capped at 500 MiB. Competitor URL research becomes authenticated/workspace-bound and uses the existing distributed per-IP/workspace quota; each URL is length-bounded.
- Verified on exact SHA `f2d232f7ce5efaea2e3d1abca8a6ba7e47cf339c`: push [40288412469](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40288412469) and PR [40288420524](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40288420524) both passed. Deployment documentation records trusted-proxy assumptions; actual production ingress configuration still requires staging verification.



## 2026-10-26 public outbound-fetch and video safety — verified
- Exact implementation SHA: `f2d232f7ce5efaea2e3d1abca8a6ba7e47cf339c`.
- Push CI: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40288412469 — **success**. PR CI: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40288420524 — **success**. Both were run against the same implementation SHA.
- Full push matrix passed: Python suite **301 passed, 2 skipped** (one existing Starlette/httpx TestClient deprecation warning); SQLite migration upgrade/downgrade/drift; PostgreSQL migration upgrade/downgrade/drift and concurrent conversion reversals; AI/RAG profile **9 imports passed**; repository source checks and 53-skill parity; frontend `npm ci`, TypeScript typecheck and production Next.js build; core/AI-RAG/frontend dependency audits; and push lockfile-sync/reproducible install/build.
- The shared public HTTP fetch boundary now checks all DNS answers for public routability, resolves the target once per request and connects to the vetted IP while preserving the original Host header and HTTPS SNI, disables ambient proxy-environment use and redirects, wraps the whole streamed request in a timeout, checks declared and streamed response sizes, and rejects unsupported content types.
- The same pinned transport now backs public HTML research fetches, operator-configured OpenAffiliate requests, and campaign destination-health probes, closing the prior check-then-resolve DNS-rebinding gap at those call sites.
- Pexels search responses are JSON/type and 2 MiB bounded; media downloads require accepted video media types, block redirects/encoded response bodies, enforce declared and streamed 150 MiB limits and verify Content-Length where supplied. Source B-roll and narration are capped at 180 seconds; outputs must remain below the configured video directory and encoded output is capped at 500 MiB.
- `/research/competitors` now requires authentication and an active workspace, enforces payload limits and the existing distributed per-IP/workspace quota, and each URL is limited to 2,048 characters.
- Regression tests cover mixed public/private DNS, pinned IP + Host/SNI + proxy/redirect behavior, redirects, declared and streamed byte limits, MIME rejection, Pexels response caps and cleanup, duration bounds, and competitor endpoint authentication/workspace/quota/input caps.
- Settings.forwarded_allow_ips and Compose FORWARDED_ALLOW_IPS are implemented, validate exact IP/CIDR values, and default to loopback-only trust. CI exercises Uvicorn's actual ProxyHeadersMiddleware; actual deployed ingress stripping/replacement and spoofed-header/client-IP behavior remain an external staging gate. Never use wildcard trust.
- Production is still **not certified live**: the four documented ChromaDB upstream advisory IDs remain temporary security exceptions, and authorized live-provider UAT, SBOM/license/secret evidence, hosted staging/deployment smoke, monitoring/SLO proof and backup/restore evidence remain open release gates.
- Next P0: verify the actual deployment/ingress profile and add isolated integration tests around pinned-IP request behavior against local controlled transports; review remaining provider SDK/direct HTTP calls to ensure they use the shared fetch boundary where they accept untrusted URLs.


## 2026-10-26 CMS configured-host DNS pinning — candidate
- Starting checkpoint `910ab73fe7a0cef8fcd507fda27e30a7b3e85598` passed push [40288954753](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40288954753) and PR [40288959578](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40288959578).
- Follow-up source audit found `cms_publisher.py` still validated `WORDPRESS_SITE_URL`/`GHOST_SITE_URL` and then sent credentialed POST requests using a separate HTTP client, leaving a DNS-rebinding window for global CMS credentials.
- Candidate extends the shared pinned public HTTP transport to support fixed CMS POST operations with JSON bodies, preserves original Host/SNI, disables redirects and proxy environment use, and caps CMS responses at 2 MiB. The existing `CMS_PUBLISH_EXECUTE` live-publish gate remains unchanged.
- Four regression tests cover WordPress and Ghost request routing/credentials, no-follow redirect behavior, and oversized response rejection. Verified on exact SHA `13ec393d0897c4ba75ed83ba6bed8ce8690f7c06`: push [40290026088](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290026088) and PR [40290033400](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290033400) both passed.

## 2026-10-26 CMS transport candidate — initial test-fixture failures and correction
- Candidate implementation commit `186d149be9f99707095a1515db14ce26211db0eb` failed the Python test step: four CMS tests hit a `NameError` in the fake response fixture, and one pinned-request test fake client did not accept the new `json` keyword. Result was **5 failed, 300 passed, 2 skipped**. These were test-double incompatibilities; the trace did not indicate a failing security assertion against the production implementation.
- Corrected the fake CMS response to initialize attributes in `__init__`, and updated the fake HTTP client's `build_request` signature to accept/pass `json`. The correction is verified on exact SHA `13ec393d0897c4ba75ed83ba6bed8ce8690f7c06`: push [40290026088](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290026088) and PR [40290033400](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290033400) both passed.


## 2026-10-26 CMS configured-host transport — verified
- Exact SHA: `13ec393d0897c4ba75ed83ba6bed8ce8690f7c06`.
- Push CI https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290026088 — **success**. PR CI https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290033400 — **success**.
- Full push and PR matrix passed: Python suite **305 passed, 2 skipped** (one existing Starlette/httpx TestClient deprecation warning); SQLite migration/drift; PostgreSQL migration/concurrency; AI/RAG imports; frontend typecheck/production build; core, AI/RAG and frontend dependency audits; 53-skill repository guard; and push lockfile-sync/reproducible install/build.
- The shared pinned transport supports GET/HEAD plus the controlled CMS JSON POST use case. WordPress and Ghost requests resolve the configured public endpoint once per request, pin the socket to the vetted public IP, preserve Host/TLS SNI, disable environment proxy usage and redirects, and enforce a total timeout plus a 2 MiB response cap.
- Four CMS tests passed: WordPress and Ghost request routing/credentials, refusal to follow a CMS redirect, and oversized response rejection. The first run had five test-double incompatibilities (four local-variable NameErrors and one fake client's missing `json` argument); fixtures were corrected without weakening production assertions.
- `CMS_PUBLISH_EXECUTE` remains required for live publication. Four documented ChromaDB advisory exceptions, trusted-proxy staging verification, provider live-authorization/UAT, SBOM/license/secret scans, hosted deployment smoke and backup/restore remain open release blockers.
- Next P0: audit remaining direct HTTP integrations and validate the trusted-proxy deployment profile in staging.


## 2026-10-26 fixed credentialed provider HTTP transport — verified
- Base checkpoint `e79b4bad6f067e537306fc6aff4c0b94629cf847` was verified green by push [40290480101](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290480101) and PR [40290486273](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40290486273).
- Source audit found remaining bare HTTPX clients at fixed credentialed provider endpoints for Resend delivery, Reddit OAuth/search, X trend search, Pinterest/Reddit publishing and Meta campaign pause. URLs were fixed official-provider endpoints, not user-supplied targets, but they bypassed shared DNS-pinned connection, no-proxy and no-redirect behavior.
- The change adds bounded `request_public_json` on the shared pinned transport, including form-encoded POST support; migrates those endpoints while preserving Resend stable `Idempotency-Key` and tenant-safe atomic claim/retry, social `PUBLISHING_DRY_RUN`, and Meta `AD_AUTOMATION_EXECUTE`. Meta campaign IDs are validated before path interpolation.
- Three new provider contract tests cover Reddit/X response transformation, Pinterest/Reddit publishing and dry-run, Meta execute gate/path validation. Existing Resend concurrency/stale-retry tests now mock the helper while asserting the same idempotency key and stable unsubscribe header. Verified: push [40292024351](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40292024351) and PR [40292030798](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40292030798) passed; the later clean exact-HEAD push [40292982126](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40292982126) and PR [40292990297](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40292990297) passed again.


## 2026-10-26 fixed credentialed provider HTTP transport — verified
- Implementation commit: `15edaf7ea7103150295098754ae8a64166120e3d`; subsequent current HEAD `868fbbc25d3d8dde5e5d772e1abeec9b3a4a16a4` includes the change.
- Push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40292024351 and PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40292030798 passed; the later exact-HEAD push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40292982126 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40292990297 also passed all required jobs.
- Resend, Reddit OAuth/search, X trend search, Pinterest/Reddit publishing and Meta campaign pause use the shared pinned `request_public_json` helper. Response semantics, Resend stable idempotency, workspace-scoped email claim/retry, `PUBLISHING_DRY_RUN`, and `AD_AUTOMATION_EXECUTE` were retained; Meta campaign IDs are validated before URL path interpolation.
- New provider contract tests assert request method, endpoint, headers/body, response adaptation, dry-run and execution-gate behavior. The separate trusted-proxy ingress check remains a staging release gate.

## 2026-10-26 final generic affiliate-adapter transport — verified
- The 59-file backend/AI Python source scan found one remaining standalone HTTP client outside `backend/services/url_safety.py`: `ConfiguredJSONAdapter.fetch_offers` validated its configurable endpoint and then opened an unpinned `httpx.AsyncClient`, creating a DNS-rebinding gap.
- Candidate replaces that request with the shared pinned `request_public_json` boundary and a 2 MiB response cap, and updates adapter tests to use the real loopback rejection path plus a mocked pinned helper contract.
- The current base SHA `868fbbc25d3d8dde5e5d772e1abeec9b3a4a16a4` passed both push [40292982126](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40292982126) and PR [40292990297](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40292990297). Verified: Exact SHA `aa3a0e175c09df3572f077b1c76d565ec2776207`: push [40301426819](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40301426819) and PR [40301436060](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40301436060) both passed. Python: **321 passed, 2 skipped, 1 warning**; PostgreSQL migration/concurrency, AI/RAG imports (**9**), frontend production build, dependency security audits, 53-skill repo guard and push lockfile reproducibility passed.


## 2026-10-26 final generic affiliate adapter pinned transport — verified
- Source scan covered 59 Python modules under `backend/` and `ai_memory/`. Before this patch, the only standalone client outside `backend/services/url_safety.py` was `ConfiguredJSONAdapter.fetch_offers`, which validated DNS then opened a separate HTTP client.
- The adapter now uses `request_public_json`, the central DNS-pinned request boundary, with a 2 MiB response cap. It preserves HTTPS-only endpoints, query/limit normalization, bearer auth and configured item-path extraction.
- Regression tests prove loopback rejection through the real helper and assert the pinned request method, query, auth header, size cap, item normalization and limit clamp.
- Exact SHA `aa3a0e175c09df3572f077b1c76d565ec2776207`: push [40301426819](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40301426819) and PR [40301436060](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40301436060) both passed. Python: **321 passed, 2 skipped, 1 warning**; PostgreSQL migration/concurrency, AI/RAG imports (**9**), frontend production build, dependency security audits, 53-skill repo guard and push lockfile reproducibility passed.
- The four ChromaDB advisory exception IDs remain unresolved. Actual trusted-proxy ingress validation, authorized provider live UAT, SBOM/license/secret scans, deployment smoke and backup/restore remain open. The updated runbook records required staging checks; this session did not claim a staging result.


## 2026-10-26 ChromaDB dependency removal — candidate
- Base checkpoint `38a7b0ff6399d4702f8e8f798cdee81567a5c45d` passed push [40302088167](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40302088167) and PR [40302094178](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40302094178).
- Candidate replaces the Chroma-backed RAG index with `ai_memory/local_vector_store.py`: SQLite persistence, normalized float32 embeddings, JSON source metadata, stable IDs/upserts, collection/model identity checks and in-process cosine ranking. The legacy `CHROMA_PERSIST_DIR` configuration remains for compatibility but now stores `local_vectors.sqlite3`.
- Removes both vulnerable-package references from the active AI requirements, removes all four conditional audit ignores, updates the AI import check, and adds five deterministic vector persistence/ranking/isolation tests plus a static no-Chroma guard.
- **Verified:** exact-SHA push [40304270245](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304270245) and PR [40304278972](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304278972) both passed; the push run passed all seven jobs, including the unignored AI audit and all 10 AI/RAG imports. Existing Chroma index files are not auto-migrated; run `python -m ai_memory.ingester` to rebuild after deployment. No production-readiness claim is made.


## 2026-10-26 Chroma removal candidate — first hosted verification result
- Candidate SHA `6a24ed5e73181bc190e6da391e6b4df040ebb49c`: push [40303851568](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40303851568) and PR [40303859476](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40303859476) failed only at `Verify AI/RAG dependency imports`. The error was `ModuleNotFoundError: No module named 'ai_memory'` because `python scripts/verify_ai_profile.py` puts `scripts/` rather than the repository root on `sys.path`.
- All other jobs passed on both runs: core suite (**326 passed, 2 skipped**), PostgreSQL migration/concurrency, frontend production build, repository guard, clean unignored AI dependency audit, and push lockfile sync.
- Corrected the verifier to add the repository root before importing the local vector store. Full push/PR CI on the next exact SHA is pending; do not call Chroma removal verified until the AI profile and every other required job pass.


## 2026-10-26 ChromaDB replacement — verified CI, rollout still required
- Exact verified SHA: `3ba90e4cb2fcb72494c0fda71e1d535398229c22`.
- Push CI: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304270245 — **success**. PR CI: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304278972 — **success**.
- All seven push jobs passed: Python tests and SQLite migration/drift, PostgreSQL migration/concurrency, local SQLite vector-store security guard, unignored `pip-audit -r requirements-ai.txt`, all 10 AI/RAG imports, 53-skill repository guard, frontend clean install/typecheck/production build, frontend audit and reproducible lockfile check.
- The first implementation SHA `6a24ed5e73181bc190e6da391e6b4df040ebb49c` failed only because `scripts/verify_ai_profile.py` ran with `scripts/` but not repository root on Python's import path. The corrected verifier at `3ba90e4` explicitly includes the root; both exact-SHA workflows are now green.
- The four historical ChromaDB advisories are no longer in the installed AI dependency graph; the new AI audit passed without ignores. Retain the historical exception record as provenance, not as a current package exception.
- Important rollout limitation: existing Chroma index files are not automatically migrated. Back up and preserve the previous index, run `python -m ai_memory.ingester` with the approved knowledge source, validate expected files/document counts and retrieval quality, then switch production only after staging checks. Provider live UAT, SBOM/license/secret scans, deployment smoke, backup/restore and trusted-proxy ingress evidence remain separate production gates.


## 2026-10-26 durable workflow lease/recovery — candidate
- Previous software-security checkpoint `3ba90e4cb2fcb72494c0fda71e1d535398229c22` passed full push [40304270245](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304270245) and PR [40304278972](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304278972). Documentation evidence was committed at `83d6b7b975b48b9cfb3733b6b93f19ea6c259cc2`; that docs-only run is still in flight as this candidate is prepared.
- Source audit found WorkflowRun checkpoints persisted in PostgreSQL but active work launched via process-local `asyncio.create_task`, with startup recovery limited to paused sessions. A process restart could strand queued/running work, and multiple workers had no lease/heartbeat ownership.
- Candidate adds lease owner, expiry, heartbeat and attempt count to WorkflowRun; migration `0010_durable_workflow_leases`; skip-locked PostgreSQL claims; a recovery loop for expired queued/running leases; and paused-session lease recovery. Read-only stages resume from the persisted current-step checkpoint. A stale live S5 publication stage is marked unknown/failed and emits an audit event rather than being replayed automatically.
- Added four SQLite recovery/lease tests and a dedicated PostgreSQL concurrent-claim test wired into the integration workflow. Verified on exact SHA `03d967e97b1993b80f853cc2fec72cf9e6b5f392`; push [40306591424](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40306591424) and PR [40306596350](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40306596350) both passed, including the migration/drift and PostgreSQL concurrency gates.
- Boundaries still needing follow-up: HITL response payloads intentionally stay in memory and therefore must be re-submitted if the process dies after a resume request; multi-replica resume routing is not yet proven. This queue/lease addition is an incremental durability improvement, not full production certification.


## 2026-10-26 durable workflow leases/recovery — verified CI
- Exact implementation SHA: `03d967e97b1993b80f853cc2fec72cf9e6b5f392`.
- Push workflow https://github.com/AITECHPRODUCTS/Project1/actions/runs/40306591424 — **success**, all seven jobs passed. PR workflow https://github.com/AITECHPRODUCTS/Project1/actions/runs/40306596350 — **success**, all required jobs passed.
- Python: **330 passed, 3 skipped, 1 warning**. The dedicated PostgreSQL job completed Alembic upgrade to `0010_durable_workflow_leases`, schema drift check, downgrade, re-upgrade and second drift check; PostgreSQL integration reported **3 passed** including a concurrent workflow lease claim.
- Frontend typecheck/production build, 53-skill parity/source guard, unignored core/AI/frontend security audits, 10 AI/RAG imports, and push lockfile sync passed.
- The workflow runner now persists lease owner, expiry, heartbeat and attempt count; claims expired rows through PostgreSQL `FOR UPDATE SKIP LOCKED`; resumes queued/running read-only work from the stored stage checkpoint; and reclaims paused sessions through the lease path. The periodic worker and app lifespan start/stop hooks are included.
- Safety guard: an expired running live S5 external-publication stage is marked failed/outcome-unknown and audited for manual provider reconciliation; it is never blindly re-executed after a lost lease.
- Explicit limitations remain: the HITL verification response is still process-memory only and must be resubmitted if the process dies after a resume request; multi-replica resume routing has not been proven. Lease support improves restart recovery but is not a complete durable queue/outbox/at-least-once delivery guarantee or production certification.



## 2026-10-26 durable HITL response persistence — candidate
- Resumed from verified exact SHA `b6a83feaa279e8e2ff7e345b3713c63b2de673a5`; push [40307225678](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40307225678) and PR [40307237277](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40307237277) both passed before this change.
- The previous lease-recovery checkpoint still stored `verification_code` only in process memory and returned `verification_code_persisted: false`; a crash or request routed to a different replica could lose the acknowledged response.
- Candidate change adds nullable `paused_sessions.verification_response_encrypted`, encrypted using a Fernet key derived from the stable `APP_SESSION_SECRET`; no plaintext response enters state JSON or audit details. The response stays encrypted until its stage checkpoint succeeds.
- Resume requests can be accepted by any authenticated API instance. The lease-owning worker polls the durable `resume_requested` row and wakes its local task; after worker loss, a new lease owner loads the encrypted response before asking for another response. Decryption mismatch fails closed and records a workspace-scoped audit event.
- Migration `0011_durable_hitl_resume_responses` and two end-to-end regressions cover active cross-worker delivery and process-restart recovery. This candidate is pending exact-SHA SQLite migration, full Python, PostgreSQL migration/concurrency, AI/RAG, frontend, dependency-audit, repository-guard and PR CI. The first run's dependency-audit failure is recorded below and must be resolved by pinning a fixed cryptography line.
- Operational requirement: all replicas must use the same stable `APP_SESSION_SECRET`; key rotation during an outstanding resume request must be planned. Production release remains blocked by other documented security and UAT gates.


## 2026-10-26 HITL encryption dependency-audit correction
- The first run on `1095ae96a599ade8d3d2320ab0491a40bc4a43f6` exposed a required security-audit failure: `cryptography>=44,<47` resolved to 46.0.7 and `pip-audit` reported seven advisories. This failure is not waived.
- Updated the runtime range to `cryptography>=50,<51` based on the failed CI report's fixed versions (the live PyPI package record listed 50.0.2 as the latest release at review time). The follow-up exact-SHA audit and the entire matrix must pass before HITL encryption is considered verified.
- First-run checks before this correction: repository guard, frontend typecheck/build and push lockfile sync passed; Python, PostgreSQL, and AI/RAG jobs were still running. The current candidate remains pending the replacement run.



## 2026-10-26 durable encrypted HITL response and cross-worker resume — verified
- Exact implementation SHA: `92af1c5d06544e4870c8c550176fd19a25084d06`.
- Push CI https://github.com/AITECHPRODUCTS/Project1/actions/runs/40333566763 — **success**; PR CI https://github.com/AITECHPRODUCTS/Project1/actions/runs/40333573375 — **success**. All required jobs passed on this exact SHA.
- Confirmed gates: Python test suite and compile; fresh SQLite migration upgrade/downgrade/re-upgrade plus Alembic drift check; PostgreSQL migration upgrade/downgrade/re-upgrade, drift and lease/conversion concurrency tests; AI/RAG import profile; frontend `npm ci`, typecheck and production build; 53-skill source/runtime parity; core/AI/frontend dependency audit; and push lockfile sync.
- New migration `0011_durable_hitl_resume_responses` persists `PausedSession.verification_response_encrypted`. Fernet uses a key derived from `APP_SESSION_SECRET`; response values are not written to workflow state JSON or audit details. The response is cleared after the retried stage checkpoint succeeds.
- Any authenticated API replica can persist a workspace-validated resume request. The lease-owning worker polls its own pending rows and wakes its local task; after worker loss, a new lease owner consumes the encrypted pending response before emitting a fresh HITL prompt. A decryption/config mismatch fails closed and is audited. Two focused tests passed for active cross-worker delivery and process-restart recovery.
- Audit correction: the first candidate range selected vulnerable `cryptography 46.0.7` and failed CI; the finding was not waived. The requirement is now `cryptography>=50,<51`, and the subsequent full dependency audit passed.
- Production remains **not certified**: remaining provider authorization/UAT, broader route/worker/export tests, SBOM/license/secret scans, deployment smoke, backup/restore, and other outstanding release gates still need evidence. Every replica must keep the same stable `APP_SESSION_SECRET`; key rotation with pending encrypted responses needs a plan.


## 2026-10-26 outbound HTTP transport boundary — candidate
- Resumed from exact verified checkpoint `a1c11b197d3c81a0c6ed077bda9048f96048fdb8`: push [40334257428](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40334257428) and PR [40334262387](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40334262387) both passed all seven required jobs.
- Source review confirms credentialed provider calls use `backend/services/url_safety.py`, which pins the actual request to a vetted public IP, preserves Host/TLS SNI, disables redirects and environment proxies, caps response bodies, and supports the approved GET/HEAD/POST methods.
- Added a static AST guard and regression tests that reject new raw `httpx`, `requests`, `aiohttp`, `urllib`, `urllib3`, and `http.client` clients in `backend/` and `ai_memory/` outside the single approved transport module. CI's fast repository guard runs this before dependency installation.
- New exact-SHA push and PR verification is pending. This code-level guard does not substitute for the still-open live staging reverse-proxy spoofing test described in `docs/requirements/v4/11_DEPLOYMENT_OPERATIONS.md`.

## 2026-10-26 outbound HTTP transport boundary — verified
- Exact implementation SHA: `1725afcfc17acc8b890d8ccbc4bf04114638458d`.
- Push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40338107674 — **success**. PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40338115729 — **success**. All seven push jobs and every required PR job passed.
- Python suite: **338 passed, 3 skipped, 1 warning**. SQLite migration/drift and PostgreSQL migration/concurrency passed; frontend clean install/typecheck/production build passed; security audit, 53-skill parity, lockfile sync and AI/RAG profile passed (**10 imports**).
- Added `scripts/verify_outbound_transport_boundary.py` and six regression tests. The AST guard scans runtime Python in `backend/` and `ai_memory/` and rejects raw HTTP clients (`httpx`, `requests`, `aiohttp`, `urllib`, `urllib3`, `http.client`, low-level socket connect) outside the one approved `backend/services/url_safety.py` module. It also fails if pinning, TLS SNI, redirect, or environment-proxy invariants disappear from the approved transport.
- The fast `repo-guard` runs this check before dependency installation; the new guard itself passed in both push and PR runs.
- Separate external release gate remains open: actual reverse-proxy forwarding-header stripping/trust must be tested through a deployed staging ingress with sanitized logs, client-IP/rate-limit observations, staging URL, proxy source IP/CIDR, deployed SHA/image digest and timestamps. No staging result is inferred from this CI pass.
- Other release evidence still outstanding per runbook: authorized live-provider UAT, SBOM/license/secret scans, deployment smoke, database backup/restore and production monitoring/SLO evidence.

## 2026-10-26 Uvicorn trusted-proxy middleware tests — verified in CI
- Verified base checkpoint: 76d8469edd19d1dcf24a713ec3aad135cd6d96d2; transport guard runs passed in push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40338998193 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40339009309.
- The configuration accepts CIDR allowlists, but the previous Uvicorn lower bound 0.30 did not guarantee the implementation supports IP-network trust. Raised it to uvicorn[standard]>=0.31,<1.0.
- Added tests/test_trusted_proxy_middleware.py using the actual uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware: an untrusted direct peer cannot spoof client IP/scheme, an allowlisted CIDR can supply normalized forwarded identity, and trusted proxy chains stop at the first untrusted address.
- Exact-SHA verification passed: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40341045895 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40341061656 both succeeded. It does not replace live staging ingress test: deployed reverse proxy must strip and replace client-provided forwarding headers; record staging URL, SHA/image, proxy source CIDR, timestamps, sanitized logs and rate-limit observations.


## 2026-10-26 Uvicorn trusted-proxy middleware tests — verified in CI
- Implementation SHA: `da36211099ba27732510706189a267e9860b090e`.
- Push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40341045895 and PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40341061656 both passed. All seven push jobs and all required PR jobs passed: Python tests, SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG imports, frontend typecheck/build, dependency security audits, 53-skill/source repository guard and push lockfile reproducibility.
- `tests/test_trusted_proxy_middleware.py` uses Uvicorn's actual `ProxyHeadersMiddleware` and covers untrusted spoofed X-Forwarded-For/X-Forwarded-Proto, allowlisted CIDR forwarding and trusted-hop chain selection. Runtime requirement is `uvicorn[standard]>=0.31,<1.0`.
- This closes the code-level compatibility/test gate only. It does **not** establish that a real deployed reverse proxy strips/replaces attacker-supplied forwarding headers. The staging ingress gate remains open and requires a controlled spoof test plus timestamped sanitized evidence: staging URL, deployed SHA/image digest, configured proxy CIDR/source IP, app/proxy-observed client IP and scheme, and rate-limit behavior.
- Next code-addressable release gap: add deterministic CI SBOM generation, license-policy reporting/enforcement, and secret scanning. These jobs must run on push and PR without printing secrets; output artifacts should identify exact candidate SHA. Keep live staging proxy verification and provider/UAT/deploy/restore gates as external requirements.


## 2026-10-26 supply-chain evidence automation — candidate
- Verified base code checkpoint: `da36211099ba27732510706189a267e9860b090e`; push [40341045895](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40341045895) and PR [40341061656](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40341061656) both passed.
- Added a pinned Gitleaks full-history scan using an OCI image digest, with redaction enabled and a redacted JSON report artifact. Added candidate-SHA SBOM artifacts for core Python/test dependencies, optional AI/RAG dependencies and the committed frontend package tree.
- Added a conservative license policy: missing/unknown metadata and GPL/AGPL/LGPL/SSPL, proprietary/commercial-source and noncommercial licenses fail the release CI gate pending explicit legal review. Scanner dependencies run in an isolated tool venv so they do not contaminate the target runtime inventories.
- Added license-policy regression tests for permissive, prohibited and unknown license labels/expressions. Candidate changes are **pending exact-SHA CI**; current scan output and package inventory must be reviewed before considering this item verified.


## 2026-10-26 supply-chain scan first-run findings and narrow correction — verified
- Exact initial candidate `4331d2c5f848d5580dc93990191fc01a7c80b2cb`: push [40346076313](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40346076313) and PR [40346091684](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40346091684) failed the new secret-scan and frontend license-policy steps. Python, PostgreSQL, frontend build, repo guard, AI/RAG import + AI SBOM, and lockfile sync passed.
- Gitleaks reported one finding at `knowledge/affiliate-skills/upstream/skills/content/viral-post-writer/SKILL.md:68`. Reviewing the redacted report plus the historical source shows the match is the ordinary phrase “conversational tone”, not a credential. The fix ignores only the exact historical Gitleaks fingerprint; a test rejects any additional/broader ignores.
- Frontend CycloneDX reported exactly two LGPL-3.0-or-later components: `@img/sharp-libvips-linux-x64@1.3.4` and `@img/sharp-libvips-linuxmusl-x64@1.3.4`. Added exact-package/version/license inventory exceptions expiring 2026-11-02 to keep CI reporting complete. The policy artifact explicitly marks these as release blockers pending legal review; they are not distribution approval. Other blocked/unknown licenses continue to fail.
- Corrective commit verified on exact SHA `f254ec0d998fa6541fba8415d0ed059fda7e4a23`: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40348612494 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40348624953 passed all required jobs. Reports are keyed to `GITHUB_SHA`; exact-fingerprint and time-expiry regression tests pass.


## 2026-10-26 SBOM, license policy and secret scan automation — verified
- Exact implementation SHA: `f254ec0d998fa6541fba8415d0ed059fda7e4a23`. Push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40348612494 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40348624953 both passed. All eight push jobs passed (including lockfile sync); all seven required PR jobs passed.
- Python suite: **361 passed, 3 skipped, 1 existing Starlette/httpx deprecation warning**. PostgreSQL migration/concurrency; frontend typecheck and production build; AI/RAG import/SBOM; dependency audits; 53-skill/repository guard; and full-history Gitleaks scan all passed.
- The redacted Gitleaks report artifact is [here](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40348612494/artifacts/12662667063); its JSON contains **zero findings**. The only ignored fingerprint is a confirmed false positive for the ordinary phrase “conversational tone” in a historical skill file, constrained by a regression test to one exact historical file/rule/line.
- Core/test Python SBOM + license report (76 packages): zero findings, no exceptions. AI/RAG report (90 packages): zero findings, no exceptions. Frontend CycloneDX/license report (109 packages): zero unreviewed findings; two exact LGPL-3.0-or-later transitive libvips components use time-bounded CI-inventory exceptions ending **2026-11-02**. The report explicitly sets `release_approved=false`.
- Evidence artifacts: [core + frontend SBOM/license inventory](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40348612494/artifacts/12662472475) and [AI/RAG SBOM/license inventory](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40348612494/artifacts/12663455278).
- The license exceptions are not legal clearance. Production remains blocked until a maintainer/legal reviewer resolves LGPL notice, source/relinking and redistribution requirements, or the components are removed/replaced; if unresolved, the exception expires and CI fails closed. External staging trusted-proxy verification, authorized live-provider UAT, SBOM artifact review as part of release, deployment smoke, monitoring/SLO and backup/restore also remain release gates.
- Next P0: review remaining provider SDK/direct transport integrations and actual deployment evidence; keep the single branch and continue fixing any observed CI failure.



## 2026-10-26 hosted LLM SDK transport hardening — verification history

- The initial async-only attempt `5ffcd5d5042d7ebd14e024c15bd271cca277908b` was correctly rejected by the strict guard because the legacy RAG factory also constructed `ChatOpenAI` without the pinned client. The guard was not weakened.
- Corrected implementation SHA `337e31ed9a964a7cdfcde56abb9ee9d379400265` passed push [40360698617](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40360698617) and PR [40360704559](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40360704559). Python: 368 passed, 3 skipped, 1 existing warning; all eight push jobs and all seven required PR jobs passed.
- Documentation checkpoint `f41cb8e1eba7caeb05777263c9f53c5890f1be23` also passed push [40361504831](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40361504831) and PR [40361512478](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40361512478).
- This verifies the code-level SDK transport change only. Actual staging proxy/egress verification, authorized model/provider UAT, deployment smoke, monitoring/SLO and backup/restore remain external release gates.

## 2026-10-26 pinned SDK sync/async correction — verified
- The first exact-SHA candidate `5ffcd5d5042d7ebd14e024c15bd271cca277908b` failed the strict transport guard at `ai_memory/rag_chain.py:80`. The failed push [40359428990](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40359428990) and PR [40359436287](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40359436287) otherwise passed Python, PostgreSQL migrations/concurrency, AI/RAG imports/SBOM, frontend build, security audits and secret scan. The source guard correctly identified a second legacy `ChatOpenAI` factory; it is not being suppressed.
- Corrective candidate adds both a synchronous and asynchronous DNS-pinned transport, injects both into the primary LLM service and legacy `DoctrineRAG.retrieval_qa()`, disables SDK retries, and retains the static guard requirement for both clients. The RAG service exposes explicit async cleanup for retained clients.
- New tests cover the sync transport's HTTPS rejection, IP pinning, Host/TLS SNI, and the static guard requires both injected clients. Await exact-SHA push and PR CI before marking this fix verified.

## 2026-10-26 model-artifact runtime egress boundary — verified
- Base SHA `f41cb8e1eba7caeb05777263c9f53c5890f1be23` is green in push [40361504831](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40361504831) and PR [40361512478](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40361512478). The blueprint's next P0 security follow-up is preventing implicit model downloads on API, worker, or RAG ingestion paths.
- Candidate centralizes Hugging Face embedding setup in `ai_memory/model_artifacts.py`, sets `local_files_only=True` for embeddings and local Transformers/PEFT loads, rejects mutable/short revision pins, requires an immutable 40-hex revision for production Hub embedding IDs, and places model@revision into the local SQLite vector-index identity. A blank development revision keeps the existing default index identity and adds no database migration.
- Added static-guard regressions and `tests/test_model_artifacts_local_only.py`. The operator artifact-preparation runbook is `docs/MODEL_ARTIFACT_OPERATIONS.md`. No model artifact is claimed to have been staged, licensed, or validated in production.
- Exact-SHA implementation and fixture-repair CI passed at `393e12760762993e70a862af9b4c3ab61d308739`: push [40364123382](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40364123382) and PR [40364131533](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40364131533). The model cache, model license review, RAG re-ingestion golden tests and deployed runtime behavior remain separate release gates.


## 2026-10-26 model local-only guard regression fixture — corrective commit pending CI
- Candidate SHA `47bd006c665ba490d2cbd0c0a87c57c8350ef0f4` failed the required Python suite with four failures in `tests/test_outbound_transport_boundary.py`; the run log shows the synthetic source fixtures contained literal backslash-n sequences, so the AST guard correctly rejected unparsable Python before checking the forbidden/allowed `local_files_only` forms.
- This is a test-fixture escaping defect, not a reason to relax the guard or permit implicit downloads. The fixtures are being corrected to use real newline escapes in the Python string literals; require new exact-SHA push and PR runs before marking the model-artifact change verified.


## 2026-10-26 model-artifact runtime egress boundary — verified
- Exact validated SHA: `393e12760762993e70a862af9b4c3ab61d308739` (includes the model artifact implementation plus the corrected guard-test fixtures).
- Push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40364123382 — **success**. PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40364131533 — **success**. Push ran all eight jobs including lockfile sync; all required PR jobs passed (lockfile-sync is deliberately skipped on PR).
- Python suite: **377 passed, 3 skipped, 1 existing warning**. Static verification passed. PostgreSQL migration/downgrade/drift and concurrent reversal/workflow-lease checks passed. AI/RAG imports and reproducible AI/RAG SBOM/license inventory passed. Frontend typecheck/production build, core+AI dependency/license audits, secret scan, 53-skill repository guard, and push lockfile reproducibility passed.
- Runtime embedding setup is centralized in `ai_memory/model_artifacts.py`, with `local_files_only=True`, immutable 40-hex revision normalization and revision-aware vector-index identity. RAG runtime, CLI ingestion, local tokenizer/model, and PEFT adapter loaders use local-files-only behavior; production Hub embeddings require a revision pin. Runbook: `docs/MODEL_ARTIFACT_OPERATIONS.md`.
- The first implementation SHA `47bd006c665ba490d2cbd0c0a87c57c8350ef0f4` failed four tests because the synthetic source strings used literal backslash-n text. The guard correctly rejected invalid syntax; the guard was not relaxed. Commit `393e12760762993e70a862af9b4c3ab61d308739` corrected the fixture escapes and both subsequent workflows passed.
- This is source/CI verification, **not** proof that a real model artifact has been staged, license-reviewed, benchmarked, or loaded against a deployed index. Production still requires artifact provenance/license approval, staged cache-only load, RAG re-ingestion and retrieval-golden tests, plus staging egress/proxy checks, live provider UAT, LGPL exception resolution, deployment smoke, monitoring/SLO and backup/restore.
- Next P0: verify and document staged model provenance plus runtime cache-only load/recall checks; then continue the remaining egress/provider/deployment release gates.


## 2026-10-26 implementation update — proprietary learning dataset candidate generator
- Added workspace-scoped `POST /api/learning/proprietary-dataset` and dashboard controls to produce a JSONL snapshot from the persisted A/B experiment assignment/event ledger.
- The builder pairs stable A/B headline snapshots, aggregates persisted impression/conversion events, ignores duplicate event IDs, and excludes experiments without both variants or with inconsistent headline snapshots.
- Configurable per-variant impression and recorded-conversion gates label rows as eligible for human review or excluded for low sample. Visitor IDs are not included in dataset rows or exports.
- Snapshots persist as review-required ContentAsset records with an audit event. Only rows passing the sample gate enter the JSONL body.
- Events are internal app-recorded observations and are not provider-attested; observed rates are not causal proof. No model training, fine-tuning, promotion, publishing, or external action is performed.
- Tests cover aggregation, sample gates, variant/snapshot integrity, duplicate event IDs, ignored event types, invalid thresholds, and endpoint persistence. Hosted CI must pass on the exact commit before this slice is considered verified.
