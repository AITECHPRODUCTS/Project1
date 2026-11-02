# Product requirements

## User-facing value
Provide a coherent workspace that turns evidence-backed audience/product information into reviewed drafts, authorized campaigns and measured affiliate economics. The product must work for both affiliate publishers and merchants, with separate workspace capabilities and a platform-level operations role.

## Functional scope
- Offer catalogue and source/terms evidence with `observed_at`, geography, source links, commission basis, attribution window if supplied, restrictions, version and confidence.
- Explainable offer scoring. Missing data remains unknown; traffic, EPC, conversion, commission and earnings are never fabricated.
- Campaign funnel and versioned landing pages, honest disclosures, consented lead capture, email preferences/unsubscribe, UTM and click-ID tracking.
- Blog, SEO, comparison/how-to, social copy, image/video scripts, media rendering, CMS and social distribution through allowed APIs.
- Click/conversion states and append-only commission/reversal observations; payout threshold tracking must not claim funds received.
- Dashboard reads persisted API data; every button has an observable action, loading/error/empty/stale/permission states.
- Admin surface for platform operations is required; current implementation remains a gap until global admin controls are implemented and tested.

## Non-functional scope
Safe defaults, retries, idempotency, observability, controlled cost, source provenance, accessibility, mobile responsiveness, tenant authorization, data retention, backups and recoverable operations.

## Out of scope for automatic bypass
Provider KYC/approval, forbidden scraping, UI automation around CAPTCHAs, automated bank transfers, mass unsolicited spam, false reviews/claims and guaranteed revenue.
