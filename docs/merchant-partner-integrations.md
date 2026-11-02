# Merchant partner integration lifecycle

## Current capability in this release slice

OmniAffiliateOS supports a first-party merchant-to-publisher program workflow:

1. A merchant creates an offer and records commission, currency, attribution, cookie and payout-policy terms.
2. A distinct merchant workspace owner/admin reviews seller authorization and program terms, then lists the approved offer.
3. A publisher discovers the listing and applies with website, audience, channels, regions and promotion plan.
4. The merchant approves or rejects the application. Approval creates a publisher-owned campaign and first-party tracking URL with a subid click identifier.
5. The merchant connects a supported conversion event source. Credentials are encrypted at rest, never returned from list APIs, and can be rotated or disabled.
6. Valid events are attributed to the original publisher campaign and recorded as pending commission observations in the append-only ledger. Duplicate event IDs are idempotent.
7. Merchant payout readiness applies refund holds and minimum thresholds. It is a review queue only; it does not confirm payment or transfer funds.

## Native Stripe webhook setup

The first native merchant checkout adapter is Stripe webhook ingestion. It verifies the endpoint-specific signing secret (whsec_...) and Stripe-Signature timestamped HMAC against the exact raw request bytes. Signatures outside the five-minute replay window are rejected.

1. In Merchant → Business integrations, create a native Stripe endpoint for the relevant merchant program.
2. Copy its webhook URL into Stripe Workbench → Webhooks.
3. Subscribe the endpoint to payment_intent.succeeded, invoice.paid, charge.refunded and charge.dispute.created.
4. Copy that endpoint's whsec_ signing secret from Stripe and save it against the same OmniAffiliateOS integration. The secret is encrypted at rest and never displayed again.
5. Send a Stripe test event and inspect the integration's last accepted event/status.

The merchant's existing checkout setup must preserve the OmniAffiliateOS click reference as omni_click_id metadata on the PaymentIntent or initial subscription invoice. For subscription renewals, preserve the initial PaymentIntent ID as omni_original_payment_intent_id on each renewal invoice (or continue including the click ID). Current Stripe invoice snapshots may expose paid payments through the payments collection rather than the legacy payment_intent field; the adapter handles either a legacy single PaymentIntent or a single paid payment in that collection. If the event snapshot does not include a usable PaymentIntent reference, OmniAffiliateOS does not infer one and returns a non-success result for manual reconciliation. Verify the actual event shape against a Stripe test endpoint and your account's API version before enabling live attribution.

For sales and renewals, the normalized internal event identifier is the Stripe PaymentIntent ID. This lets a later full charge.refunded event link to the original commission without adding a second attribution identifier. The Stripe envelope event ID is also preserved in conversion evidence.

## Native WooCommerce order webhooks

WooCommerce signs the exact raw JSON request body with HMAC-SHA256 and sends the Base64 digest in `X-WC-Webhook-Signature`. The receiver also requires `X-WC-Webhook-Topic` and `X-WC-Webhook-Delivery-ID`. Configure active `order.created` and `order.updated` webhooks in WooCommerce → Settings → Advanced → Webhooks, using the endpoint URL and one-time secret displayed by OmniAffiliateOS. A valid signature alone does not mark the integration connected; a paid, attributed conversion must be accepted.

A sale requires an order status of `processing` or `completed`, a positive `total`, a three-letter currency, a WooCommerce GMT paid timestamp, and order-level `omni_click_id` metadata. The adapter also recognizes `affiliate_click_id`, `click_id` and `subid`. The merchant checkout, theme or plugin must persist this value from the affiliate tracking URL; OmniAffiliateOS does not infer attribution from customer fields.

A renewal order must include order-level `omni_original_order_id` metadata containing the original Woo order ID. This explicit relationship is required to attribute a renewal to the original approved affiliate conversion. The merchant's subscription extension or server-side hook must preserve this metadata.

A full refund is reversed only when the Woo order status is `refunded` and the sum of the refund records equals the original order total exactly. Partial or inconsistent refunds, missing refund detail, and missing attribution/time evidence are stored for manual review rather than treated as full reversals. Repeated `order.updated` notifications use a stable order conversion identity and cannot create a second commission for the same order.

## Custom signed event relay

For other checkout/billing systems, the merchant server can send normalized sale, recurring-renewal, refund or chargeback events to the merchant-specific endpoint. Sign the exact raw JSON request body with HMAC-SHA256 and send the hex digest in X-Omni-Signature with a sha256= prefix. Keep the generated secret only on the merchant server. Rotate it from the merchant integrations page if exposed or lost.

Sale requires event_id, event_type=sale, click_id (or subid), revenue and currency. A renewal can use its click ID or reference the original signed sale with original_event_id. Custom full refunds and chargebacks require event_id, event_type, original_event_id and currency.

## Explicit boundaries

- Stripe is a webhook receiver integration, not Stripe OAuth or a Stripe API integration. OmniAffiliateOS does not create Checkout Sessions or PaymentIntents, change Stripe checkout configuration, manage products/prices, sync catalogues, initiate refunds, or read merchant Stripe balances.
- Stripe payment_intent.succeeded is accepted only when successful and when affiliate click metadata is present. The click reference must be saved by the merchant's checkout flow; OmniAffiliateOS does not infer missing attribution.
- Stripe invoice.paid is accepted only for subscription creation/cycle, with a usable PaymentIntent reference, and when it is not paid out of band. Renewal attribution requires the original PaymentIntent metadata or the same stored click reference.
- Only full Stripe charge refunds are automatically reversed. Partial refunds return a manual-reconciliation result and do not silently reverse the entire commission. Stripe disputes/chargebacks are also returned for manual reconciliation rather than automatically marking a conversion reversed.
- An offer has a single integration row. To switch a custom relay to native Stripe, disable the existing relay first; the native endpoint reuses that row and leaves prior conversion evidence/receipts intact.
- The generic HMAC relay still supports full refund and chargeback reversals. Partial refunds are not part of this release slice.
- Provider-native catalogue/terms synchronization and external affiliate-network applications/approval reconciliation are not included. Product details and affiliate terms remain merchant supplied and human reviewed.
- The payout screen reports evidence-backed readiness after refund holds and minimum thresholds. It does not create payable balances, reconcile bank transfers or initiate money movement.
- No integration sends ads, publishes content, changes merchant checkout settings or transfers money on the merchant's behalf.


## WooCommerce release boundaries

- This is a signed inbound order webhook receiver, not WooCommerce REST API authentication, programmatic webhook provisioning, catalogue/product import, merchant-program synchronization, inventory sync, customer data sync or checkout customization.
- The adapter has not been validated against a live merchant store, payment gateway, custom order status or subscription plugin. Confirm actual payload and metadata behavior with test orders before production use.
- WooCommerce's native delivery ID is required. The receiver does not invent a delivery timestamp or claim replay-window protection because the standard WooCommerce webhook signature does not contain a timestamp.
- Partial refunds and inconsistent refund histories remain in a manual-review queue. The current operator view lists receipt IDs/outcomes but does not yet provide complete payload-detail inspection or commission-adjustment controls.
