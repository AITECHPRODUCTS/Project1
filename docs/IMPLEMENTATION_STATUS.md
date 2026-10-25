# Implementation status — Project1 / OmniAffiliateOS
Updated: 2026-10-25

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
See `skill-parity-matrix.csv`: 53 skill rows are explicitly traced. Current matrix is 47 partial and 6 not implemented, 0 fully implemented end-to-end. These 53 rows are a skill inventory only, not overall product-completion percentages. That is a gap ledger—not a claim that reference skill text equals working runtime behavior.

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
