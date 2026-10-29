# OmniAffiliateOS — Build Status Summary

**Snapshot:** 29 October 2026  
**Repository:** https://github.com/AITECHPRODUCTS/Project1  
**Working branch:** build/omni-affiliate-os-production  
**Current verified code SHA:** 58f3235925d50522fa8db6f56de1cac7b61f7861  
**Release decision:** NOT PRODUCTION READY. Draft PR #1 is open and unmerged.

## Built in the current branch

The codebase contains a FastAPI/SQLAlchemy backend and Next.js/TypeScript workspace UI with authentication, tenant/workspace-scoping patterns, audit logging, health/readiness probes and CI quality/security gates.

Major vertical slices already present include:

- **S1 — Research and offers:** offer intelligence and metrics, shortlist management, offer-term evidence snapshots, qualification reviews and affiliate-program application packets. Provider approval and live offer terms are not inferred.
- **S2 — Content:** source-backed research briefs with source snapshots/hashes and claim-to-quote matching, blog generation, content atomization, platform-specific text/script drafts, infographic/video generation, the product comparison writer and the evidence-aware listicle writer.
- **S3 — SEO and trust:** on-page checks, keyword clustering, internal-link recommendations, content moat and content-decay review queues. Some inputs remain operator supplied; live Search Console/competitor data is not universally connected.
- **S4 — Funnels and leads:** landing-page/form paths, consent evidence, lead lifecycle functions, attribution fields and email automation foundations.
- **S5 — Distribution and advertising:** distribution queue/approval patterns, draft ad campaign plans, creative variants, budget guardrails and review-only performance evaluation. External publishing and paid spend are not authorized by generated drafts.
- **S6 — Analytics and finance:** conversion/commission recording, attribution, finance ledgers/reconciliation evidence and persisted commission projections. Projections are assumptions; they do not prove actual earnings or move money.
- **S7/S8 — Automation and learning:** workflow/state-machine foundations, governed skill packages/runtime and capability/integration registry. Registry coverage does not prove a live provider connection.
- **Operations and privacy foundations:** signed provider-event handling, lead export/email-delivery history, repository guard, Python/frontend checks, PostgreSQL migration tests, security/SBOM scans, secret scan and browser UAT.

This means code paths are present, not that every feature or provider is production complete. Some capabilities are draft-only, partially connected, based on operator input, or pending dedicated acceptance.

## Comparison source evidence feature — previously verified at cb82e4cdbe1eeb9d7bdfd51c1956c1655358daad

The product comparison writer is now more than a draft-only fact table: it safely captures bounded public source snapshots and records which supplied fact wording was, or was not, present in the corresponding product's snapshot.

- POST /api/content/comparison-post validates 2–5 distinct products, up to 12 fact fields per product and at most 10 unique HTTPS source URLs across the comparison.
- It fetches through the repository's pinned public transport, with a 1 MB response cap per URL, 12-second timeout, concurrency capped at four, no silent redirect following, readable-content allowlisting and source text extraction that removes scripts/navigation and other irrelevant elements.
- Captured snapshots include a UTC capture time, source/product association, bounded excerpt and SHA-256 hash. Failed fetches are visible as failed and do not become evidence.
- Deterministic per-fact matching checks only the snapshots assigned to that product. Results distinguish literal text observed from text not found, missing sources, failed fetches and facts not supplied. A text match is explicitly not independent verification of truth, freshness, completeness, pricing, eligibility or compliance.
- Evidence ledgers/summaries persist with the active workspace's ContentAsset draft and audit row. The frontend displays snapshot and evidence counts, per-fact status and expandable source excerpts/hashes. Publishing remains off.
- Service/schema/API/persistence/security regression tests and Chromium journeys cover bounded fetching, sanitization, source failure, product-scoped evidence matching, persistence/audit, evidence display and invalid input.

**Latest exact-SHA evidence:** push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40860248603 and PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40860256236 passed all required jobs on code SHA `532d909ddd074848b985f2ff87ff328b834d4549`. Python: **788 passed, 8 skipped, 5 warnings**. Chromium UAT: **25 passed**. PostgreSQL migration/integration: **8 passed**, including 24 simultaneous revision-number reservations. Frontend typecheck/build/Docker smoke, AI/RAG, security/SBOM, secret scan and repository guard passed. Push lockfile-sync passed; PR lockfile-sync was skipped under its configured push-only condition.

