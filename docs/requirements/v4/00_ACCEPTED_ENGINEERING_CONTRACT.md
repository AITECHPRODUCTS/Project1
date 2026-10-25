# Accepted engineering contract

## Mission
Build OmniAffiliateOS as an original operations platform for the permitted affiliate lifecycle: research, offer validation, program eligibility and application tracking, content/media, SEO, landing pages, consented leads, authorized distribution, attribution, commission reconciliation and evidence-based learning.

## Product-side flows
1. **Publisher / affiliate:** discover offers, inspect terms and geography, apply to programs, record approval/decline, create tracking links, draft compliant assets, publish through authorized channels, measure clicks/conversions, reconcile pending/approved/reversed/paid commissions, and pause/export campaigns.
2. **Merchant / product owner:** prove authority over an offer, version product facts and terms, define actual commission/region/channel rules, review affiliate applications, deliver approved assets, and inspect aggregate partner performance.
3. **Platform Super Admin:** separately authorized platform health, tenants, queues, integrations, usage/cost, abuse, alerts, retention/deletion, releases and kill switches. Workspace-admin is not global-admin.

## S1–S8
S1 research and opportunity evidence; S2 source-grounded content intelligence; S3 SEO/blog; S4 offers/landing/consent; S5 authorized distribution/nurture; S6 attribution/experimentation; S7 operational/budget controls; S8 reviewed performance memory and learning.

## Implementation discipline
Each vertical slice includes migration/model, business service, typed API, authorization/audit, frontend client and states, tests, documentation and traceability. Keep a single implementation branch, serialize changes, and use one PR to main. Do not merge or deploy until the selected commit passes the release gates.

## External blocker policy
When an API, credential, platform approval or production secret is unavailable, ship the complete safe boundary and mark the capability precisely (`not_configured`, `manual_provider_flow`, `approval_required`, `not_supported`); never fake success. This build’s chosen target is the user-directed public `AITECHPRODUCTS/Project1`, despite earlier prompts preferring a private repository; protect that public repo accordingly.

## Continuous-build thumb rule — added 2026-10-25

- Continue the highest-priority unblocked implementation slice without asking the user to repeat the master command or issue another instruction. Review prior chats and available attachments first, build code and regression tests on the one Project1 build branch, run hosted workflows and fix failures, then update traceability and status. A scheduled ZIP reminder does not pause implementation. On receipt of the live-application ZIP, audit it and port selected code only after compatibility, security, license and test review.
