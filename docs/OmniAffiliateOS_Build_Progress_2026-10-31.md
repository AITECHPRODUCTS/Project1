# OmniAffiliateOS — build progress and production remainder

**Updated:** 31 October 2026  
**Repository:** https://github.com/AITECHPRODUCTS/Project1  
**Working branch:** build/omni-affiliate-os-production (existing branch only)  
**Release decision:** **NOT PRODUCTION READY.**

## Current application foundations

- Affiliate commission-earner / publisher cockpit: /.
- Merchant / product-publisher workspace: /merchant, /merchant/offers, /merchant/applications.
- Platform Super Admin console: /admin.
- Execution modes exist: FULL_AUTONOMOUS (only pre-authorized safe stages), SEMI_AUTONOMOUS (approval pause/resume), and MANUAL_OVERRIDE (one selected stage). Sensitive external, advertising and financial actions remain approval-gated.
- Current code includes FastAPI, Next.js/TypeScript, SQLAlchemy/Alembic, workspace authorization, persistent S1–S8 workflows, research/content/SEO/funnel drafts, lead/consent flows, guarded distribution, ad planning/guardrails, conversion/commission-ledger foundations, AI/RAG foundations, provider registry, merchant operations and admin visibility.
- Native provider account slices found in the current branch include ClickBank read-only account/order reporting, Digistore24 read-only marketplace directory and Flipkart read-only product/offer feeds. The wider provider catalogue is not a list of connected integrations.

## 31 October continuation — connected marketplace search

