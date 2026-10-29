# OmniAffiliateOS — Built Work and Remaining Production Build

**Snapshot date:** 29 October 2026  
**Repository:** [AITECHPRODUCTS/Project1](https://github.com/AITECHPRODUCTS/Project1)  
**Existing implementation branch:** `build/omni-affiliate-os-production`  
**Previous verified base:** [`ca24c8d595f63b5593ce67e7d8db566f343d81cd`](https://github.com/AITECHPRODUCTS/Project1/commit/ca24c8d595f63b5593ce67e7d8db566f343d81cd)  
**Release status: NOT RELEASE READY.**

This document is a practical handoff for continuing the implementation. It distinguishes existing code and automated verification from provider-connected, staging-verified and production-live behavior.

## Commission projection history increment (test correction in current candidate; CI pending)

The initial exact-SHA test run found a test assertion that assumed insertion order even when SQLite timestamps tie. The test now checks the endpoint's deterministic `(created_at DESC, id DESC)` order and verifies both records across the first two pages; application ordering remains unchanged. The corrected candidate must pass new exact-SHA push and PR workflows.

The calculator now retrieves saved workspace projections through `GET /api/research/commission-projections`, sorted newest first and paginated with bounded inputs. It returns only records owned by the active workspace, plus parsed result and assumption metadata, and the UI loads/refreshes saved history and allows reopening a stored result after navigation or page reload. API tests cover pagination and cross-workspace isolation; Chromium tests cover refresh and restore. This is not a provider data feed and does not authorize publishing or payout. Await exact-SHA push/PR checks for this increment.

## Previous user-facing calculator journey

The commission calculator is now available at `/commission-calculator` and `POST /api/research/commission-calculator`. It authenticates through the existing workspace session, validates traffic/rate/program assumptions, writes a review-required workspace draft, and records an audit event. The UI compares up to ten programs, restricts ranking to a single currency, and lets users export the JSON report. It does not fetch provider metrics, claim earnings or perform payout operations. API and Chromium UAT coverage has been added; this new head must pass exact-SHA push and PR CI before the increment is marked verified.

## Previous code increment

Added the executable allowlisted handler `research.commission_calculator` for S1 affiliate earnings projections. It calculates expected clicks/conversions, commission per conversion and 12-month payout projections from explicitly provided visitor counts, click-through and conversion-rate assumptions, payout rules, currency, average order value and recurring duration. All money calculations use bounded Decimal arithmetic and fixed-point strings. Comparisons reject mixed currencies and results are sorted only within one shared currency. Recurring cohorts use the submitted payment duration and are labelled as pre-churn estimates.

The handler does not assume market benchmark CTR/CVR or visitor counts, fetch provider metrics, promise earnings, or transfer money. Outputs explicitly mark the estimates as caller-supplied assumptions and require human review. It is now exposed through Skill Studio presets and the API runtime contract, with a tested package create/review/execute path and browser preset acceptance test.

Also hardened the skill-package schema validator: it now validates every value in an array/object, not just the first 100 entries/properties. Regression tests cover malformed values beyond that former cutoff and explicit boolean/NaN/infinity rejection. A follow-up code review also ensures unhashable reward/commission type inputs are rejected as controlled validation errors rather than uncaught type errors.

## Previous checkpoint's additive feature


The governed skill runtime now includes `research.offer_term_change_review`, reusing the existing offer-term normalizer, field-level comparator and SHA-256 fingerprint:

- Compares the eight declared offer-term fields: terms version, commission type/value/currency, cookie and attribution windows, allowed regions and restricted traffic sources.
- Normalizes currency, commission decimal precision and region/traffic-list ordering before comparison.
- Emits a first-snapshot baseline when no previous snapshot exists, rather than fabricating history.
- Flags changed fields and requires revalidation on detected changes.
- Treats every submitted term record as untrusted: source attestation and network approval remain false, human review is required, and automatic activation is prohibited.
- Rejects unexpected keys, malformed region/traffic lists, ambiguous snapshot flags, invalid commission amounts and claims that try to mark the provider as verified.

Regression coverage includes material changes, semantically equivalent term normalization, first-snapshot behavior, negative payloads and execution as a governed skill-package fixture. This does **not** fetch an affiliate network, authenticate a merchant, determine account eligibility or approve/activate offers.

## Additive advertising performance reporting increment (CI pending)

- Added inclusive `from_date` and `to_date` filters to `GET /api/ads/observations` and `GET /api/ads/performance`. Both use UTC calendar dates, expose the applied date bounds and timezone, and reject reversed ranges with HTTP 422.
- Filters are applied to the persisted `observed_at` timestamp before summaries are calculated; the existing query limit and evidence-status semantics remain intact. Unverified operator-entered observations are still clearly labelled and cannot become optimization-eligible through date filtering.
- Added API regression coverage for same-day inclusion, prior/next-day exclusion, response date metadata, and invalid reversed ranges in `tests/test_ad_performance.py`.
- This improves reporting on data already stored; it does **not** connect advertising accounts, fetch provider spend, or verify imported evidence. Exact-SHA push and pull-request workflows must complete before this increment is marked verified.

## What is already implemented in the branch

- **Application foundation:** FastAPI backend, SQLAlchemy persistence, Alembic schema migrations, workspace-scoped authorization/audit patterns, Next.js/TypeScript dashboard, Docker/Compose and CI workflows.
- **S1 research/offers:** offer discovery foundations and a configured OpenAffiliate directory sync, evidence-aware metrics, merchant offer/review records, term snapshots, bounded source fetching, hash comparisons and reviewed material-change controls.
- **S2–S3 content and SEO:** draft/content-generation helpers, content atomization, research briefs with source snapshots, SEO audit/internal-linking helpers, content-decay/moat tools, landing/funnel drafts and a local RAG foundation.
- **S4 leads and consent:** workspace-scoped lead capture, consent-event ledger, unsubscribe/suppression, configurable double opt-in, scheduled email queue, email automation graph handling and webinar-registration foundations.
- **S5 distribution:** review-first queue, provider/CMS boundaries, idempotency and selected static/bio-link deployment paths. Native provider credentials/scopes and live account UAT remain separate requirements.
- **Mandatory advertising:** ad planning and creative/audience variants, budget guardrails, verified-evidence requirements for performance recommendations, signed collector ingestion and no automatic remote campaign action without an authorized provider contract.
- **S6 finance/analytics:** signed conversion intake, idempotency, append-only commission observations, reversal handling, currency separation and review-oriented reconciliation.
- **S7–S8 automation/learning:** persisted workflow checkpoints/leases/recovery/cancellation, human approval boundaries, resource budget controls and review-only learning primitives.
- **Skill runtime:** seven deterministic, code-owned handlers plus a declarative-only option; includes extractive summary, keyword extraction, evidence-dependent offer metrics, commission projections, offer-term change review, review-only ad guardrails and ROAS review. User-authored Markdown/instructions are not executed. Runtime and parity work is still partial.

## Verified CI for the current Skill Studio/API integration

Exact-SHA push [40812412185](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40812412185) and PR [40812420246](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40812420246) both completed successfully on `06a5bbd86aa21ce2a85729c5438ee4991b45e421`. Python: **725 passed, 7 skipped, 5 warnings**. PostgreSQL integration, frontend TypeScript/production build/Docker, AI/RAG dependency and SBOM checks, security audit, secret scan and repository guard passed. Browser UAT reported **8 passed** on each run. Push lockfile-sync passed; PR lockfile-sync was skipped by its configured PR-event condition.

These runs verify the deterministic handler and its Skill Studio/API wiring, not live provider authentication, account eligibility, provider-attested metrics, external ad actions, payouts or production deployment.

## Previous CI checkpoint

Exact-SHA push [40811838953](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40811838953) and PR [40811844496](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40811844496) passed on `316c1c5d9ee41f6a64a4bae4e30d23f9cfa22a6c`, covering the commission calculator backend and schema traversal hardening before the Skill Studio/API integration.


## Highest-priority remaining production work

1. **Real affiliate network integrations:** implement selected official APIs/OAuth, least-privilege scopes, provider-specific mapping, rate limits/backoff, token refresh/revocation, provider contract/sandbox tests and evidence-backed provider status. A catalog, configured directory or stored URL is not network verification.
2. **Native paid-ad connectivity:** provider-attested spend/impression/click/conversion data, authorized launch/pause/budget-change contracts, approval records, remote IDs, idempotent retries, reconciliation and kill-switch UAT. No campaign mutation or paid spend should be enabled without explicit authorization.
3. **End-to-end user journeys:** content version/edit/review/publish; source-grounded claims and editorial evaluation; technical SEO/Search Console; actual CMS/social/email/CRM delivery; form-to-consent-to-CRM lifecycle; commission reconciliation and all supported failure/recovery paths.
4. **53-skill parity:** each skill needs a real service/API/UI implementation, input/output contracts, negative tests, dependencies, browser acceptance and evidence. At the last recorded parity checkpoint the 53 skills were partial; handler/registry presence alone is not completion.
5. **Security and tenancy:** complete cross-tenant negative tests through every API, worker, queue, cache, export and credential path; verify workspace roles versus Platform Super Admin; perform PostgreSQL concurrency and load/soak tests.
6. **Privacy, legal and licensing:** implement governed data-subject deletion/unlink/retention; review jurisdiction-specific disclosures and email policy; resolve recorded build-license exceptions; decide whether the repository's public visibility is appropriate for a proprietary product.
7. **Operations/release:** real provider secret configuration, staging deploy and health checks, backup/restore, migration rollback, queue/dead-letter operations, monitoring/alerts/SLOs, incident runbooks, accessibility testing and a release candidate whose deployed SHA is verified.

## Production status

Do not assert a completion percentage until feature-level acceptance criteria and denominator are reconciled. Product release status remains **NOT RELEASE READY**. No external provider/account, campaign, publishing action, payout or production deployment is claimed as verified by this document. The separate newer ZIP described as an already-live app was not in the inspected Library inventory; do not claim that its code was reviewed or ported.


## 2026-10-29 additive fix — qualification queue pagination (verification pending)

- Found a real user-facing limitation in the new offer qualification workflow: the API supported bounded offset pagination, but the page always requested the first 50 rows and exposed no way to reach later offers.
- Updated the qualification page to request explicit offsets, retain the active filter across navigation, display the current range/total, and disable Previous/Next at the correct boundaries. Refresh and post-save reload retain the current offset; filter changes reset to the first page.
- Added Chromium browser acceptance coverage for a 52-offer queue, next/previous navigation, filter preservation and absence of UI errors. This is an additive UI/test change; API contracts and qualification decisions are unchanged.
- Candidate parent before this change: [`03bdbb6f60a6e8b9f86472a86f17d0156214dadc`](https://github.com/AITECHPRODUCTS/Project1/commit/03bdbb6f60a6e8b9f86472a86f17d0156214dadc). Exact-SHA push/PR CI is required before marking the fix verified. Release remains **NOT RELEASE READY**.

## 2026-10-29 additive fix — qualification queue stale-page recovery (verification pending)

- Follow-up inspection found a second edge case in the S1 offer qualification review queue: after a decision removes the final record from the current filtered page, reloading the same offset can return an empty page while earlier matching records still exist. This is especially relevant when reviewing the final item on a later page.
- Updated `frontend/app/offers/qualification/page.tsx` so a reload whose offset is now beyond the filtered total is clamped to the last valid page (or offset zero for an empty queue). The request retains the active filter, and this changes navigation only—not review decisions, provider evidence, or activation permissions.
- Added `test_offer_qualification_returns_to_valid_page_when_last_filtered_item_is_removed` in `browser_tests/test_workspace_browser_smoke.py`. The browser test models a two-item, one-item-per-page queue, qualifies the last item, and checks that the UI returns to the remaining item without a UI alert.
- The existing 52-offer pagination acceptance test remains in place.
- Candidate code commit: `871d6d30e0852163cdf147e7410e9203a10d1c5f`. At documentation time, the exact-SHA PR workflow `40825056412` was still in progress and the exact-SHA push workflow `40825051280` was queued. Earlier runs for superseded commits were cancelled when new commits were pushed; none of those cancelled runs is evidence of a pass. This entry must not be marked verified until both current-commit workflows complete successfully, including browser UAT where configured.
- Release remains **NOT RELEASE READY**. No provider integration, affiliate-network approval, paid campaign action, production deployment, or live external delivery is claimed as verified.


## 2026-10-29 verified paid-ad snapshot conflict safeguard

- Candidate change groups provider-verified observations by platform, creative and UTC day, then chooses the latest timestamp for each group. If multiple latest records share the same timestamp but disagree on spend, commission, impressions, clicks, conversions or currency, the evaluation returns `blocked_ambiguous_provider_snapshots`.
- Exact duplicates remain deduplicated. Ambiguous evidence returns no breach recommendations and cannot trigger the guardrail latch. Regression tests cover both conflicting and identical duplicate records.
- This is not provider authentication or live campaign control. It does not execute a remote pause, change budgets, authorize spend, or certify source authenticity.
- Current candidate before this slice: `06a47498fc6cba7186884cf4ccbc4962042f7f39`. The new candidate must be verified with exact-SHA push and PR Actions, including Python, PostgreSQL, frontend, security, repository guard and browser UAT. Release remains **NOT RELEASE READY**.


## 2026-10-29 verified operator-visible ad snapshot conflict alert

- The /ads/guardrails page now renders a semantic alert for the blocked_ambiguous_provider_snapshots evaluation, showing the affected platform/creative, UTC day, conflicting metric fields and number of same-timestamp records.
- The alert explicitly states that evaluation is blocked until reconciliation and that no remote campaign action was executed; the raw evaluation payload remains available for debugging.
- Added Chromium browser acceptance coverage for the rendered warning. Exact-SHA push [40829287184](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40829287184) and PR [40829292836](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40829292836) passed; browser UAT was 16 passed, and all configured jobs passed. Live provider authentication/action and production release remain unverified.


### Browser-test correction for the operator-visible conflict alert

- First UI candidate: `4d6f9e3fb71018b8ff3544e8218ed96b25d85c91`. Python (746 passed, 7 skipped), PostgreSQL, frontend, security, AI profile, secret scan and repository guard passed. Browser UAT failed one new test because a generic alert selector matched both the conflict warning and the Next.js route announcer; 15 other browser tests passed.
- Corrected the test to scope its content assertions to `main [role='alert']`, retaining all warning/safety assertions. No runtime code was changed for this test-only correction. The new exact-SHA push and PR workflows must pass before the UI increment is verified.


## 2026-10-29 verified lead consent evidence UI

- The lead list now exposes the stored email confirmation timestamp and consent source. Each lead can lazily load its workspace-scoped consent event history; the view shows the exact captured consent text, purpose, policy version, source/channel and event time, and labels the history read-only.
- Added an API regression and Chromium acceptance for the display. Exact-SHA push [40830226995](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40830226995) and PR [40830233016](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40830233016) passed: Python 747 passed, 7 skipped, 5 warnings; browser UAT 17 passed; PostgreSQL, frontend, security, AI profile, secret scan and repository guard passed. Push lockfile-sync passed; PR lockfile-sync was skipped. This does not mutate consent or send email; production email provider delivery and jurisdictional policy acceptance remain separate gates.


### Consent-history UI compile correction

- First candidate `5f2696434be2d1de75e38d904658d176cb5279bf` passed Python (746 tests), PostgreSQL, AI profile, repository guard and secret scan, but frontend TypeScript and the security-audit job failed because the generated page contained literal `\\n` sequences in the new state declaration. Browser UAT was skipped as a dependent job.
- Corrected the state declaration to real source lines and added the `Lead`, `ConsentEvent` and `ConsentHistory` TypeScript fields that the earlier escaped-newline replacement had not applied. Fresh exact-SHA push and PR verification is required; the feature remains unverified until all jobs pass.


## 2026-10-29 verified workspace-scoped lead pagination

- The leads API now supports bounded limit/offset pagination and returns a workspace-scoped total count. Ordering is stable for equal timestamps; the frontend shows total count and page navigation, clarifies that search applies to the current page, and recovers to the last valid page when records are deleted while viewing a later page.
- Added API regression coverage and browser acceptance that navigates to page two and simulates the only record being deleted before refresh. Exact-SHA push [40831057432](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40831057432) and PR [40831064003](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40831064003) passed: Python 748 passed, 7 skipped, 5 warnings; browser UAT 18 passed; PostgreSQL, frontend, security, AI profile, secret scan and repository guard passed. Push lockfile-sync passed; PR lockfile-sync was skipped.


### Pagination browser-fixture correction

- The first pagination candidate included a consent-history browser fixture that matched `/api/leads` only when the URL had no query string. Since the new UI requests `/api/leads?limit=50&offset=0`, the mock must match the URL path before `?`. Corrected the fixture; this does not change production code. The corrected candidate needs exact-SHA push/PR UAT.


## 2026-10-29 verified cross-page lead search

- Added bounded server-side email/resource search to the workspace-scoped lead API and separate client-side UTM filtering for the current page. The UI makes those scopes explicit and resets pagination when global search changes.
- Added API query assertions and browser acceptance for global search plus current-page UTM filtering. Exact-SHA push [40831713023](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40831713023) and PR [40831720664](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40831720664) passed: Python 748 passed, 7 skipped, 5 warnings; browser UAT 19 passed; PostgreSQL, frontend, security, AI profile, secret scan and repository guard passed. Push lockfile-sync passed; PR lockfile-sync was skipped.


## 2026-10-29 global UTM attribution search (verification pending)

- Global lead search now includes allowlisted first-touch and last-touch UTM dimensions, so campaign/source values can locate leads across pages without relying on the current-page-only quick filter. Workspace scope and bounded pagination remain applied to both count and row queries.
- Updated browser acceptance to search by UTM source; exact-SHA push and PR CI is pending.
