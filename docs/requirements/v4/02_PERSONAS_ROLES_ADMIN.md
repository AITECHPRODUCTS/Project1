# Personas, roles and administration

## Roles
- Platform Super Admin / Operations: global infrastructure and tenant lifecycle, separate authorization.
- Platform support/operator: limited support tools, audited access.
- Workspace owner/admin: workspace settings, members, integration credentials, budgets and kill switches.
- Affiliate member: offer research, links, content drafts and campaign analytics.
- Merchant member: owned offer facts/terms, affiliate application decisions and partner analytics.
- Analyst/read-only: reports without write capabilities.
- Compliance reviewer: content claims/disclosures, provider policy and audit evidence.

A user may be both publisher and merchant in separate workspaces. Role choice must not imply ownership of an external product or approval by an affiliate network.

## Platform control surface
Global overview: API/error and workflow success/failure rates, queue age/dead letters, provider health, webhook lag, DB storage/connections, backups, model/video usage/cost, quota and alerts.
Tenant registry: search, membership, suspension with reason, usage, export/deletion requests, audit history.
Worker operations: sanitized runs/inputs/outputs, correlation IDs, safe retry/replay/cancel and dead-letter resolution.
Integration registry: provider/account/workspace status, tested scope/version, last healthy check, expiry metadata and independent read/write capability.
Cost/security: budgets, usage, limits, feature flags, kill switches, abuse signals and audit export.
Release: current main/deployed SHA, actual CI/UAT, migration and rollback state.

## Current gap
The branch includes a workspace capability outline and several admin-gated routes, but not yet a complete global Super Admin lifecycle or independently proven cross-tenant authorization. Do not mark this acceptance item complete until it is implemented and covered with negative isolation tests.
