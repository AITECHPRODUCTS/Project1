# Affitor partner experience comparison — 1 November 2026

**Purpose:** Use Affitor as a product reference for OmniAffiliateOS partner/publisher and merchant flows. This is a feature comparison, not a claim of equivalence or production readiness.

## Live reference baseline

Affitor's public partner documentation describes a partner dashboard with Marketplace, Programs, Chat, Referrals and Payout. Its program page includes Overview (clicks, signups, paid signups, revenue and commission over date ranges, chart and top links), Links (link creation and performance), Customers (masked customer identity, signup date, last purchase and lifetime value), and Commissions (dated transaction rows with type, link, sale, commission and status). Partner setup and start-earning checklists are also documented.

Reference pages:
- https://affitor.com/partner
- https://affitor.com/docs/partners/dashboard
- https://affitor.com/docs/partners/faq
- https://affitor.com/docs/getting-started/how-it-works

## OmniAffiliateOS evidence at baseline commit \`059dfa63dfaf43f6e8322eeb69f8e6cd9c01c795\`

| Capability | Current evidence | Comparison |
|---|---|---|
| Merchant offers marketplace | \`GET /api/marketplace/offers\`, \`/marketplace\`, merchant offer approval/listing gates | Implemented as an internal merchant offer marketplace; not a universal external network marketplace |
| Partner applications | Persisted \`MarketplaceApplication\`, publisher submit, merchant review, approval/rejection, terms snapshot, compliance attestations | Implemented |
| Merchant-issued tracked link | One \`AffiliateProgramLink\` and campaign issued only after merchant approval | Implemented, one primary link per application |
| Publisher My Programs list | \`/programs\`: search, status filter, terms snapshot, approval state, tracked clicks and grouped commission evidence | Implemented |
| Program-specific detail | Previously absent; data only shown inside the list card | Gap; this increment adds a workspace-scoped detail endpoint and page |
| Performance | First-party click counts; signed merchant conversion/commission observations grouped by currency/evidence | Partial; no complete signup/paid-signup or source-provider analytics series |
| Multiple links and link-level reporting | One link per application/campaign; no publisher-created aliases | Not implemented |
| Customer directory | No publisher-scoped masked customer profile/last-purchase/LTV view | Not implemented; don't infer identities from click events |
| Partner chat | No persisted merchant-publisher conversation/message model or inbox | Not implemented |
| Partner payout account, withdrawal and transaction history | No publisher payout onboarding/withdrawal/history; merchant readiness is only a review aid | Not implemented; no funds-transfer assertion |
| Brand-referral rewards | No partner referral-to-Affitor reward workflow established in the inspected implementation | Not verified / not implemented |

## Added in this increment

- Added \`GET /api/marketplace/applications/{application_id}\`, which returns only a program belonging to the authenticated publisher workspace. Cross-workspace IDs return 404.
- Exposed scoped all-time clicks, last-30-day daily click counts, and commission evidence grouped by currency, evidence status and ledger entry type.
- Added \`/programs/{applicationId}\` with Overview, Links, Commissions and Terms sections.
- Added explicit "Not implemented" states for Customers, Messages and Payouts. No customer identities, messages, payout accounts or money movement are fabricated.
- Added API and browser regression tests; the change adds no database migration and does not modify existing application records or the append-only commission ledger.

## Release and acceptance boundaries

The detail view proves the stored application/link/click/ledger data can be presented for an authorized publisher. Browser CI uses controlled fixtures and is not a live merchant/affiliate UAT. A real program needs a listed merchant offer, publisher application, merchant approval, first-party tracked click and merchant-signed event. Live provider credentials, payouts, messaging, customer-privacy design, backups/restore, operational worker readiness and staging acceptance remain separate release gates.
