# OmniAffiliateOS build checkpoint — 1 November 2026

**Repository:** `AITECHPRODUCTS/Project1`  
**Branch:** `build/omni-affiliate-os-production` (existing branch only)  
**Parent HEAD:** `cf014a1070359ad3b8c2cb2e860884cb78325150`  
**Release decision:** **NOT PRODUCTION READY / NOT DEPLOYED**

## Increment: native WooCommerce inbound order webhooks

- Added `backend/adapters/woocommerce_webhook.py` for exact-raw-body Base64 HMAC-SHA256 signature verification, topic/delivery-ID validation, paid-order normalization, explicit renewal linkage and exact-full-refund gating.
- Reused the existing merchant integration, encrypted-secret, receipt, conversion and append-only ledger tables. No database migration was introduced.
- The merchant integration creation flow recognizes `provider_name=woocommerce`, stores a provider-specific integration type and returns the one-time signing secret. Listing APIs do not return secret material.
- The webhook receiver verifies `X-WC-Webhook-Signature`, `X-WC-Webhook-Topic` and `X-WC-Webhook-Delivery-ID`. Only `order.created` and `order.updated` are accepted for normalization.
- Paid `processing`/`completed` orders require positive total, valid currency, GMT paid timestamp and explicit order metadata for affiliate attribution. Renewal orders require `omni_original_order_id` pointing to the original order.
- Stable order identities prevent repeated updates from creating duplicate commissions. Changed later order payloads with a distinct provider delivery ID are acknowledged as already recorded while the first accepted conversion evidence remains unchanged.
- A full refund is reversed only when Woo status is `refunded` and cumulative refund records exactly equal the original order total. Partial/inconsistent refunds and missing attribution/time evidence are durably routed to manual review.
- Updated merchant setup UI and integration documentation with explicit limitations.

## Connector boundaries

This is signed inbound order-event ingestion only. No WooCommerce REST API authentication, programmatic webhook provisioning, product/catalogue/price/inventory sync, customer sync, checkout customization, automatic refund initiation or payout transfer was added. Live store payload verification remains outstanding.

## Verification and rollout gates

Run adapter tests, merchant lifecycle integration tests, full Python suite, frontend typecheck/production build, PostgreSQL migration drift, browser UAT, security/secret/SBOM checks, Docker build and exact-commit push + PR workflows. Record actual run IDs/results below; do not mark this increment verified before they complete.

Update the Windows Docker copy only after exact-commit CI is green and the local `.env` plus database/Redis volumes are backed up. Use a normal `docker compose up --build -d` update; never use `docker compose down -v` for an ordinary update.

Remaining release blockers include live provider authorization/UAT, 53-skill end-to-end validation, commission/refund/manual-adjustment operations, approved distribution/ad execution, queue/incident handling, security/load testing, backup/restore/rollback/DR, monitoring and commercial/legal sign-off.