**Earlier comparison-writer verification:** push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40851987784 and PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40851997494 passed on cb82e4cdbe1eeb9d7bdfd51c1956c1655358daad. Python: **785 passed, 7 skipped, 5 warnings**. Browser UAT: **24 passed** on both runs. PostgreSQL integration, frontend typecheck/build/Docker smoke, AI/RAG, security/SBOM, secret scan and repository guard passed. Push lockfile-sync passed; PR lockfile-sync was skipped under its configured push-only condition.

The source-evidence feature is verified for snapshot collection and literal text matching only; the later hash-bound review lifecycle is documented above. Merchant facts, current pricing, eligibility, legal compliance, affiliate network authorization and live provider behavior remain independently unverified.

## Previous feature: saved comparison draft retrieval — verified on 29 October 2026

The comparison writing workflow now supports durable retrieval after navigating away or reloading the page.

- GET /api/content/comparison-posts returns a bounded, paginated summary of comparison drafts for the authenticated active workspace only; it orders newest first, caps the page size at 100, and returns Cache-Control: no-store.
- GET /api/content/comparison-posts/{asset_id} returns the stored HTML, product/fact matrix, bounded source snapshots and hashes, evidence ledger, word-target state and explicit review-only execution boundary. It also uses no-store responses.
- Both endpoints require an authenticated active workspace and explicitly filter the content_assets query by both workspace_id and asset_type. A missing or cross-workspace ID returns 404, so the endpoint does not disclose that another workspace's record exists.
- The Next.js comparison page now loads the workspace's saved draft list on page load, refreshes after creating a draft, and can reopen a saved record in the evidence review and isolated HTML preview. It remains draft-only and does not publish.
- Regression coverage verifies persisted source evidence, list/detail response data, no-store headers and cross-workspace denial in SQLite API tests. Chromium UAT verifies draft creation, opening the created draft and reopening an existing saved draft after a page reload.

Exact-SHA push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40855889234 and PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40855896327 passed on code SHA 321ba0a463819af2fe6915c55dcf62fb0fc1c0a0. Python: 787 passed, 7 skipped, 5 warnings. Chromium browser UAT: 25 passed on both runs. PostgreSQL integration, frontend typecheck/build/final Docker smoke, AI/RAG profile, security/SBOM, secret scan, repository guard and push lockfile-sync passed. PR lockfile-sync was skipped by its push-only condition.

This feature makes saved comparison drafts retrievable; it does not change the overall release decision. Merchant evidence, true/current product facts, eligibility, legal/compliance approval, live affiliate provider connections, production deployment and backup/restore remain separate open gates.

## Latest feature: immutable comparison draft revisions — verified on 29 October 2026

- Added the optional `revision_of_asset_id` request field for `POST /api/content/comparison-post`. The API verifies that the source is a comparison draft inside the authenticated active workspace, returns 404 for missing/foreign resources and rejects non-draft resources without changing them.
- A revision creates a new `ContentAsset` and stores `revision_number`, `revision_of_asset_id` and `revision_root_asset_id` in metadata. The original body, title, evidence and audit row remain unchanged. Revision creation has the separate `content_comparison_post.revised` audit action. Existing metadata storage is reused; no database migration is needed.
- Saved draft detail now returns the topic, audience, disclosure and revision lineage. The UI loads the saved form values, can save a new revision or intentionally start a separate independent draft, updates the workspace history, and displays the parent/root lineage.
- API regression coverage verifies revision 1/root identity, revision 2 lineage, persisted root metadata, immutable original content, revision audit evidence and denial of cross-workspace revision attempts before invoking the generation service. Chromium UAT exercises opening a saved draft, changing it, saving a revision and confirming the original remains unchanged.
- Exact-SHA push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40858629542 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40858638120 passed on code SHA 62dfa336dfa4c617359f01588037611ec93be899. Python: 787 passed, 7 skipped, 5 warnings. Chromium UAT: 25 passed on both runs. PostgreSQL migration/integration, frontend typecheck/build/Docker smoke, AI/RAG profile, security/SBOM audit, secret scan and repo guard passed. Push lockfile-sync passed; PR lockfile-sync was skipped by the configured push-only condition.
- Revision history establishes lineage/auditability, not claim truth or provider approval. Product-source snapshots record literal text presence only; legal review, official affiliate eligibility, provider credentials/UAT, live publishing, staging deployment, observability and backup/restore remain production blockers.


