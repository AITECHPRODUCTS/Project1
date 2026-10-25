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
See `skill-parity-matrix.csv`: 53 skill rows are explicitly traced. Current matrix is 36 partial and 17 not implemented, 0 fully implemented end-to-end. These 53 rows are a skill inventory only, not overall product-completion percentages. That is a gap ledger—not a claim that reference skill text equals working runtime behavior.

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
