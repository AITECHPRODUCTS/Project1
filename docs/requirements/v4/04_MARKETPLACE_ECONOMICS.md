# Marketplace economics and ledger

## Offer facts
Store network vs internal merchant vs operator-import source, owner/rights, versioned terms/effective dates, commission type/rate/currency/conditions, attribution period only if reported, allowed regions/channels, restrictions, source URL, observation time, expiry and confidence.

## Ranking and forecasting
Use explicit explainable factors and weights; support missing features and scenario assumptions. Network-specific recurring/tiered/capped commission, currency, refunds, reversals and payout hold rules must not be collapsed into one universal rate. Estimates are scenarios, not expected income.

## Append-only finance evidence
- Use decimal currency arithmetic in the production ledger (current prototype stores floats; conversion before production is required).
- Record provider/network ID, transaction/event ID, click ID, original event, timestamps, currency, amount, state, source payload hash/evidence and idempotency.
- Pending, approved, reversed, paid, pending-verification and unmatched reversal remain distinct. Corrections are compensating entries, not destructive rewrites.
- A payout threshold or confirmation email is not proof of bank receipt.
- No automatic bank transfer is implemented or authorized in this scope.

## Merchant workflows
Only verified product representatives may activate an internal merchant offer. Internal commission terms are not evidence of money paid by an affiliate network. Affiliate applications require an explicit merchant decision and audit trail.
