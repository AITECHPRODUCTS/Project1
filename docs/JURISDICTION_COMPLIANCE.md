# Jurisdiction compliance evidence workflow

## Purpose and limits

This feature stores source-backed compliance assessment records for OmniAffiliateOS workspaces. It does not contain or automatically generate a complete worldwide law database. A user must enter authoritative sources and the person who approves an assessment must check each source, effective status, applicability and the target jurisdictions. The system records evidence, freshness and review decisions; it is not legal advice or a guarantee of compliance.

## Required workflow

1. Select activity, actual channel/provider identifiers, and every target jurisdiction (use ISO-style country/subdivision codes; add EU/EEA separately when applicable).
2. Add cited HTTPS source evidence for each required category in every jurisdiction. Record title, requirement summary, optional effective date, source review time and reviewer attestation. Global/general evidence does not silently substitute for country-specific evidence.
3. Save the assessment. It remains \`draft\` when coverage is missing/stale and \`review_required\` only when the evidence grid is covered.
4. A workspace administrator independently reviews the sources and confirms the scope before approval. The backend blocks approval if required evidence is missing, stale, future-dated or unattested. Approval is scoped to the activity, provider/channel and jurisdiction set, and expires after 180 days; faster-changing activities use a shorter evidence freshness window.
5. New live social and CMS publishing, and workflow S5 live distribution, check for a current approved matching assessment at execution time. A missing or mismatched assessment is audited and blocks the provider action. Draft and dry-run work remains available.

## Configured evidence categories

- Affiliate promotion: affiliate disclosure; advertising claims; platform terms.
- External content publishing: affiliate disclosure; advertising claims; platform terms; privacy and data protection.
- Paid media: affiliate disclosure; advertising claims; paid-media rules; privacy and data protection; platform terms.
- Email marketing: affiliate disclosure; email marketing rules; privacy/data protection; consent and marketing permissions.
- Lead capture: privacy/data protection; consent and marketing permissions; retention/deletion.
- Tracking and analytics: privacy/data protection; cookies/tracking; retention/deletion.
- Merchant marketplace: affiliate disclosure; advertising claims; platform terms; consumer protection.

The registry defines categories for future action integrations; it does not mean those channels already execute live actions or that every country's rules are populated. Current live checks are wired for social publishing, CMS publication and workflow S5 distribution. Paid-media spending, outbound marketing email, lead-capture publication and tracking changes remain separately gated/not configured until their specific external side-effect paths are implemented and tested.

## Evidence security

Evidence source URLs must be absolute HTTPS and reject embedded credentials, localhost/internal hosts and non-global IPs. Review timestamps require timezone offsets. Do not store secrets or sensitive personal data in source summaries. Only the active workspace's assessments are listed/reviewed. Audited blocked attempts must not call external providers. For a changed target scope, create a new assessment rather than mutating a prior approved decision.

## Operator acceptance

Before enabling live actions, use authoritative regulators/platform documentation and confirm the actual business model, audience location, promotion channel, product category, consent model and applicable rules with qualified counsel or the designated legal reviewer. Include browser/accessibility UAT, source-refresh ownership, escalation/expiry alerts and documented test records. A successful software approval is evidence of an internal decision, not proof that the decision is legally correct.


## Curated source catalogue (prepared 2026-10-28)

The authenticated `GET /api/compliance/source-catalog` endpoint and compliance screen provide a curated **starter subset** of regulator, legislation, self-regulatory and platform-policy references for the US, UK (GB), India (IN), Canada (CA), Australia (AU), EU instruments, and selected global Meta/Google Ads policy pages. Search can filter by jurisdiction, activity, required category and channel.

Catalogue rows carry an explicit jurisdiction scope, source type, optional recorded update date, scope note, and a review-required/non-approved status. The UI only copies the title and URL into the draft evidence form; it does not create evidence or approve it. The reviewer must open the current source, check effective status and applicability, then write and attest a substantive summary. A `GLOBAL` platform policy is supplemental and never satisfies a country-specific evidence requirement.

This is not a comprehensive worldwide law database, not a legal conclusion, and not an automated regulatory-update service. Jurisdiction coverage, product-specific rules, local implementations, sector-specific obligations, commencement dates, enforcement and platform rules change. Do not rely on catalogue membership, source labels, or displayed dates as proof that a source is current or that an activity is lawful. Maintain authoritative sources and appropriate qualified review for every actual target market.