## Latest verified lifecycle increment — 29 October 2026

The latest verified implementation is code SHA 378f890da1063b8e98eaea9f979bd6d2ff9e9112. It extends the comparison-writer vertical slice into a controlled editorial lifecycle:

- Bounded source capture and per-product literal fact evidence; source snapshots keep excerpt hashes and explicit fetch failures.
- Workspace-only saved draft listing/detail, immutable revisions and atomic workspace/root revision numbering.
- Integrity verification across stored HTML, canonical source-snapshot manifest/excerpt bytes, structured evidence payload and creation/revision audit bindings.
- Owner/admin review decisions are hash-bound, auditable and immutable per revision. Missing or changed integrity baselines block review; editorial approval is not provider approval and does not publish.

Exact-SHA evidence:
- Push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40886156627 — passed.
- PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40886166294 — passed.
- Python: **798 passed, 8 skipped, 5 warnings**; Chromium browser UAT **26 passed** on both; PostgreSQL migration/integration **8 passed**. Frontend/Docker, AI/RAG, security/SBOM, secret scan and repository guard passed. Push lockfile-sync passed; PR lockfile-sync was skipped by its configured push-only condition.

The current fix only corrects test-fixture variable scope and does not weaken the integrity checks. Hashes are not signatures, and literal source text is not proof of truth/currentness. Overall production readiness remains blocked by official provider/account UAT, legal/compliance sign-off, complete 53-skill acceptance, staging deployment, monitoring, backup/restore and rollback evidence.

## Remaining before a production launch

1. **Close P0 authorization and safety findings:** continue reviewing remaining workspace/tenant ownership checks, globally configured provider surfaces, public-route abuse/rate limits, outbound HTTP/SSRF boundaries, workflow retry/idempotency and externally impactful provider paths. Add negative tests for each finding.
2. **Verify real provider connections:** official OAuth/app approval, scopes, revocation, sandbox contract tests and account-level evidence for selected affiliate networks, ad platforms, social publishers, CMS, email and CRM. A registry entry or mocked test is not provider UAT.
3. **Connect and validate data:** merchant terms and freshness, click/conversion/postback deduplication, signed event ingestion, provider-attested ad metrics, refund/reversal handling, commission reconciliation and payout-threshold checks using real test-account evidence. No payout transfer is certified by this summary.
4. **Complete product acceptance:** map each of the 53 skills to implementation, persistence, tenant isolation, API contracts, negative tests, browser paths and dependencies; close partial/stub items and maintain the traceability/parity files.
5. **Prove deployment operations:** target-environment migrations, TLS/session/CORS/trusted-proxy configuration, key/secret rotation, worker/queue health and retries, monitoring/alerts, load/cost tests, backup/restore and disaster-recovery drills.
6. **Finish governance and release approval:** product/legal review of disclosures and geography/program restrictions; model/provider configuration and artifact provenance/license review; final vulnerability/SBOM/secret scans; staged end-to-end UAT, rollback plan and signed production acceptance.

## Latest verified feature: evidence-aware listicle writer — 29 October 2026

