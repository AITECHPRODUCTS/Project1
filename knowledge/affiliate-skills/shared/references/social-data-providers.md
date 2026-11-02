# Authorized social-data providers

This repository supports optional social/content research using properly authorized APIs. Adapter availability depends on the account's permissions, credentials, region, terms, quotas, and endpoint version.

## Data contract

Normalize each returned item with platform, external ID, URL, text/title, author/publication timestamp when returned, observed metrics, source URL, fetch timestamp, API version, and field provenance. Keep absent metrics null. Do not infer that a field is zero because it was not supplied.

## Provider implementation rules

- Use documented official endpoints and supported OAuth scopes. Keep tokens server-side and redact them from logs.
- Respect platform quotas, retry-after headers, pagination, retention and redistribution terms.
- Do not access private groups, private accounts, paywalled data, or restricted research datasets without explicit eligibility.
- Do not deploy prohibited scraping, browser automation, or account-control workarounds.
- If an account or API is not configured, return `not_configured`; do not return mock results or claim provider connectivity.
- Persist cache timestamps and invalidate stale records according to the provider's terms and product requirement.
- Keep ranking derived metrics distinct from provider-supplied counts. Document formula, denominator, sample window, and missing data.
- Do not promise that engagement predicts conversions or that content will go viral.

## Research fallbacks

When authorized APIs are unavailable, use explicitly allowed public research sources or user-supplied URLs. Label limited samples and unknown metrics. A failed provider call must remain a failed/missing result, not be replaced by manufactured data.
