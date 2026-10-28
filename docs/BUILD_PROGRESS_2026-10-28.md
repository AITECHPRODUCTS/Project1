# OmniAffiliateOS — build checkpoint and remaining production work

**As of:** 28 October 2026  
**Repository:** https://github.com/AITECHPRODUCTS/Project1  
**Working branch:** build/omni-affiliate-os-production  
**Latest verified code candidate:** [052fc71ac422b357caeef47fb44a6bffdbcabe4e](https://github.com/AITECHPRODUCTS/Project1/commit/052fc71ac422b357caeef47fb44a6bffdbcabe4e)  
**Release status:** NOT RELEASE READY  

## Latest verified checkpoint — bounded source ratings and persisted affiliate catalog (2026-10-28)

Code: [052fc71ac422b357caeef47fb44a6bffdbcabe4e](https://github.com/AITECHPRODUCTS/Project1/commit/052fc71ac422b357caeef47fb44a6bffdbcabe4e) adds a five-star bound to the existing OpenAffiliate metric normalizer. Ratings outside 0–5, malformed, boolean, negative, non-finite or overflowing inputs remain unknown rather than being displayed as valid ratings. The regression suite covers 5.01, 100 and valid 5.0. The prior verified catalog UI at [1fc52aa8da1a6b7b4097ce37df820710d1fd7abb](https://github.com/AITECHPRODUCTS/Project1/commit/1fc52aa8da1a6b7b4097ce37df820710d1fd7abb) exposes persisted `GET /api/offers` with filters, null-last sorting, pagination, explicit “provider claimed — not independently attested” labels, unknown metrics, HTTPS-only links and Chromium acceptance.

Exact-SHA [push CI 40738666906](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40738666906) and [PR CI 40738675557](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40738675557) passed. Python: **690 passed, 7 skipped, 5 warnings** on PR. Browser UAT: **6 passed** on each. PostgreSQL, frontend/Docker, AI/RAG SBOM and license inventory, security/dependency audit, secret scan, repository guard and push lockfile sync passed; PR lockfile sync was skipped by the configured event condition.

These slices improve local data quality and the persisted-catalog workflow; they do not authenticate source data or complete live marketplace research. Native provider authorization, freshness/terms/eligibility verification, full 53-skill S1–S8 acceptance, legal/licensing disposition and staging/deployment/restore gates remain. Status: **NOT RELEASE READY**.


## Previous verified feature slice — 2026-10-28 S1 offer metrics runtime

Feature commit [440d378d7588081f6e072e18e35bd7573543f89a](https://github.com/AITECHPRODUCTS/Project1/commit/440d378d7588081f6e072e18e35bd7573543f89a) added allowlisted `research.offer_metrics` to the governed runtime with regression and executable package-fixture tests. It reuses existing input validation and preserves unknown measurements; it does not scrape sources or call providers.

Exact verification snapshot: [ca03d16af65c11f93f185fd7e2f33d3ad9598d41](https://github.com/AITECHPRODUCTS/Project1/commit/ca03d16af65c11f93f185fd7e2f33d3ad9598d41). [Push run 40723769566](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40723769566) and [PR run 40723782320](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40723782320) both completed successfully. Python: **648 passed, 7 skipped, 5 warnings** on each run. Browser UAT: **5 passed** on each run. PostgreSQL, frontend/Docker, AI/RAG SBOM, dependency/security audit, secret scan and repository guard passed; push lockfile sync passed and PR lockfile sync was skipped by design. No failed jobs were present.

The 53-skill catalogue remains partial, no external provider was newly connected, and production remains blocked by the release, authorization, staging/deployment and operational acceptance gates below.


## 2026-10-28 verified checkpoint — double opt-in and truthful signup outcomes

- Verified feature/test SHA: `22b64068cb06d5085761aad986e3787a59634981`. [Push CI run 40713741377](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40713741377) and [PR CI run 40713751355](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40713751355) both completed successfully on feature/test checkpoint `22b64068cb06d5085761aad986e3787a59634981`. Python: **619 passed, 7 skipped, 5 warnings**. PostgreSQL migration/concurrency, frontend typecheck/build/final Docker smoke, AI/RAG, security/SBOM, secret scan, repository guard and browser UAT passed. Push lockfile-sync passed; PR lockfile-sync was skipped by event condition. The predecessor feature-code push/PR attempt exposed two test assertions comparing raw HTML with rendered copy; `22b6406` fixes the assertions to decode HTML entities while keeping production escaping intact.
- Migration 0026 adds a per-lead email-confirmation timestamp plus expiring confirmation records; the feature is controlled by `EMAIL_DOUBLE_OPT_IN_REQUIRED` and is off by default. It requires configured `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, and a valid public HTTPS callback URL before relying on real delivery.
- Implemented explicit DOI email delivery, 48-hour confirmation expiry, stored SHA-256 token hashes (raw tokens are not persisted), scanner-safe GET that renders a confirmation form without changing state, and a bounded URL-encoded POST that applies consent only after the recipient confirms.
- A conditional database update atomically claims a still-sent token before scheduling, preventing concurrent confirmation replays from both succeeding. Unsubscribe cancels pending/sent confirmation tokens; the email worker suppresses marketing delivery while DOI is required but unconfirmed.
- Owner/admin resend is workspace-scoped. A five-minute duplicate request guard reuses a recent matching confirmation, avoids sending a second message, and prevents a different pending signup payload from silently replacing the request bound to the existing token.
- Public HTML and JSON signup responses distinguish queued marketing, confirmation pending/in flight, and provider delivery failure; they no longer report a marketing sequence as queued when none was scheduled. Production HTML output remains escaped.
- Actual Resend account authentication, sender-domain verification and production delivery were **not** tested; CI uses controlled fixtures/mocks. Jurisdiction and owner policy review is needed before enabling DOI for a particular deployment. This is not a universal compliance guarantee.



## Prior verified checkpoint — immutable lead consent evidence

- Feature-code SHA: 8addf2b83991ca8015b4496704ef6a159b0a0a4a.
- Push CI: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40706775818
- PR CI: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40706784399
- Both runs completed successfully. Python: 610 passed, 7 skipped, 5 warnings. PostgreSQL migration/concurrency, frontend production/Docker, AI/RAG, security/SBOM, secret scan, repository guard and browser UAT passed. Push lockfile-sync passed; PR lockfile-sync was skipped by event condition.
- Added migration 0025 and a tenant-scoped consent event model. Grant, resubscription and unsubscribe events record exact canonical wording/version where applicable, purpose, source, channel and timestamp. Database triggers and ORM guards prevent update/delete. A read-only, workspace-scoped API exposes event history.
- Regression coverage verifies exact form copy, rejection of altered wording/old versions, persisted grant evidence, idempotent unsubscribe/suppression, ORM immutability and scoped history access.
- At this historical checkpoint, configurable double opt-in had not yet been implemented. The newer DOI checkpoint below closes the code-level confirmation journey; purpose/jurisdiction policy and governed unlink/anonymization/retention still remain open. No universal legal compliance is claimed.

## Prior verified checkpoint — unsubscribe safety and workflow test isolation

- Exact verified SHA: dc998827d52a1a2c7973630f22df2642f058a8e6.
- Push CI: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40701960870
- PR CI: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40701969318
- Both workflows passed. Python: 604 passed, 7 skipped, 5 warnings. PostgreSQL migration/concurrency, frontend production/Docker, AI/RAG, security/SBOM, secret scan, repository guard and browser UAT passed. Push lockfile-sync passed; PR lockfile-sync was skipped by event condition.
- Unsubscribe GET presents a signed confirmation page without changing consent. A signed POST must carry a supported URL-encoded confirmation body, including the RFC 8058 one-click form. Invalid signature/expiry, wrong content type, malformed or oversized body fails closed. Opt-out suppresses pending/retry scheduled mail transactionally.
- Browser UAT proves the GET did not change subscription state and explicit form POST did. A Playwright body-encoding mismatch was corrected by using its form parameter rather than a JSON-encoded dictionary.
- Workflow cancellation regression uses file-backed SQLite with independent connections for concurrent pause/poll checks; this changes the test harness only.
- This historical S4 gap was addressed in the later consent-evidence checkpoint below. Applicable double opt-in and governed privacy unlink/retention remain open.



## Newly implemented and verified in this checkpoint

### 1. Offer term snapshots and change detection

- Added Alembic migration 0021 and the MerchantOfferTermSnapshot persistence model.
- Added workspace-scoped POST capture and GET history endpoints under /api/merchant/offers/{offer_id}/term-snapshots.
- Records commission model/value/currency, terms version, cookie and attribution windows, regions, restricted traffic sources, source reference, evidence classification/excerpt, observation/capture times and actor.
- Computes stable SHA-256 term fingerprints and field-level before/after comparisons. Each offer's history has a monotonic sequence number so equal timestamps cannot reorder entries.
- Material changes disable terms verification and activation; approved offers are suspended and internally unlisted pending revalidation.
- Added a merchant-offer terms editor/history view and tests for baseline, unchanged/changed terms, suspension, workspace scoping and invalid evidence input.
- Important limitation: term snapshots retain operator-supplied values and do not fetch URLs during capture. A separate explicit fetch action can retrieve a cited public HTTPS page through the DNS-pinned, redirect-disabled, byte-limited helper; this proves only that a response was retrieved, not that the page belongs to the claimed merchant/network or that its text is true. The fetch result is immutable evidence metadata and never automatically verifies or approves the offer.

### 2. Offer metric integrity

- Fixed the offer metric service so click/conversion counts are not silently truncated or clamped.
- Negative, fractional/invalid count, boolean, negative/non-finite revenue and invalid/non-finite weight inputs raise validation errors.
- Invalid, negative or non-finite source gravity values remain unknown, instead of allowing NaN/Infinity to enter normalized scores.
- Added regression tests for invalid values and valid-zero versus unknown measurements.

## 3. Bounded public-source retrieval and content-change detection

- Added migration 0022, append-only fetch result records and workspace-scoped fetch/history endpoints. Fetches are explicit user actions and use the existing DNS-pinned SSRF-safe public fetch boundary.
- Requires HTTPS; redirects are not followed; only HTML/XHTML/plain text is accepted; response is capped at 1.5 MB and an 8-second timeout. Each attempt stores outcome/status, content type, bytes, SHA-256, bounded extracted text excerpt, ETag/Last-Modified, error code, timestamp and actor. Script/style content is removed from the excerpt.
- Migration 0023 compares successful body hashes and records baseline, unchanged, changed or non-comparable results. A full-page hash signals a source-page change; it does not claim commission terms changed.
- No page content is executed. Provider verification and offer approval remain false unless a separately defined, evidenced human workflow changes internal state.

## 4. Independent human review of source-page changes

- Migration 0024 adds reviewer decision, notes, reviewer identity, review time and review status.
- Only a changed page awaiting review can be reviewed. Self-review by the offer creator or snapshot creator is denied, review notes must be meaningful, and repeat decisions on an already reviewed fetch are rejected.
- Decisions: no material change, material change found, or source unreliable. Material-change/unreliable decisions disable activation, unlist internally and suspend a previously approved offer. “No material change” records only a human decision; it is not automated/provider verification.
- The UI exposes the review decision and evidence history. The action is audited; no external publish/network operation is triggered.

## Exact hosted verification for checkpoint 536428eab7c391b663bb311c5a2cf4aac1d4b854

- Push CI: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40696184789
- PR CI: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40696194630

Both exact-SHA workflows completed successfully. The Python suite reported 597 passed, 7 skipped and 1 warning. PostgreSQL migration/concurrency, frontend production/Docker, AI/RAG, security/SBOM, secret scan, repo guard and browser UAT passed. Push lockfile-sync passed; PR lockfile-sync was skipped by event condition. This evidence is not production deployment or provider integration proof.

## Exact hosted verification

Historical checkpoint f787358479d27490f3e4e8b516eab5c27f2e84be passed both workflows. The current authoritative verification for the latest feature slice is recorded in section 5 above.

CI success verifies the code candidate under the automated checks above. It does not establish live provider connectivity, legal clearance, production deployment or end-to-end product completion.

## Existing product foundation

The implementation branch already contains real but incomplete code for:

- FastAPI, SQLAlchemy/PostgreSQL, Alembic migrations, workspace-scoped APIs, authentication/role gates, audit events and Docker/Compose.
- Affiliate offer research, a provider-readiness registry, evidence-aware scoring and traffic/eligibility screening.
- Content/creative draft generation, LLM abstraction, RAG retrieval, SEO helpers, content-decay and content-moat planning.
- Landing/lead capture, consent-aware email queueing, webinar registration and nurture/workflow helpers.
- Distribution queues, provider/CMS boundaries, draft-first defaults and human review gates.
- Persisted advertising plans, creative/audience variants, unverified KPI intake, sample-gated review recommendations and budget guardrails.
- Signed/deduplicated conversion ingestion, commission ledger/reversals, currency-separated analytics and review-only reconciliation.
- Workflow checkpoints/recovery, approval pauses, resource budget controls and a partial read-only platform operations console.
- A 53-row skill parity matrix, source skill package and supporting evaluation/test framework.

These inventories describe code present, not blanket production readiness. A provider adapter, catalog row, skill registry entry or UI control is not proof of an authorized end-to-end capability.

## Remaining production work — priority order

1. **Real provider coverage and verification:** official APIs, OAuth or provider authentication, least-privilege scopes, credential rotation/revocation, contract/sandbox tests, rate-limit handling, pagination, retries, provider status reconciliation and actual account health evidence for selected affiliate networks. The long-term 100+ provider objective is not current live coverage.
2. **Mandatory paid-ad operations:** provider-attested spend/impressions/clicks/conversions, tracking and attribution-window maturity, approved remote create/pause/budget operations, budget caps, stop-loss and kill-switch tests, duplicate/timeout recovery, policy checks and evidence-backed reporting. Existing planning and intake do not prove live campaign management.
3. **53 skill end-to-end parity:** the current matrix records 53 partial and 0 fully end-to-end implemented. Each skill still needs verified service behavior, typed API, persistence where relevant, usable UI, provider integration or explicit unsupported state, security and acceptance tests.
4. **Lead/consent/email/CRM:** complete browser-tested form-to-database-to-consent-to-delivery/CRM journeys, double opt-in where required, unsubscribe/suppression/re-subscription correctness, email event handling, nurture execution and data export/deletion flows.
5. **Content/SEO/trust:** claim-by-claim grounding and evaluation, complete edit/review/version/publish lifecycle, localization, authorized Search Console data, technical crawling, internal-link validation, content freshness, accessible disclosures and measured publish/refresh loops.
6. **Distribution/deployment:** official channel-specific authorization, media upload, draft/schedule/publish/status reconciliation, remote IDs, idempotent retry/cancel, provider response evidence, bio-link and GitHub Pages deployment verification and rollback.
7. **Attribution and finance:** provider-specific signed events/postbacks, replay protection, conversion lifecycle transitions, source-backed commission reconciliation, partial/full reversal and refund/chargeback edge cases, payout evidence, concurrency and currency-safe reporting with authorized network test data.
8. **Multi-tenant SaaS and roles:** exhaustive authorization and cross-tenant testing across APIs, workers, queues, caches, events, files and exports; complete workspace/member lifecycle; distinguish workspace admins from platform Super Admin; verify the full lifecycle against production-like PostgreSQL.
9. **Operational reliability:** durable queue/dead-letter controls, worker/queue health, alerts/SLOs, tracing and redacted diagnostics, realistic load/soak tests, per-tenant/model/provider cost controls, backup and restore rehearsal, migration rollback, incident runbooks and verified kill switches.
10. **Security, privacy and legal release gates:** authentication/session and CSRF review as applicable, SSRF and webhook hardening, secrets rotation, dependency/SBOM/license review, resolution or explicit legal disposition of the recorded sharp-libvips LGPL exception, privacy/retention controls, market-specific advertising/disclosure review and an explicit owner decision on public repository visibility.
11. **Staging and release:** controlled staging deployment, healthy service checks, verified deployed SHA, applied migration proof, monitoring, restore/rollback rehearsal, end-to-end UAT against authorized provider sandboxes and exact-candidate workflow evidence. No production deployment is claimed.

## Source and owner-controlled blockers

The current requirements register records 35 Library items at the 2026-10-27 inventory checkpoint but 21 unique content identities because duplicate copies and nested archives exist. The newer separately described ZIP of an already-live application was not identified in that inspected inventory. Older ZIPs and the 53-skill package are useful references, not proof that the newer live application was inspected or ported. Do not replace current Project1 code wholesale with an unreviewed archive.

Provider credentials/approvals, staging environment, backup destination, licensing/legal review and the proprietary repository visibility decision are owner-controlled prerequisites where they remain unresolved.

## Working rules for the next checkpoint

Continue only in the existing branch. Pick the highest-priority unblocked requirement, implement a vertical slice with tests and traceability, inspect exact-SHA push and PR workflow logs, fix regressions before proceeding, and record implemented/tested/provider-verified/deployed as separate statuses.

Do not merge the draft PR or claim production-live readiness until the full release gates have evidence.


## Latest verified numeric safety refinement — 602f761732ce8930bc103ed3f19b13ee524dc6a3

Schema minimum/maximum constraints now reject boolean, malformed, NaN and infinite values without type-comparison exceptions. The skill ROAS handler has bounded Decimal inputs, six-decimal precision checks and an explicit computed-ratio ceiling; it returns review-only results and executes no remote campaign action. Added regression coverage for malformed bounds, over-precision money and extreme ratios. Exact push/PR workflows 40721720474 and 40721732685 passed; Python 640 passed, 7 skipped, 5 warnings, and browser UAT 5 passed each.
