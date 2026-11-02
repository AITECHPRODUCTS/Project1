# Integrations and provider coverage

## State semantics
`catalogued_disabled`, `not_configured`, `configured_not_health_checked`, `contract_tested`, `sandbox_verified`, `production_verified`, and `not_implemented` must remain distinct. No enabled flag or API key proves successful authentication, account eligibility, permitted scope, or write capability.

## Provider scope
The catalogue currently lists 168 affiliate, commerce, software, social, CMS, email and ad platforms. Most are catalog-only and disabled; a directory adapter and generic/proxy/webhook boundaries are not native production integrations. Current actual provider/account status must be checked per environment.

## Required adapter contract
Credential acquisition/refresh/revocation; stable IDs; pagination/rate-limit handling; typed response mapping; timestamps/currency/geography; retries/backoff; source evidence; errors; idempotency; read/write scope separation; secret redaction; live/sandbox evidence and account-specific prerequisites.

## Platforms that may require manual action
Merchant/network approval, KYC, Amazon/other program application, API app review, OAuth scope approval, payment receipt and channels with no permitted public-write API remain manual or unsupported. No CAPTCHA bypass, prohibited scraping, policy-evasion or fabricated API success.