- Candidate code adds authenticated POST /api/affiliate-research/search and /affiliate-research to search connected Digistore24 and Flipkart read-only catalogs from one query.
- Each account is queried independently; provider snapshots are saved against the exact workspace/connection, audit events record outcomes, and one account failure does not erase another provider's successful results.
- Commission, cookie duration, payout terms, eligibility and approval stay unknown unless authoritative evidence is separately verified. ClickBank is not in this product-search operation because its current adapter is account/order reporting.
- This remains read-only: no affiliate application submission, content publishing, ad spend, account mutation or payout transfer.
- Exact-head verification for this slice: candidate HEAD `a99aa24b6031a0a21aeff1ce6cd5f968defd1439`. Push Actions [41181063396](https://github.com/AITECHPRODUCTS/Project1/actions/runs/41181063396) and PR Actions [41181067506](https://github.com/AITECHPRODUCTS/Project1/actions/runs/41181067506) both completed successfully. Python: 909 passed, 9 skipped, 5 warnings; Chromium browser UAT: 47 passed. PostgreSQL integration, frontend build/typecheck, AI/RAG profile, security audit, secret scan and repository guard passed. Push lockfile sync passed; PR lockfile sync was skipped by its configured push-only condition. This proves automated CI behavior on the candidate SHA, not a local human session or live affiliate-account credential test.
- Local deployment and real-user acceptance on the user's Windows machine are still pending. Recommended next gate: start the Compose stack, create a normal workspace owner account, connect a user-owned Digistore24 and/or Flipkart credential locally, search the actual provider catalog, inspect persisted snapshots and tenant isolation, then collect redacted logs/screenshots without sharing secrets.

## Production remainder

1. All 53 skills remain partial in the current parity ledger; end-to-end runtime, APIs, persistence, authorization, UI/trigger, provider evidence, evaluations and acceptance must be completed skill by skill.
2. Additional affiliate networks need official provider-specific adapters, scopes, health checks, revocation/refresh, terms, applications and commission/postback contracts. The 100+ provider objective remains open.
3. Paid ads, organic publishing, CRM and social/CMS/email integrations need real account scopes, provider-attested metrics, idempotent remote status reconciliation and live sandbox UAT.
4. Attribution and commission need full provider event matching, deduplication, partial/full reversal, statements and payout-state reconciliation. Money transfers are not automated.
5. Merchant and Admin need full publisher lifecycle plus queue/worker health, dead-letter controls, alerts/incidents, quotas/cost, privacy export/deletion and support audit.
6. Production release needs legal/license and repository-confidentiality decisions, staging deployment, managed secrets/rotation, monitoring/SLOs, load/soak, accessibility, backup restore, rollback and DR evidence.

No claim is made of guaranteed earnings, 100% failproof operation, universal provider connectivity, production deployment or live affiliate credentials.


## Dashboard independence and navigation hardening — 31 October 2026

- The Publisher dashboard now routes its article-writing, content-health, research-brief and offer-qualification shortcuts to their existing dedicated feature pages. The applications shortcut targets the actual application list section in the marketplace rather than only the marketplace page top.
- Merchant navigation now provides explicit Dashboard, Manage offers and Review applications links plus a workspace data refresh action.
- Platform Super Admin navigation now links directly to the platform operations and tenant lifecycle sections.
- Dashboard client-side access checks now require the persisted account persona: `affiliate_publisher` for the Publisher dashboard, `merchant_product_owner` for the Merchant dashboard, and both `platform_admin` and `is_admin=true` for the Super Admin console. This prevents a global admin flag alone from making the business-persona dashboards interchangeable.
- Browser regression coverage was extended for navigation destinations and cross-persona denial. These changes do not make the remaining platform lifecycle, provider integrations, ad delivery or commission settlement work complete; production readiness remains open pending full feature and live-environment acceptance.


## Dashboard business-operations increment — 31 October 2026

- Publisher dashboard now reads the immutable conversion evidence ledger and presents commission totals grouped by currency and evidence status, with recent observations and an internal-application status summary. It does not add multi-currency values together or label provider observations as paid commission.
- Merchant dashboard now derives terms-verification, seller-authorization, activation-readiness, marketplace-listing and evidence-gap counts from persisted offer records. It also reads the pending, internally approved and rejected publisher-application counts and shows a short pending-review preview.
- Platform Super Admin now has a bounded CSV export of global audit metadata with exact workspace/action/outcome filters, formula-injection-safe cells, no-store response headers and an audit record for the export action. Exported values are not copied into the export audit event.
- Browser coverage now verifies the new publisher and merchant summaries and the Admin export link. API tests cover export scoping filters, spreadsheet formula safety, export audit recording and rejection of non-platform-admin users or missing audit workspaces.
- Queue/dead-letter recovery, incident management, usage/cost controls, richer release monitoring, live provider credentials and local real-user acceptance remain open; this increment is not a production-readiness declaration.


## Super Admin operational-control increment — 31 October 2026

- Added a bounded, platform-admin-only cross-workspace operations snapshot for persisted workflow attempts, workflow leases/heartbeats, distribution review-queue rows, and incident records. Global views return operational metadata only; full workflow state, error payloads, content bodies, provider tokens, and customer queue titles are not exposed.
- The Super Admin operations view distinguishes failed runs, expired/stale workflow leases, provider outcomes requiring manual reconciliation, and failed side-effecting runs that are **dead-letter candidates**. This is not represented as a completed dead-letter worker or a provider dispatch queue.
- Added an operator retry path for one explicitly failed **non-side-effecting** workflow stage only. It runs as MANUAL_OVERRIDE, requires a reason and confirmation, creates a durable retry-claim audit record, and allows only one retry claim per original run. S5/provider publishing stages and any run with an uncertain external side effect are blocked and must be reconciled before any resubmission.
- Added a durable global platform incident model and Alembic migration 0041. Failed workflow runs can be linked to incident records; creation is idempotent; acknowledgement and resolution require Platform Super Admin; each transition is audited. Incident summaries retain stage/error-class metadata, not raw workflow payloads.
- Distribution queue inventory is shown as review/scheduling evidence only. The existing queue implementation has no provider-dispatch worker; approval still does not publish. No dispatch retry or queue requeue control was added.
- The new Super Admin operations APIs require both the global admin flag and explicit platform_admin persona, without changing the existing shared global-admin dependency used by existing provider/finance integrations. Added API tests for cross-workspace visibility, safe read-only retry, side-effect retry denial, incident lifecycle/audit, and denial of a business persona even when the global flag is present. Browser UAT now exercises the operations API and renders queue/incident panels.
- Remaining in this area: a real durable provider dispatch worker with per-provider idempotency and reconciliation; persisted dead-letter queue semantics for retryable queue jobs; incidents from broader system/worker events; alert delivery, support tools, usage/cost limits, and release monitoring.
- Automated tests are added in this increment and must be treated as unverified until the exact-commit push and PR Actions runs finish. Docker/local user acceptance on the user's port 3001 instance still requires rebuilding the local Compose stack and exercising it on the user's machine. CI does not prove that running local containers have been updated.


## 2026-10-31 — unified public entry and role-aware workspace UX
- Preserved the existing large Growth Command application code as an authenticated workspace component; the new homepage does not replace or discard those tools.
- Added a public homepage at /, a unified sign-in route at /login, and an improved Brand / Partner signup flow at /register.
- Both business personas now land on the same /dashboard entry after registration or sign-in. The dashboard reads the authenticated identity and shows Merchant or Affiliate actions and counts from existing role-authorized APIs.
- Added /growth for existing Publisher Growth Command tools and /platform for the existing command centre restricted to platform administrators. The separate /admin Platform Super Admin operations console remains intact.
- Workspace switching uses existing authorized memberships only. The current backend still models one business persona per account; the UI does not pretend a user can switch roles without backend authorization.
- Existing /publisher, /merchant and their detail routes remain in place for compatibility. Browser smoke journeys now use the preserved /growth route.
- Updated persona browser tests for the common dashboard entry. Exact-commit CI evidence is pending until push and PR workflows complete.
