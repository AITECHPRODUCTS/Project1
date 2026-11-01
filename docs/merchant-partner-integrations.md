# Merchant partner integration lifecycle

## Current capability in this release slice

OmniAffiliateOS supports a first-party merchant-to-publisher program workflow:

1. A merchant creates an offer and records commission, currency, attribution and payout-policy terms.
2. A distinct merchant workspace owner/admin reviews seller authorization and program terms, then lists the approved offer.
3. A publisher applies with website, audience, channels, regions and promotion plan.
4. The merchant approves the application. OmniAffiliateOS creates a publisher-owned campaign and exposes a first-party tracking URL with a subid click identifier.
5. A merchant creates a signed webhook receiver for the offer. The generated signing secret is shown once and encrypted at rest.
6. The merchant checkout server stores the affiliate subid with the order and sends normalized sale, recurring-renewal, refund or chargeback events. The exact raw JSON body must be signed with HMAC-SHA256 and sent in X-Omni-Signature with a sha256= prefix.
7. Valid events are attributed to the original publisher campaign and recorded as pending commission observations in the append-only ledger. Duplicate event IDs are idempotent. Refunds and chargebacks fully reverse a referenced original event.

## Normalized event contracts

Sale requires event_id, event_type=sale, click_id, revenue and currency.

Subscription renewal may include its stored click_id or reference the original signed sale event using original_event_id.

Refund and chargeback require event_id, event_type, original_event_id and currency.

Generate the signature over the exact raw request bytes, not a re-serialized JSON object. Keep the generated secret only on the merchant server. Rotate it from the merchant integrations page if exposed or lost.

## Explicit boundaries

- This webhook adapter receives a normalized event relay. Provider labels such as Stripe, Shopify or WooCommerce describe the merchant's event source; they do not mean that native OAuth, provider-specific signature verification or API catalogue synchronization is implemented by this adapter.
- Product details and affiliate terms remain merchant supplied and human reviewed in this release slice.
- First-party click attribution respects the configured sale attribution window when the merchant provided one. Subscription renewals refer back to the initial signed event.
- Full refund and chargeback reversals are supported. Partial refunds are not part of this initial integration.
- Ledger records are evidence-backed observations, not a paid balance. Refund hold, minimum payout and payout schedule are published program terms; payout reconciliation, payment-provider setup and funds-transfer execution remain separate work.
- No integration sends ads, publishes content, changes merchant checkout settings or transfers money on the merchant's behalf.