- Added `POST /api/content/listicle` to generate a review-required roundup from five to twelve operator-supplied product entries, plus optional bounded public-page snapshots. It uses the existing pinned, size-limited public-fetch transport and the comparison writer’s product-scoped literal-text evidence helpers.
- The narrative is sanitized with the existing HTML allowlist. Product order and the deterministic “at a glance” table are based on the supplied order and values. The fact ledger labels exact text observed, exact text not found, failed fetches or missing sources; these statuses are not claims of truth or currentness. Affiliate destinations are bounded HTTPS URLs, disclosed in the article, and never called by the service.
- Added workspace-scoped create/list/detail APIs, saved `ContentAsset` drafts and `AuditLog` events; body SHA-256, fetched excerpt hashes, canonical source-manifest hash and evidence-payload hash are bound to creation-audit data. Detail/review calls fail closed with HTTP 409 when stored content/evidence no longer matches the saved baseline.
- Added one-time owner/admin editorial approve/request-changes/reject decisions bound to the current content hash. A review decision never changes the asset out of draft status and never triggers CMS/social publication, affiliate-network submission, ad spend or other provider writes.
- Added `frontend/app/listicle-writer/page.tsx`, dashboard and comparison-page links, Python schema/service/API regressions and two Chromium browser tests. Latest code SHA: `58f3235925d50522fa8db6f56de1cac7b61f7861`.
- Exact-SHA push [40897990313](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40897990313) and PR [40898005395](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40898005395) both passed all required jobs: Python **802 passed, 8 skipped, 5 warnings**; Chromium browser UAT **29 passed**; PostgreSQL migration/concurrency, frontend typecheck/build/Docker smoke, AI/RAG imports/SBOM, security/SBOM audit, secret scan and repository guard passed. Push lockfile-sync passed; PR lockfile-sync was skipped by its configured push-only condition.
- Remaining for this skill: content revisions, authoritative fact verification and source freshness checks, seller/program terms and eligibility validation, jurisdiction-specific disclosure approval, editor usability/accessibility review and end-to-end production provider/publishing UAT. Product remains **NOT PRODUCTION READY**.

## Current count and limitations

| Verification measure | Exact current result |
|---|---|
| Python CI suite | 802 passed · 8 skipped · 5 warnings |
| Chromium browser UAT | 29 passed |
| Push CI | Passed |
| Draft-PR CI | Passed |
| Push lockfile sync | Passed |
| PR lockfile sync | Skipped by configured push-only trigger |
| Production deployment/live provider UAT | Not established by these CI runs |

A trustworthy overall completion percentage is not reported because the complete requirement inventory has not been proven against production acceptance criteria, and green software CI does not establish provider/account, compliance, disaster-recovery or live deployment readiness.

**Resume instruction:** continue from the existing build/omni-affiliate-os-production branch and this verified SHA. Do not create another branch, merge, deploy, or mark the product production-ready until the remaining gates have current evidence.

## Latest verified fix: concurrent revision allocation

Revision allocation is now backed by migration 0031 and a workspace/root-scoped sequence. The atomic reservation is audited before generation and does not alter the original draft. The SQLite test seeds prior revision history; the PostgreSQL test reserves 24 revision numbers concurrently and proves uniqueness/monotonic sequence.

The first PostgreSQL attempt found a fixture ordering error (workspace parent not flushed before child asset); the fixture was corrected and the exact-SHA push/PR checks above passed. This does not close the broader release gates: product-source text is not verified truth; official network credentials/approval, compliance/legal review, external publishing, staging operations, monitoring, backup/restore and remaining skill parity remain pending.

## Latest verified fix: comparison draft and evidence integrity

Code SHA 585c30cf91d8d8baf64796ddbd565c90550412eb passed exact-SHA push [40882079872](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40882079872) and PR [40882091616](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40882091616). New drafts store an SHA-256 body baseline and canonical source-snapshot manifest/hash, with both recorded in the creation/revision audit. Detail and review operations detect changed HTML, snapshot identity/metadata, excerpt bytes, and missing or mismatched audit baselines; a failed check blocks editorial review with HTTP 409 and the UI explains the blocked state.

Regression suite results: Python 796 passed, 8 skipped, 5 warnings; browser UAT 26 passed; PostgreSQL migration/integration 8 passed; frontend typecheck/build/Docker smoke, AI/RAG, security/SBOM, secret scan and repo guard passed. Push lockfile-sync passed; PR lockfile-sync was skipped by its push-only condition. A direct-insert test fixture initially failed because it omitted the new creation-baseline/audit contract; the fixture was corrected and the fresh exact-SHA push/PR runs passed. This protects against ordinary drift and partial tampering, not a privileged attacker rewriting all database records. Product fact truth, legal/compliance status, provider eligibility and publication readiness remain independently unverified.
