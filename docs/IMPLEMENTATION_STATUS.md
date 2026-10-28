# Implementation status — Project1 / OmniAffiliateOS
Updated: 2026-10-28

## Candidate under verification — hardened ad guardrail runtime (2026-10-28)

- Feature code commit: [9ccfb8480453a35311b7fdd451f6cbba0bcc3f71](https://github.com/AITECHPRODUCTS/Project1/commit/9ccfb8480453a35311b7fdd451f6cbba0bcc3f71). The `ads.guardrail_review` skill runtime now treats all payload observations as caller-supplied and unattested even if the JSON claims `provider_verified`. The authoritative result fails closed; any possible breach is isolated inside `hypothetical_review` and labelled as a scenario requiring independent attestation.
- This correction is important because the generic skill execution endpoint accepts user-supplied JSON. It must not turn an operator-entered status label into evidence that Meta, Google or another ad provider was authenticated. No live spend, pause, kill-switch or other provider action is authorized or performed by this handler.
- Regression tests cover caller-claimed provider verification, blocked authoritative results, hypothetical spend-cap breach scenarios, stale scenario evidence, and invalid inputs.
- Status of the corrected combined candidate: push/PR CI is pending after the final code plus documentation commit. Do not call this correction CI-verified until those exact-SHA runs complete.


## 2026-10-28 verified build — S1 offer-metrics runtime handler

- Feature code was introduced by [commit 440d378d7588081f6e072e18e35bd7573543f89a](https://github.com/AITECHPRODUCTS/Project1/commit/440d378d7588081f6e072e18e35bd7573543f89a). The handler `research.offer_metrics` is allowlisted in `backend/services/skill_runtime.py` and calls the existing validated `compute_offer_metrics` service. It computes EPC, conversion rate and normalized supplied gravity from explicit inputs; missing data remains unknown. It rejects unexpected input fields, invalid numeric values and impossible counts. It performs no network request or external mutation.
- The fully tested source candidate [ca03d16af65c11f93f185fd7e2f33d3ad9598d41](https://github.com/AITECHPRODUCTS/Project1/commit/ca03d16af65c11f93f185fd7e2f33d3ad9598d41) includes that feature plus documentation. Both exact-SHA hosted workflows passed: [push 40723769566](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40723769566) and [PR 40723782320](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40723782320).
- Python: **648 passed, 7 skipped, 5 warnings** on both runs. Browser UAT: **5 passed** on each run. PostgreSQL migration/concurrency, frontend typecheck/production build/Docker smoke, AI/RAG SBOM, security/dependency audit, secret scan and repository guard passed. Push lockfile sync passed; PR lockfile sync was skipped by its configured event condition. No failed job was present.
- This verifies the current automated scope, not full S1 production completion. Authorized affiliate source retrieval, provider-origin evidence, freshness/terms confirmation and live provider contract/UAT remain pending. This runtime handler must not be presented as a marketplace connector or as independent validation of supplied values.


## 2026-10-28 verified checkpoint — double opt-in and truthful signup outcomes

- Verified feature/test SHA: `22b64068cb06d5085761aad986e3787a59634981`. [Push CI run 40713741377](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40713741377) and [PR CI run 40713751355](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40713751355) both completed successfully on feature/test checkpoint `22b64068cb06d5085761aad986e3787a59634981`. Python: **619 passed, 7 skipped, 5 warnings**. PostgreSQL migration/concurrency, frontend typecheck/build/final Docker smoke, AI/RAG, security/SBOM, secret scan, repository guard and browser UAT passed. Push lockfile-sync passed; PR lockfile-sync was skipped by event condition. The predecessor feature-code push/PR attempt exposed two test assertions comparing raw HTML with rendered copy; `22b6406` fixes the assertions to decode HTML entities while keeping production escaping intact.
- Migration 0026 adds a per-lead email-confirmation timestamp plus expiring confirmation records; the feature is controlled by `EMAIL_DOUBLE_OPT_IN_REQUIRED` and is off by default. It requires configured `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, and a valid public HTTPS callback URL before relying on real delivery.
- Implemented explicit DOI email delivery, 48-hour confirmation expiry, stored SHA-256 token hashes (raw tokens are not persisted), scanner-safe GET that renders a confirmation form without changing state, and a bounded URL-encoded POST that applies consent only after the recipient confirms.
- A conditional database update atomically claims a still-sent token before scheduling, preventing concurrent confirmation replays from both succeeding. Unsubscribe cancels pending/sent confirmation tokens; the email worker suppresses marketing delivery while DOI is required but unconfirmed.
- Owner/admin resend is workspace-scoped. A five-minute duplicate request guard reuses a recent matching confirmation, avoids sending a second message, and prevents a different pending signup payload from silently replacing the request bound to the existing token.
- Public HTML and JSON signup responses distinguish queued marketing, confirmation pending/in flight, and provider delivery failure; they no longer report a marketing sequence as queued when none was scheduled. Production HTML output remains escaped.
- Actual Resend account authentication, sender-domain verification and production delivery were **not** tested; CI uses controlled fixtures/mocks. Jurisdiction and owner policy review is needed before enabling DOI for a particular deployment. This is not a universal compliance guarantee.

## Prior verified checkpoint — immutable lead consent evidence
- Feature-code SHA: 8addf2b83991ca8015b4496704ef6a159b0a0a4a. [Push CI](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40706775818) and [PR CI](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40706784399) both completed successfully. Python: 610 passed, 7 skipped, 5 warnings. PostgreSQL migration/concurrency, frontend, AI/RAG, security/SBOM, secret scan, repository guard and browser UAT passed. Push lockfile-sync passed; PR lockfile-sync was skipped by its event condition.
- Migration 0025 and LeadConsentEvent add workspace-scoped evidence for consent grant, resubscription and unsubscribe. Grant events store the canonical displayed consent copy/version, purpose, source and timestamp. ORM and PostgreSQL/SQLite migration triggers enforce append-only history.
- The consent schema rejects client-substituted copy and non-current versions. Persisted landing pages display and submit the same canonical wording/version. GET /api/leads/{lead_id}/consent-events returns read-only workspace-scoped history.
- At this historical checkpoint, double opt-in remained unfinished. The later DOI checkpoint below closes the code-level confirmation route; purpose/jurisdiction-specific policy review, sender-domain verification, and governed privacy unlink/anonymization/retention remain open. No universal legal compliance is claimed.

## Historical verified checkpoint — unsubscribe safety and workflow test isolation
- Verified code checkpoint: dc998827d52a1a2c7973630f22df2642f058a8e6. [Push workflow](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40701960870) and [PR workflow](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40701969318) both completed successfully. Python: 604 passed, 7 skipped, 5 warnings. PostgreSQL migration/concurrency, frontend production/Docker, AI/RAG, security/SBOM, secret scan, repository guard and browser UAT passed. Push lockfile-sync passed; PR lockfile-sync was skipped by event condition.
- Unsubscribe is GET-safe: opening a signed URL renders a confirmation page and does not change consent. A separate signed POST is required for browser confirmation; RFC 8058 one-click POST remains supported. Request content type/body length, signature and expiry are checked; response headers prevent caching/referrer leakage and remote script/resource loading; pending/retry scheduled emails are suppressed transactionally on opt-out.
- Browser UAT asserts the initial GET leaves the lead subscribed, then submits an actual URL-encoded form POST and verifies the lead is suppressed. Workflow pause/cancel regression uses file-backed SQLite for the concurrent worker/poller test; this was test-harness isolation, not a runtime workflow code change.
- Historical gap at this checkpoint: Lead stored only the latest consent timestamp/source. The subsequent feature commit added the immutable event ledger; applicable double opt-in and universal jurisdictional compliance remain open.
- Release status remains NOT RELEASE READY. See docs/BUILD_PROGRESS_2026-10-28.md and docs/REQUIREMENTS_TRACEABILITY_MASTER.md for remaining work.

## 2026-10-28 verified build checkpoint — source evidence and human review
- Verified code checkpoint: 536428eab7c391b663bb311c5a2cf4aac1d4b854. [Push workflow](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40696184789) and [PR workflow](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40696194630) both completed successfully. Python: 597 passed, 7 skipped, 1 warning. PostgreSQL migration/concurrency, frontend production/Docker, AI/RAG, security/SBOM, secret scan, repo guard and browser UAT passed. Push lockfile-sync passed; PR lockfile-sync was skipped by event condition.
- Added explicit bounded HTTPS source fetches for offer terms (migration 0022), recorded body-hash comparisons across successive fetches (migration 0023), and a second-person human-review flow for changed pages (migration 0024). The fetch uses the existing DNS-pinned public HTTP helper; it refuses HTTP, does not follow redirects, caps response bytes and text types, persists safe retrieval metadata and hashes, and audits the attempt.
- Changed source page content opens human review; it is not assumed that a page hash change means the terms changed. The review records decision, notes, reviewer and time. Material-change or unreliable-source findings invalidate internal term verification and activation; no external network approval or provider verification is inferred.
- Release status remains NOT RELEASE READY. See docs/BUILD_PROGRESS_2026-10-28.md for remaining production work.

## 2026-10-28 verified build checkpoint — offer terms and metric integrity
- Historical checkpoint f787358479d27490f3e4e8b516eab5c27f2e84be passed its push and PR workflows; current authoritative evidence is the latest 536428eab7c391b663bb311c5a2cf4aac1d4b854 run documented above.
- Added merchant offer term snapshots with an Alembic migration, workspace-scoped capture/history APIs, SHA-256 fingerprints, deterministic per-offer sequence numbers, field-level comparisons, audit events, a terms-history UI and revalidation gating. This is operator-evidence capture; it does not fetch evidence URLs or establish provider verification.
- Fixed offer metric handling so negative or non-finite revenue, invalid/fractional counts, booleans and invalid weights raise validation errors instead of being silently clamped/truncated. Invalid/non-finite source gravity remains unknown.
- Release status remains NOT RELEASE READY. See docs/BUILD_PROGRESS_2026-10-28.md for the current feature list and remaining production work.

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
See `skill-parity-matrix.csv`: 53 skill rows are explicitly traced. Current matrix is 53 partial and 0 not implemented, 0 fully implemented end-to-end. These 53 rows are a skill inventory only, not overall product-completion percentages. That is a gap ledger—not a claim that reference skill text equals working runtime behavior.

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
- Current skill matrix remains 53 partial, 0 not implemented, 0 fully end-to-end complete. Latest previously verified baseline c7ee98e1... passed push/PR workflows, including PostgreSQL migration/reversal checks. The newly added guard/vendor changes need exact-SHA hosted workflow confirmation.
- P0 work still open: generate and commit a reproducible frontend lockfile; strengthen tenant/RBAC/security tests across all active endpoints and workers; add dependency/security scans and Playwright UAT; prove provider contracts, staging/deployment, backup/restore and operational budgets. The local package registry was not reachable for lockfile generation, so CI is not yet switched to npm ci.


## 2026-10-25 resumed checkpoint — deterministic frontend install and security gate
- Re-inspected the live branch before continuing: `build/omni-affiliate-os-production`, HEAD at `e6e6eb4e552b4887da252db0df172dd25ee79561`. No branch was created and `main` was not changed.
- The committed `frontend/package-lock.json` is npm lockfile v3 with 141 dependency packages and 141 resolved package entries. Its root dependency/devDependency declarations match `frontend/package.json`.
- On exact SHA `e6e6eb4e552b4887da252db0df172dd25ee79561`, push workflow [40213802242](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40213802242) and PR workflow [40213808545](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40213808545) both completed successfully. Verified successful jobs: Python/source tests and SQLite migrations; PostgreSQL 16 upgrade/downgrade/drift and conversion-reversal integration; AI/RAG dependency imports; repository/source-syntax and pinned 53-skill registry guard; frontend `npm ci`, TypeScript typecheck and Next.js production build. The push-only lockfile sync job also passed; the PR correctly skipped that write-capable job.
- Runtime skill parity remains 53 partial, 0 not implemented and 0 fully end-to-end complete out of 53 tracked skills. The 53-source inventory is not an overall product completion percentage.
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
- Tests cover aggregation, sample gates, variant/snapshot integrity, duplicate event IDs, ignored event types, invalid thresholds, privacy and endpoint persistence. Verified on exact SHA `a9eebf989704b7d7d347ee9021572bd2d5ea4f03`: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40365898032 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40365904286 both passed.


## 2026-10-26 proprietary experiment-learning dataset — verified
- Exact SHA: `a9eebf989704b7d7d347ee9021572bd2d5ea4f03`.
- Push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40365898032 — success; PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40365904286 — success.
- Python suite: 385 passed, 3 skipped, 1 existing warning. PostgreSQL migration/concurrency, AI/RAG imports and SBOM/license inventory, frontend production build, core/AI dependency and license audits, repository/53-skill guard, secret scan and push lockfile sync passed.
- Workspace-scoped POST /api/learning/proprietary-dataset creates a review-required JSONL ContentAsset and audit record from persisted A/B experiment assignments/events. The builder pairs stable A/B headline snapshots, deduplicates event IDs, ignores unknown event types, excludes incomplete/inconsistent experiments, and applies per-variant impression/conversion gates before marking a row eligible for human review.
- Privacy tests assert actual visitor identifier values are absent while permitting the explicit disclosure flag visitor_identifiers_included=false. Registry parity expects 48 partial and 5 not implemented rows across 53 pinned skills, consistent with the new feature row. The initial failed run on 684e6e1ae3d5b2a19fa6df6b074735788e47f420 remains in Actions; corrective commit a9eebf989704b7d7d347ee9021572bd2d5ea4f03 corrected both test assertions without weakening feature behavior.
- This is a dataset candidate generator, not model training. Events are app-recorded and not provider-attested; observed rates are not causal evidence. No fine-tuning, training, promotion, or model update occurred.
- Next P0: operator-run staged model-artifact manifest validation for exact app SHA, immutable model revision, file digest, license/provenance and cache-only runtime policy. Real artifact staging, license review, deployed cache-only load and retrieval golden tests remain external release gates.


## 2026-10-26 staged model artifact provenance gate — candidate, exact-SHA CI pending
- Base verified head: `b704a3fb79b8c47762719ff3a84b95702a6ebe0a`. The proprietary-learning dataset feature is green at `a9eebf989704b7d7d347ee9021572bd2d5ea4f03`: push [40365898032](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40365898032) and PR [40365904286](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40365904286) passed; Python 385 passed/3 skipped.
- Candidate adds an operator-run release manifest verifier that binds the exact application SHA to staged model directories; verifies safe relative paths and symlink-free files, deterministic SHA-256 tree digests, immutable Hub revisions, license approval/provenance fields with timezone-aware timestamps, local-files-only and `trust_remote_code=false`.
- Added `tests/test_model_artifact_manifest.py` for valid manifest acceptance, deployment SHA mismatch, mutable revision rejection, artifact drift, unapproved license, unsafe runtime flags, path traversal, symlink rejection, timezone validation and duplicate names. Documentation is in `docs/MODEL_ARTIFACT_OPERATIONS.md`.
- This is validation tooling, not a claim that a model has been staged or approved. Exact resulting-SHA full push/PR CI is pending; artifact source, digest, license evidence, release-image cache-only load and retrieval golden tests remain external release gates.



## 2026-10-26 staged model artifact manifest release gate — source and CI verified
- Exact candidate SHA: a3c2627d26a765ac88e4ef3c164b86e850a7c40c.
- Push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40367360162 succeeded; PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40367367483 succeeded.
- Python: 396 passed, 3 skipped, 1 existing warning. All eight push jobs passed: Python, SQLite migrations/drift, PostgreSQL migration/concurrency, AI/RAG imports and SBOM/license inventory, frontend typecheck/production build, dependency/license audit, secret scan, 53-skill repository guard, and lockfile reproducibility.
- Added scripts/verify_model_artifact_manifest.py. It validates the exact application commit SHA, safe relative artifact paths, symlink-free directory trees, deterministic SHA-256 tree digests, immutable 40-character Hub revisions, required acquisition/license-review fields and timezone-aware timestamps, local_files_only=true and trust_remote_code=false.
- Added ten test functions/cases in tests/test_model_artifact_manifest.py, including valid manifests, deployment SHA mismatch, mutable revision rejection, digest drift, unapproved license, unsafe runtime flags, traversal, symlink and timestamp rejection, and duplicate artifact names.
- Operator runbook: docs/MODEL_ARTIFACT_OPERATIONS.md. A positive result only verifies the staged directory against its manifest and declared provenance. The verifier does not cryptographically authenticate the manifest or the truth of human license approval.
- Production still is not certified: no real model artifact has been reported staged or license-approved in this repo. Actual artifact/cache digest and license sign-off, cache-only load from the release image, RAG re-ingestion/retrieval-golden tests, staging egress/proxy tests, authorized provider UAT, LGPL exception resolution, deployment smoke, monitoring/SLO and backup/restore remain open.

## 2026-10-26 implementation update — webinar registration funnel
- Added workspace-scoped `WebinarEvent` and `WebinarRegistration` persistence with Alembic migration `0012_webinars`, chained after the current migration head.
- Added authenticated event draft/list endpoints and explicit owner/admin open/close controls. Draft pages remain unavailable publicly until registrations are intentionally opened.
- Added a public registration page and API with IANA timezone validation, start/end/deadline validation, optional capacity, required event-administration consent, separately optional marketing consent, normalized email addresses, per-event duplicate suppression and audit entries.
- Added a responsive Next.js public registration route and dashboard form for event details, agenda, privacy policy, disclosure and opening/closing registration.
- Registrations are stored locally; meeting-room/provider integration and confirmation-email delivery remain unconfigured and are explicitly reported as such. Event registration never implies marketing opt-in.
- Tests cover draft visibility, opening authorization, consent enforcement, duplicate registration and seat capacity. CI must pass on the exact commit before this slice is considered verified.


## 2026-10-26 implementation update — affiliate program application packet
- Added workspace-scoped `AffiliateProgramApplication` persistence and Alembic migration `0013_program_applications`.
- Added create/list/review API routes for affiliate program application packets. The packet captures program and publisher URLs, audience, traffic sources, promotion channels, regions, monthly visitor declaration, promotion plan, evidence URLs and compliance attestations.
- Readiness checks report missing official terms evidence and unchecked affiliate disclosure, traffic-source terms, geographic restrictions, consent/privacy and claims-substantiation controls. User-provided URLs are references only; the system does not fetch them or treat them as verified facts.
- Owner/admin review can approve the packet for manual handoff or reject it. Provider submission remains `not_configured`; no external application is sent and no network approval is claimed.
- Audit events record packet creation and internal review. Tests cover incomplete readiness, evidence/checklist-gated handoff, workspace role gate and the non-submission invariant.



## 2026-10-27 merchant offer lifecycle — exact-SHA CI verified
- Implementation commit: \`fd712d411269a251b5fc70c912e2731c55c39a0a\`.
- Push workflow [40517947381](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40517947381) and pull-request workflow [40517953771](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40517953771) both completed successfully.
- Exact-SHA evidence: Python suite 406 passed, 3 skipped, 1 existing Starlette/httpx deprecation warning; PostgreSQL integration suite 3 passed; frontend typecheck and production build passed and included the \`/merchant/offers\` route; AI/RAG import/SBOM, repo/source/53-skill guard, dependency and license inventory, Gitleaks secret scan, and push lockfile reproducibility jobs passed.
- Added a workspace-scoped merchant offer packet with typed Decimal commission terms, allowed regions, restricted traffic-source declarations, source references and affiliate disclosure; draft, submit, second-person evidence review, reject and suspend routes write audit events.
- Regression tests cover workspace isolation, self-review denial, explicit evidence attestations, suspension, non-admin denial, private-URL rejection, commission percentage bounds, and the invariant that internal approval never implies affiliate-network approval or provider submission.
- **Not production release approval:** the frontend SBOM/license report still says \`release_approved=false\` due to two temporary LGPL-3.0-or-later sharp/libvips inventory exceptions expiring 2026-11-02. External provider authorization, human verification of evidence, browser UAT, staging ingress/egress, deployment smoke, monitoring/SLO and backup/restore remain open.



## 2026-10-27 internal publisher marketplace and cross-workspace applications — exact-SHA CI verified
- Implementation source is present on the existing branch and verified at exact SHA \`de8a59e2e86c6f318a7c9a789516d749debfb9ae\`.
- Push workflow [40522649663](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40522649663) and PR workflow [40522660792](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40522660792) completed successfully.
- Python suite: **410 passed, 3 skipped, 1 existing Starlette/httpx deprecation warning**. PostgreSQL integration: **3 passed**. SQLite and PostgreSQL migrations upgraded/downgraded/re-upgraded with \`alembic check\` reporting no new operations.
- Frontend typecheck/production build passed and emitted \`/marketplace\`, \`/merchant/applications\`, and \`/merchant/offers\`. Repository/53-skill guard, AI/RAG imports and SBOM, dependency/license inventory, Gitleaks, and push lockfile reproducibility passed.
- Added explicit internal-marketplace listing state, publish/unlist controls, safe catalog projection, terms snapshots, application compliance/contact-sharing attestations, publisher-scoped outgoing records and merchant-owner-scoped incoming reviews. Cross-workspace regression tests passed. No external affiliate-network submission/approval is claimed.
- **Production is still blocked:** the security job says \`release_approved=false\` because two temporary LGPL-3.0-or-later sharp/libvips inventory exceptions expire on 2026-11-02. Authorized live provider UAT, browser/accessibility UAT, staging trusted-proxy/egress, production deploy smoke, monitoring/SLO and backup/restore remain separate release gates.


## 2026-10-27 marketplace migration drift — correction verified
- Initial marketplace candidate SHA \`4ed81112ad2b579ef88e720c5e4cdef9ce539cf8\` failed both push [40521613901](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40521613901) and PR [40521622522](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40521622522) at SQLite/PostgreSQL drift checks because the column \`merchant_offers.marketplace_listed\` had a migration default not represented in ORM metadata.
- The correction adds SQLAlchemy \`server_default=false()\` to match the migration. No migration guard or tests were weakened.
- Corrected exact SHA \`de8a59e2e86c6f318a7c9a789516d749debfb9ae\` passed both push run 40522649663 and PR run 40522660792, including both migration drift gates. The original failed runs are retained as audit history.


## 2026-10-27 marketplace eligibility enforcement — candidate
- Added server-side rejection before any application row is created when publisher intended regions exceed the merchant's explicitly allowed regions or selected traffic sources conflict with the merchant's declared restrictions. Space, hyphen and underscore variants are normalized.
- The publisher form pre-populates eligible regions and selects safe default traffic sources from the displayed merchant offer; the backend remains authoritative.
- Regression tests cover disallowed regions, restricted traffic, no application row on rejection, and a compliant application path.
- This source candidate is not verified until both exact-SHA push and PR workflows pass, including SQLite/PostgreSQL migration/drift, frontend build, security and 53-skill guard jobs.



## 2026-10-27 paid-media budget guardrails — exact-SHA CI verified
- Implementation commit: 8a32bfb8c6b948c0b9221a984920183ff609de82. Push workflow 40525971292 and pull-request workflow 40525978916 both succeeded.
- Python suite: 416 passed, 3 skipped, one existing Starlette/httpx deprecation warning. PostgreSQL integration: 3 passed. The frontend production build includes /ads/guardrails. AI/RAG profile, secret scan, repository/skill guard, security audit and push lockfile reproducibility passed.
- Migration 0016 supports per-plan daily/campaign caps, ROAS/CPA and evidence sample gates, verified-evidence-only evaluation, an auditable stop latch and manual kill switch. It never executes a provider pause or authorizes live spend.
- Release remains blocked by two temporary LGPL-3.0-or-later sharp/libvips inventory exceptions expiring 2026-11-02 (license inventory records release_approved=false). Human legal review, provider authorization/UAT, browser acceptance and deployment/restore evidence remain required.


## 2026-10-27 signed ad performance ingestion — exact-SHA CI verified
- Implementation commit: 13700e8076641ae3dca1244f37b878e890ec6723. Push workflow 40528436803 and pull-request workflow 40528445045 both succeeded.
- Python suite: 420 passed, 3 skipped, one existing Starlette/httpx deprecation warning. The 0017 migration passed SQLite and PostgreSQL upgrade/downgrade/re-upgrade and Alembic drift checks; PostgreSQL integration: 3 passed. Frontend, AI/RAG SBOM/import profile, security audit, secret scan, repo/skill guard and push lockfile jobs passed.
- Added workspace/platform-scoped HMAC, exact-body verification, request-size bounds, unique event idempotency, raw-body digest provenance, an audit event, timestamp and platform validation, and regression tests including end-to-end stop-latch triggering from a signed observation.
- HMAC authenticates the configured trusted collector, not a native platform signature. Only mark evidence provider_verified when the separately provisioned collector independently validates the source; native ad-account authorization, provider-native verification, live pause/scale actions and live spending remain not configured. Production release is still blocked by the LGPL license exceptions noted above.



## 2026-10-27 scheduled ad guardrail monitor — exact-SHA CI verified
- Implementation commit: 798d4f60d212ba8d86dbc7d48e72dead52423a93. Push workflow 40529623563 and pull-request workflow 40529634466 both succeeded.
- Python suite: 422 passed, 3 skipped, one existing Starlette/httpx deprecation warning. PostgreSQL integration: 3 passed. SQLite and PostgreSQL migration/drift checks passed; frontend, AI/RAG, security audit, secret scan, repository guard and push lockfile reproducibility passed.
- A five-minute APScheduler job scans known workspaces using the existing background workspace enumerator. It rechecks non-latched policies under the owning workspace context and row lock, evaluates verified observations, persists the latest result, and audits status transitions and stop breaches.
- The monitor test uses signed collector data and confirms the scheduled job latches a verified breach. The job never invokes remote provider actions. Production still lacks provider pause enforcement/UAT, and release remains blocked by the temporary LGPL sharp/libvips exceptions pending legal review.


## 2026-10-27 frontend production dependency boundary — exact-SHA CI verified
- Implementation source and production-runtime policy are verified at commit bd103628f038401de73e14484088965fb29e0516: push workflow [40536193799](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40536193799) and PR workflow [40536200952](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40536200952) both succeeded.
- Python suite: **423 passed, 3 skipped, 1 existing Starlette/httpx deprecation warning**. PostgreSQL integration: **3 passed**. Frontend typecheck/build, post-prune Next server smoke, actual Docker build and container smoke all passed.
- The production runtime verifier found no next/image use, no installed sharp, and no installed @img/sharp-* / libvips package. The separate production CycloneDX SBOM contained **19 packages** and passed the license policy with no exceptions, unknown licenses or blocked licenses.
- The complete npm build/install SBOM remains at 109 packages for traceability. It records two exact optional libvips components only as temporary-build-inventory-only; release_approved for that build inventory is indeterminate, and this report is not used to approve production distribution. The runtime SBOM was filtered from the actual pruned package manifests and scanned without an exceptions file.
- This resolves the sharp/libvips runtime inventory blocker for the current frontend image, not overall product release approval. Authorized provider UAT, browser/accessibility UAT, staging proxy/egress, deployment smoke, monitoring/SLO, model-artifact provenance/retrieval validation, backup/restore and remaining external-provider capabilities remain open.


## 2026-10-27 signed ad collector deployment configuration — exact-SHA CI verified
- Implementation SHA: 714d81b4518f6ac5fdd366dd8d536f9af8b3e728. Push workflow [40537147027](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40537147027) and PR workflow [40537158642](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40537158642) completed successfully.
- Compose forwards AD_PERFORMANCE_WEBHOOK_SECRETS to the API container; .env.example defaults to an empty JSON object and contains no live secret. The CI regression parses the deployment YAML.
- This wiring configures a signed trusted collector only; it does not authenticate the underlying ad-network account or enable live ad changes.



## 2026-10-27 jurisdiction compliance evidence register — candidate
- Added a workspace-scoped assessment register with activity, channel, target jurisdiction, per-category HTTPS source evidence, reviewer attestation, evidence freshness checks, 180-day approval expiry, immutable reviewed/rejected decisions, and audit events.
- New live social/CMS publication and S5 workflow actions are gated against current approved assessments covering the exact channel and every declared target jurisdiction. A completed idempotent replay remains replay-only and does not execute a new provider action. Drafts, previews, and dry-runs remain available without a legal assessment.
- Added a responsive /compliance console for source evidence collection, coverage gaps, reviewer notes, and explicit human approval confirmation. No global law database or legal certification is claimed; reviewers must confirm current authoritative sources and jurisdictional applicability.
- Candidate until exact-SHA push and PR tests, migration/drift, frontend typecheck/build, security/SBOM/license, secret scan, AI/RAG, PostgreSQL integration and lockfile checks all pass. Paid-media, email, lead-capture and tracking rule categories are catalogued, but corresponding external live actions remain separately gated/not enabled until their own execution paths are implemented.


## 2026-10-27 implementation update — governed declarative skill packages
- Added tenant-scoped, semver-versioned skill package records with a unique workspace/skill/version key, input/output JSON contract schemas, declared capabilities, Markdown instructions, fixture manifests, deterministic SHA-256 checksums, and review audit events.
- Added a bounded JSON-schema subset validator. It rejects unsupported schema keywords (including remote references), checks fixture inputs and expected outputs, and labels the result explicitly as contract-fixture validation—not runtime execution or proof that the instructions behave correctly.
- Added workspace API routes to create/list/detail skill packages and approve/reject individual versions. Approval requires explicit human confirmation and all contract fixtures to pass. Reviewed versions are immutable; changes require a new version. Capability names suggesting external writes, publishing, communications, financial actions, credentials or deployment are flagged for reviewer attention but do not execute.
- Added the “Governed skill packages” UI for authoring declarative manifests, inspecting checksums and fixture failures, and recording review decisions.
- Updated `docs/skill-parity-matrix.csv`: `meta/create-skill` is now partial because package authoring, static contract validation and review persistence exist. Runtime dispatch/sandboxing, execution-specific tests, and UAT remain open; this is not an end-to-end-complete skill.
- Current skill inventory remains 53 rows: 51 partial, 2 not implemented, 0 fully implemented end-to-end. This is a skills inventory, not an overall product completion percentage.


## 2026-10-27 implementation update — bio-link studio and CMS publishing
- Added a workspace-scoped bio-link page builder using the existing content-asset persistence model; pages remain drafts until an operator explicitly sends them to WordPress/Ghost.
- Added strict destination validation for absolute HTTP(S) URLs, rejection of credentials/local/private literal destinations, HTML escaping for all user text, affiliate disclosure requirements, sponsored/nofollow link attributes, responsive accessible markup, and first-party UTM parameters that preserve existing query parameters.
- Added an authenticated no-store preview endpoint with a restrictive Content Security Policy. The generated markup includes no user-supplied HTML, scripts, iframe/embed, forms, or remote server-side link fetches.
- Added CMS publication for saved bio-link pages via the existing provider adapter, workspace/platform-admin boundary, external-action idempotency registry, live-publish confirmation, jurisdiction compliance approval gate, and audit trail. Ambiguous provider outcomes are marked unknown and block unsafe blind retries.
- Added service/API tests for escaping, unsafe destinations, disclosure validation, UTM preservation, tenant isolation, preview, live compliance gating, and idempotent publish replay.
- Updated `docs/skill-parity-matrix.csv`: `distribution/bio-link-deployer` is now partial. Actual connected-provider scope verification and deployed provider UAT remain unverified; a tracked partial state is not a production-ready claim.
- Current skill inventory is 53 rows: 52 partial, 1 not implemented, 0 fully implemented end-to-end. This is not an overall product completion percentage.


## 2026-10-27 implementation update — configured GitHub Pages deployment
- Added environment-backed deployment controls: `GITHUB_PAGES_DEPLOY_EXECUTE` defaults off; repository, branch, relative directory and token are configured on the server. API requests cannot supply an arbitrary target repository or endpoint URL. Configuration validates owner/repository identifiers and rejects Git ref/path traversal.
- Added a fixed-origin GitHub REST integration using the repository's DNS-pinned, redirect-disabled HTTPS client. It verifies the GitHub Pages branch source, resolves the configured root or `docs/` source, creates/updates a single generated `index.html` with the Contents API and uses the current file SHA as an optimistic concurrency guard. Matching remote content is a no-op instead of an extra commit.
- Added platform-admin-only configuration readiness, deployment and read-only reconciliation endpoints. A provider timeout marks the external action outcome unknown; a reconciliation read verifies the exact generated HTML before resolving an uncertain action as published. Non-matching content stays unknown rather than being assumed to have failed.
- Live deployment requires an explicit confirmation, configured execution flag/token/fixed target, a workspace-owned generated bio-link artifact whose SHA-256 matches stored metadata, a valid idempotency key and a current human-reviewed jurisdiction approval for channel `github_pages`. Requests do not accept raw arbitrary HTML or user-supplied GitHub API URLs.
- Added mock-provider unit/API tests for target validation, branch source matching, write/no-op behavior, token redaction, cross-workspace isolation, compliance, idempotency and unknown-outcome reconciliation. Actual remote repository permissions and live Pages UAT still require customer credentials and remain unverified until an actual deployment is run against the configured target.
- Updated the skill parity row to partial because the deployment code and tests now exist; provider credentials/repository configuration and remote UAT are not treated as completed. Current skill inventory: 53 partial, 0 not implemented, 0 fully implemented end-to-end.


## 2026-10-27 implementation update — safe workflow cancellation
- Added `POST /api/workflows/{session_id}/cancel` and a Flywheel UI action for a workspace-owned workflow. Requests are idempotent and audited; the existing workspace scope remains enforced at the runner boundary.
- Cancellation is cooperative and durable rather than an abrupt task kill. An in-flight stage/provider call is allowed to finish; the runner persists its output, marks the workflow cancelled at the next safe checkpoint, and does not start the next stage. This avoids pretending that cancellation rolls back an external action already accepted by a provider.
- Cancellation requests survive an older worker state snapshot, block conflicting HITL resume responses, and are honored after local pause waits and recovery of interrupted/paused jobs. Terminal completed/failed workflows are not overwritten by stale workers.
- Added API/state-machine regression tests for cancellation during a running stage, cancellation before the first stage begins, idempotent cancellation, workspace isolation, and safe checkpoint completion. This is workflow control plumbing; it does not mean every workflow step or external integration is production-live.


## 2026-10-28 implementation update — compliance source catalogue
- Added an authenticated, query-filtered starter catalogue of official regulator, legislation, self-regulatory and selected platform-policy references for US, GB, IN, CA, AU, EU instruments and global Meta/Google Ads policies.
- Added filters for jurisdiction, activity, required category and optional channel. The response distinguishes exact-jurisdiction references from supplemental GLOBAL platform policies and labels each row as requiring review with no legal approval granted.
- Added the compliance UI panel to search catalogue starters and load a title/URL into the evidence draft. The UI explicitly requires the operator to open the current source, confirm applicability/effective status, write a substantive summary, and attest; catalog entries never create evidence or approvals.
- Added unit and API regression tests for national-scope matching, supplemental global policy handling, filters, invalid filter rejection, authorization and non-approval boundaries.
- Scope remains partial: this curated set is not a worldwide law corpus, does not guarantee current legal coverage, and does not automatically refresh regulations. Current product compliance still requires qualified reviewer validation for every activity, actual channel and target jurisdiction.


## 2026-10-28 implementation update — branching email automation builder
- Added workspace-scoped, versioned email automation graphs on the existing content-asset store, avoiding a schema migration. Graphs support email, branch and stop nodes; purchase and engagement conditions; delay offsets; named versions; and deterministic SHA-256 checksums.
- The graph validator checks step types/identifiers, references, acyclicity, reachability and affiliate disclosure declarations. Invalid or cyclic graphs are rejected before persistence.
- Added APIs to create/list/detail, simulate, and human-review automation graph versions. Review decisions are immutable; creating/reviewing a graph does not send or enqueue email. Simulations stop immediately for no-consent/unsubscribed contexts, return the chosen path and schedule offsets, and report zero provider calls/queued/sent messages.
- Added a branching-email UI with a declarative graph editor, saved graph register, sample lead-state toggles, path preview and review notes. The existing consent, scheduler, Resend integration and unsubscribe suppression remain the live delivery implementation.
- Updated `docs/skill-parity-matrix.csv`: the email-automation-builder is now evidenced as partial; graph activation/branch progression inside the live scheduled-email worker, delivery UAT and provider-specific compliance verification remain open. This feature is not described as full automation delivery.


## 2026-10-28 implementation update — source snapshot and claim evidence ledger
- Exposed the existing public-source research brief as authenticated POST /api/content/research-brief; it validates public HTTP(S) URLs, applies workspace generation rate limits, and persists a workspace-owned draft instead of returning an untracked one-off result.
- Source snapshots include stable IDs, fetch times, HTTP/content-type metadata, excerpt SHA-256 hashes and observed numeric strings. The brief prompt requests structured claims, a cited source URL and a verbatim supporting quote.
- Added deterministic quote-to-snapshot matching. A claim receives quote_match only when the cited URL was fetched in this run and the supplied quote occurs in that snapshot after whitespace normalization. Missing sources/quotes remain unmatched; a plain-text model response fails closed to an empty machine-checked ledger.
- Added the research-brief UI to present the narrative, source snapshots, quote matches and unmatched claims in a review-required draft screen. Persistence includes an audit event and source/claim metadata. No publishing is started.
- This is a traceability improvement, not independent truth verification: quote presence does not prove accuracy, currentness, complete context, legal applicability or source reliability. Editorial review and corroboration remain necessary.
- Updated the 53-row skill parity ledger for the content research brief and branching email automation. The email graph runtime now queues the first step for an explicitly selected approved graph, schedules the next node after a successful send, and requires a current email-marketing compliance assessment before each automation email provider request. Provider UAT and production monitoring remain open.


## 2026-10-28 verification follow-up — numeric source observations (fix candidate)
- Current pre-fix candidate `a9a76b66586bf22b4d39762f2a894ae9eb3cef2f` failed both push run [40628516136](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40628516136) and PR run [40628523691](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40628523691). The Python job reported 529 passed, 3 skipped, and one failure in `tests/test_content_research_brief.py::test_research_brief_records_hash_and_matches_only_quotes_from_fetched_sources`.
- Root cause from the exact hosted log: the numeric-observation regex applied a trailing word boundary after the percent-sign alternative, so a source string such as `30%` was not recorded and the test indexed an empty observation list.
- Fix candidate: adjust the pattern so percentage tokens do not require a word boundary after `%`; add regression coverage for percentages, currency, spelled-out percent, plural units, and evidence-hash linkage. This candidate is not verified until the exact-SHA push and PR runs complete and their logs are checked.


## 2026-10-28 verification follow-up — numeric source observations (verified)
- Fix commit: `2677741f65aedc1c9c53a53fa5dd3c412abde273`.
- Exact-SHA push workflow [40634328707](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40634328707) and PR workflow [40634334600](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40634334600) both completed successfully. Push run: all eight jobs succeeded, including PostgreSQL integration and lockfile sync. PR run: all required jobs succeeded; lockfile sync is push-only and was skipped on PR.
- Python job passed 530 tests, skipped 3, with one existing warning. PostgreSQL migration upgrade/downgrade/drift checks and concurrent conversion-reversal/workflow-lease tests passed. PostgreSQL teardown completed successfully; the apparent long-running cleanup step was not a test failure.
- The source-observation regex now captures percentage tokens, currency values, spelled-out percent, plural numeric units and evidence hash linkage. This repair is verified at source/CI level; it does not by itself certify the complete product for production.
- Remaining release gates include the unresolved frontend LGPL license items noted in the source inventory, real staging proxy/egress tests, provider authorization and live UAT, deployment smoke, monitoring/SLO and backup/restore evidence.


## 2026-10-28 targeted-ad safety slice — freshness gate (candidate pending CI)
- Starting verified head: `9085d1af1fd7a7fe23574b1201849713ab5e04f9`; push and PR CI both passed all required jobs at that SHA.
- New candidate in `backend/services/ad_guardrails.py` blocks stop/monitor decisions when the latest provider-verified observation for any creative/platform is older than 24 hours or more than five minutes in the future. Historical daily snapshots remain eligible for campaign totals if each creative/platform also has a fresh latest observation.
- Added regression coverage for stale evidence, fresh latest evidence with older history, and materially future-dated observations. The guardrail still never calls an ad provider and still reports `provider_action_executed=false`; no live campaign is paused by this change.
- This is a candidate until exact-SHA push and PR workflows finish. Provider polling cadence, per-provider freshness contracts and live ad-account UAT remain external/unfinished.
- License note correction: the current frontend build config disables `next/image`; the production dependency verifier rejects installed `sharp`/`@img/sharp-libvips` packages, and CI generates a separate production SBOM checked without exceptions. Build-install inventory notices are not, by themselves, proof that these packages ship in production. Keep owner/legal review as a release governance item, but distinguish it from verified production runtime contents.


## 2026-10-28 targeted-ad freshness gate — verified
- Implementation commit: `3bc5770f3c89561e13686ea9c0023dd1ebbf5d78`.
- Exact-SHA push workflow [40636590192](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40636590192) completed successfully with all 8 jobs passing. Exact-SHA PR workflow [40636595214](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40636595214) completed successfully; all required jobs passed and push-only lockfile-sync was skipped as expected.
- Python suite: **532 passed, 3 skipped, 1 warning**. PostgreSQL integration, frontend production build and final Docker smoke test, security audit, secret scan, repository guard, and AI/RAG checks passed.
- The new freshness gate blocks guardrail decisions when any creative/platform's latest provider-verified observation is older than 24 hours or more than five minutes in the future. Regression tests cover stale evidence, historical snapshots with a fresh latest point, and materially future-dated evidence. The evaluator still performs no remote ad action.
- The prior “unresolved frontend LGPL items” note describes the full build/install inventory, not proof that restricted native packages ship. Current frontend CI passed the production-tree dependency verifier, which checks the actual pruned runtime and fails if `sharp` or `@img/sharp-libvips` is installed; the separate production SBOM is checked without exceptions. Keep legal review and the expiring build-only inventory notice tracked, but do not misstate build-only optional packages as confirmed production runtime contents.
- Remaining release gates include owner decision on public repository visibility/IP exposure, real staging proxy/egress validation, authorized provider scopes and live UAT, deployment smoke, monitoring/SLO, backup/restore, and browser/accessibility acceptance.


## 2026-10-28 implementation update — distributed resource-budget reservation lock
- `backend/services/resource_budget.py` now acquires a PostgreSQL transaction-scoped advisory lock keyed by a fixed resource-budget namespace and the authorized workspace before reading daily/per-niche usage and writing a reservation. This closes the multi-process check-then-insert race for a workspace without changing the public API or tenant accounting.
- SQLite and other non-PostgreSQL development/test dialects do not execute PostgreSQL-only SQL; the existing process-local asyncio lock remains in place for those environments.
- Regression coverage compiles the lock statement for PostgreSQL, verifies namespace/workspace parameters differ by tenant, confirms non-PostgreSQL sessions do not execute advisory SQL, and adds a dedicated PostgreSQL integration test that proves a second database connection cannot acquire the same workspace lock until the first transaction commits. The full concurrent budget check-and-reserve stress test remains outstanding.
- Verified on exact SHA `f97c30d8ff3486da361f93a2de31ac514b5bc671`: push run [40645702983](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40645702983) and PR run [40645707260](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40645707260) both passed all configured jobs. Python suite: 539 passed, 6 skipped, 1 warning; PostgreSQL migration/drift plus integration suite: 6 passed; frontend typecheck/production build, security audit, AI/RAG, repository guard, secret scan and push lockfile-sync passed (PR lockfile-sync skipped as expected). The next slice makes learning use net commission for partial reversals while excluding fully reversed outcomes; exact-SHA verification is pending. Release readiness remains NOT RELEASE READY.


## 2026-10-28 verified resume checkpoint — ad-evidence boundary regression
- Repository/branch were re-inspected before continuing: `AITECHPRODUCTS/Project1`, existing branch `build/omni-affiliate-os-production`; no branch was created and no existing feature was replaced.
- Commit `eae9a1ffdb479ac58418d101002d13f4ce3f0d08` adds regression coverage for the inclusive freshness boundaries in `tests/test_ad_budget_guardrails.py`: an observation exactly 24 hours old remains fresh, and exactly five minutes of future clock skew remains tolerated.
- Exact-SHA PR workflow [40647291464](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40647291464) completed successfully. The Python tests, PostgreSQL migration/concurrency checks, frontend typecheck/production build/final Docker smoke, AI/RAG imports/SBOM, security/dependency/license audit, secret scan, repository/outbound-transport/53-skill guards all completed successfully. The push-only lockfile-sync job was skipped on this PR run as expected. The workflow result proves CI for this SHA, not external provider operation or production readiness.
- Reconciliation from source inspection: `backend/services/s6_s8_analytics.py` currently excludes reversal event rows from conversion counts, excludes fully reversed outcomes through its eligible-status filter, and nets partial-reversal commission against append-only `ConversionLedgerEntry` reversal rows. `tests/test_resource_learning_tenant_scope.py::test_learning_uses_net_commission_for_partial_refunds_and_excludes_full_reversals` covers a partial reversal (1.25 - 0.50 = 0.75) and excludes a fully reversed sale. This behavior is present in the inspected branch source; the prior paragraph saying it was the “next slice” was stale status wording and is superseded by this source reconciliation.
- Current known external release gates remain: real trusted-proxy/egress staging checks; authorized provider scopes and live provider UAT; browser/accessibility acceptance; staged model artifact/license/retrieval proof; deployment health/monitoring/SLO; backup/restore/rollback rehearsal; and owner decision on public repository/IP exposure. Do not mark the product release-ready based on CI alone.
- Next engineering priority: complete the distributed resource-budget reservation stress test against PostgreSQL and continue the requirement backlog on this same branch. Re-run exact-SHA push/PR CI after each resulting change and fix any failure before advancing.


## 2026-10-28 verified checkpoint — PostgreSQL reversal-aware learning regression
- Test commit: `899265bb9cba7db973b7b91d0aa95c7e2052d34f`, adding `test_postgres_learning_nets_partial_reversal_and_excludes_reversed_outcomes` to `tests/test_conversion_webhook_postgres.py`, which is already included in the dedicated PostgreSQL integration CI command.
- Exact-SHA push workflow [40648503523](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40648503523) completed successfully with all jobs green, including lockfile sync. Exact-SHA PR workflow [40648508574](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40648508574) completed successfully; all required jobs passed and the push-only lockfile-sync job was skipped as expected.
- PostgreSQL integration log: **7 passed in 1.69s** across the configured conversion-reversal, durable-workflow and resource-budget integration tests. The added test proves persisted learning stores one eligible sale and net commission of 0.75 from a 1.25 original commission less a 0.50 append-only reversal; the reversal row is not a second sale and the fully reversed outcome is excluded.
- This is source and hosted-CI evidence only. It does not prove production provider ingestion, live revenue accuracy, or deployment readiness.
- Next unblocked product-acceptance gap: real browser journey/accessibility verification for the existing Next.js workspace flows. Build repeatable browser tests without replacing existing UI or treating TypeScript/build success as browser acceptance. Keep the external staging/provider/model, deployment/monitoring, backup/restore, and repository visibility/IP owner gates explicit.


## 2026-10-28 verified checkpoint — Chromium browser UAT and failure remediation
- Implementation commit `453d210043f04e76590bfebcd2540698f17ac860` added a pinned Playwright 1.64.1 browser-UAT job and two production-Next.js Chromium tests for the governed skill-package page and ad-budget guardrails.
- The first push run [40649447015](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40649447015) correctly exposed a test defect: unscoped `get_by_role("alert")` matched both the app validation error and Next.js's route-announcer element. No product feature failed. The test was fixed to scope the locator to `main`; browser API mocks were also changed to same-origin, and the pinned browser test environment now installs `pytest-asyncio==1.3.0` to match the repository pytest configuration.
- Corrective commit: `8887cf400895abac25b03cbb87201878f5d93594`. Exact-SHA push workflow [40649878346](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40649878346) and PR workflow [40649885162](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40649885162) both completed successfully with all required jobs green. The Chromium browser job passed **2 tests** (push 1.49s, PR 1.95s); Python, PostgreSQL, frontend/Docker, AI/RAG, security/SBOM, repository guard, and secret scan also passed. Push-only lockfile sync passed; PR skipped it as expected.
- Browser acceptance is now automated for these two routes, not the full product. It uses mocked API responses to verify browser rendering, keyboard focus, invalid-input handling, and read-only spend-safety messaging; it does not replace backend integration tests or live provider UAT.
- Next engineering priority: extend browser coverage to authenticated workspace journeys and lead/content/offer workflows using isolated test data and real API contracts. Keep external provider UAT, staged model artifact/license/retrieval proof, deployment health/SLO, backup/restore/rollback rehearsal, and repository visibility/IP owner decision open until independently verified.


## 2026-10-28 verified checkpoint — real authenticated browser journey
- Browser test implementation is on commit `97bc4551de400929635206a462861460d1e52b6e`. The Chromium job now boots the real FastAPI app against a disposable SQLite database, applies Alembic migrations, configures a test-only administrator to disable the non-production local-development fallback, registers a unique user, validates the signed session via `/api/auth/me`, verifies persisted workspace membership via `/api/workspaces`, and opens the authenticated dashboard.
- Failure remediation trail: `da63c7fe35eee2ecd045e399c8d81694ebe1f830` exposed the local-development fallback in the test fixture; `3e4f8d48d8b6fcbd7b958954e82f116e65482af2` configured test-only administrator credentials; `97bc4551de400929635206a462861460d1e52b6e` scoped the duplicate email assertion to the dashboard header. These were test/fixture issues; the product API registration and workspace creation behaved as expected.
- Exact-SHA push [40651721191](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40651721191) and PR [40651726705](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40651726705) both completed successfully with all required jobs green. Browser UAT passed **3 tests** in 3.02s (push) and 4.36s (PR); Python, PostgreSQL, frontend/Docker, AI/RAG, security/SBOM, secret scan and repository guards also passed. Push lockfile-sync passed; PR skipped it as expected.
- Current browser acceptance comprises two UI-level tests with controlled API fixtures plus one real API/session/workspace journey. It does not yet cover content generation, offer validation, lead capture, or distribution through a browser.
- Next unblocked engineering slice: extend the authenticated browser journey to one safe draft-generation workflow and one offer-validation workflow using real API contracts and isolated workspace data. External live-provider UAT, staged model artifact/license/retrieval proof, deployment health/SLO, backup/restore/rollback rehearsal, and repository visibility/IP owner decision remain open release gates.


## 2026-10-28 verified checkpoint — real content and offer draft flows
- Browser test commit: `58c5f7b94788771017812080a419bcd72b590566`. The authenticated Chromium journey now calls the real SQLite-backed FastAPI API to generate/persist an infographic SVG draft and create a workspace-scoped merchant-offer draft.
- Assertions verify the infographic remains review-required, publishing has not started, and no external image provider was used. Offer assertions verify draft status, unverified terms/seller authorization, activation disabled, network approval `not_configured`, and no provider submission or marketplace listing.
- Exact-SHA push [40652912071](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40652912071) and PR [40652918364](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40652918364) both completed successfully with all required jobs green. Browser suite passed **3 tests** in 4.74s (push) and 5.03s (PR); Python, PostgreSQL, frontend/Docker, AI/RAG, security/SBOM, repository guard and secret scan passed. Push lockfile sync passed; PR skipped it as expected.
- Browser UAT now covers real registration/session/workspace membership, review-only infographic creation, and offer packet creation with safe non-activation defaults. It still does not cover lead capture/CRM, distribution queueing, or external provider UAT.
- Next engineering slice: add an authenticated browser test for consent-aware lead capture/CRM persistence and verify opt-in/suppression semantics through the real API. Keep external provider UAT, staged model artifact/license/retrieval proof, deployment health/SLO, backup/restore/rollback rehearsal, and repository visibility/IP owner decision open.


## 2026-10-28 continuation — browser UAT repair checkpoint
- Re-inspected the live PR #1 head and exact hosted Actions run before changing code. Branch head at this checkpoint: `d469b372041f6b665b73afc89f6b01397075be24`; PR #1 remains open/draft/unmerged.
- Latest prior PR run `40666356431` failed only in `browser-uat`: `test_distribution_queue_is_persisted_review_gated_and_never_claims_sent` timed out waiting for the distribution queue POST response after submitting the UI form (4 other browser tests passed; the remaining configured jobs passed).
- Added a browser-compatible idempotency-key helper to `frontend/app/distribution/page.tsx`: use `crypto.randomUUID()` when available and a `crypto.getRandomValues()` fallback otherwise. This is a compatibility hardening hypothesis, not a confirmed root cause until the new hosted browser UAT run finishes.
- Repair commit: `e4333ae0aadfa8996f1011ca08d51092a3e06d71`. Exact-commit PR CI run: [40667431166](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40667431166). At the time of this entry the run was pending; do not mark the repair verified until all jobs, especially browser-uat, complete successfully.
- Requirement-source recovery: the recent 28 October handoff/audit and 27 October master handoff, source inventory, second-pass audit, and branch requirements/traceability/status ledgers were inspected. The original user requirements remain the authority for full S1–S8 scope; repeated archived files must be deduplicated by content hash. The separate newer already-live application ZIP remains absent from the current Library inventory and must not be claimed as reviewed.
- Release state remains **NOT RELEASE READY**. Hosted CI does not prove provider authorization, production deployment, backup/restore, end-to-end skill parity, or legal clearance. Reconcile the current license-policy report and owner visibility decision before any release recommendation.



## 2026-10-28 continuation — exact conversion-ledger money parsing

- Scope: S6 signed conversion webhook parsing, a correctness gap called out by the 27 October audit. The webhook adapter previously converted validated `Decimal` values to binary `float` before the ledger route converted them back to `Decimal`, which could lose precision for high-precision amounts.
- Implementation: `backend/adapters/webhook.py` now returns normalized `Decimal` amounts, rejects non-finite/negative values, rejects amounts beyond `Numeric(18, 6)`, and rejects values that would require rounding beyond six fractional digits. This aligns parser output with the append-only ledger precision contract and avoids silent database rounding.
- Regression coverage: `tests/test_webhook_adapter.py` asserts exact six-place values and rejection of excess scale and Numeric(18, 6) overflow, while retaining invalid amount, signature, event-ID, and normalization coverage.
- Commits for this slice: parser `f69e49b0346e6d9bfdc4f6ffb9522143e551e63f`; regression tests `ec9dee0c13a123b3571ceb86facb1004a11ab383`.
- Verification: the exact-SHA hosted CI run was observed as pending with no job results returned at the time this entry was prepared. **Do not count this slice as CI-verified until the current branch head's Python, PostgreSQL, browser, frontend, AI/RAG, security and repository-guard jobs are inspected.** Local execution of the repository suite was not available through this connector session.
- Remaining S6 gaps: provider-specific signature vectors and authorization, late/replay/partial-reversal contract coverage, currency-specific minor-unit policy, PostgreSQL ledger immutability/reversal checks on the exact new SHA, provider statement reconciliation and finance UI/browser acceptance.
- Product release remains **NOT RELEASE READY**; this change does not establish provider connectivity, legal clearance, deployment health, backup/restore or full S1–S8 completion.




## 2026-10-28 verification follow-up — decimal scale regression resolved

- The first hosted run after introducing exact Decimal parsing exposed a response-compatibility regression: the partial-reversal API returned `"0.750000"` instead of the existing `"0.75"` (and `"7.50"` instead of `"7.5"`). This was caused by preserving Decimal scale in the response string, not by incorrect ledger arithmetic.
- Fix: `backend/main.py` now formats remaining balances with `format(value.normalize(), "f")`, preserving the existing response contract while the ledger still stores exact Numeric values. `backend/adapters/webhook.py` validates six-place representability but returns the original Decimal value rather than quantizing its exponent.
- Exact candidate commit: `658142f6bb98617f635ea452ebda8ee0e7841aa1`.
- Exact-SHA GitHub Actions PR run [40670389433](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40670389433) completed **successfully**: Python, PostgreSQL integration, frontend/Docker, AI/RAG, security audit, secret scan, repository guard, and browser UAT all passed. `lockfile-sync` was skipped on the PR event as configured. The earlier failing run was `40670198989`; its Python/PostgreSQL failure was traced to the response-scale mismatch above, and the follow-up run passed after the fix.
- This is verification of the exact code candidate, not production certification. The documentation commits that follow this note trigger new checks and their exact current head must also be inspected. External provider authorization, license/legal release decision, staging, backup/restore/rollback and production health remain open.


## 2026-10-28 S6 commission reconciliation precision — exact-SHA verification

- **Bug fixed:** `backend/services/commission_reconciliation.py` previously quantized every candidate amount to cents. That could make distinct amounts (for example, `12.501` and `12.50`) look equal during reconciliation.
- **Implementation:** reconciliation now parses exact `Decimal` values, accepts only values representable by the ledger's `Numeric(18, 6)` range/scale, requires an explicit three-letter currency code rather than silently assuming USD, and compares exact values without rounding. Candidate matching remains review-only; it never verifies or confirms a payout.
- **Regression coverage:** four tests cover distinct fractional amounts, exact six-place matching, rejection of excess precision, and missing currency. Existing ambiguity, reversed-commission, network/currency matching, and non-confirmation tests remain.
- **Code commits:** service `dfa98507075ba53e9d36e5bfb400f5fa910add2e`; tests `d10258653c4e400cf483c006af47a64f1d3bcbaf`.
- **Exact-SHA hosted CI:** push run [40674307123](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40674307123) and PR run [40674316496](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40674316496) completed successfully on `d10258653c4e400cf483c006af47a64f1d3bcbaf`. Python: **558 passed, 7 skipped, 1 warning**; PostgreSQL integration, frontend production build, AI/RAG, security audit, secret scan, repository guard and browser UAT passed. Push lockfile-sync passed; PR lockfile-sync was skipped by its configured event condition.
- **Scope boundary:** this does not establish provider account authorization, provider-specific payout evidence, currency-specific statutory minor-unit rules, production deployment, or overall S1–S8 release readiness.


## 2026-10-28 commission reconciliation status normalization — candidate
- Corrected a status-spelling edge case in `backend/services/commission_reconciliation.py`: evidence statuses such as `Pending Verification` and `matched to conversion` are normalized to stable underscore-separated keys before state routing. This avoids treating a pending evidence row as already reviewed solely because of case/spacing differences; reviewed rows remain closed to automatic rematching.
- Added two regression tests for pending and reviewed status variants in `tests/test_commission_reconciliation.py`.
- Service commit: `91976a3e8fdbe8aab1b56ab362bcabf7504c29bf`; test commit: `38cf64a294fec308b6c9dfa5a2d3dfe978f7e70c`.
- **Candidate only until exact-current-HEAD push and PR CI complete.** No live payout state is changed. Existing staging/provider/production release gates remain open.


## 2026-10-28 commission reconciliation reversal-status hardening — candidate
- Fixed whitespace-only evidence status handling: blank/whitespace values now use the documented `pending_verification` default rather than becoming an unknown reviewed status.
- Added conservative explicit aliases for fully reversed/refunded, charge-back, and commission-reversed conversion statuses. These aliases are normalized first and excluded from candidate matches; unrelated statuses are not guessed to mean reversal.
- Regression coverage: whitespace-only evidence status continues through review matching; explicit reversal variants never become commission candidates.
- Commit: [`32f7f01a4b180f54a7fd7d0c8dc06e8c72acb969`](https://github.com/AITECHPRODUCTS/Project1/commit/32f7f01a4b180f54a7fd7d0c8dc06e8c72acb969). Exact-head push run [40678582977](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40678582977) and PR run [40678593095](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40678593095) both completed successfully. Python, PostgreSQL integration, frontend production/Docker, AI/RAG, security audit, secret scan, repository guard, and browser UAT passed; PR lockfile-sync was skipped by its configured event condition. Reconciliation remains review-only and never confirms a payout.


## 2026-10-28 checkpoint — verified commission-status hardening and current build boundary

- Exact implementation commit: `32f7f01a4b180f54a7fd7d0c8dc06e8c72acb969`.
- Exact push CI: [40678582977](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40678582977) — completed successfully.
- Exact PR CI: [40678593095](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40678593095) — completed successfully. The PR lockfile-sync job was skipped by the workflow's configured condition, not failed.
- Code slice: whitespace-only reconciliation evidence status defaults to pending verification; explicit fully-reversed/refunded, charge-back and commission-reversed status variants are excluded from candidate matching. Matching remains review-only and no payout is confirmed.
- No overall product-completion percentage is inferred from the 53-row skill parity inventory. Production release remains blocked by provider authorization/contracts, full tenant/SaaS acceptance, legal/license decisions, staging deployment, restore/rollback rehearsal, operational monitoring and full browser/accessibility UAT.
