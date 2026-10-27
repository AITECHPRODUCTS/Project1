# Signed ad performance collector contract

## Security boundary

POST /api/webhooks/ad-performance/{workspace_id}/{platform} accepts normalized daily observations from an explicitly provisioned trusted collector. It checks a workspace-and-platform-specific HMAC-SHA256 signature over the exact raw HTTP body before parsing or storing data. A successful HMAC check proves that the configured collector secret signed the body; it does not prove that Meta, Google, TikTok, or another ad network signed the underlying metrics.

Only provision the signing key to a collector that obtains data through an authorized provider API/export and verifies that source itself. Do not mark manually typed/imported reports as trusted. Native provider API credentials and provider-side verification remain separate setup/UAT work.

## Environment configuration

Configure AD_PERFORMANCE_WEBHOOK_SECRETS as a JSON object. Use a valid workspace UUID, supported platform key, and a fresh random secret with at least 32 characters:

    {
      "<workspace-uuid>:meta": "<fresh-random-secret-at-least-32-characters>",
      "<workspace-uuid>:google_search": "<different-random-secret-at-least-32-characters>"
    }

Keys are normalized to lowercase UUID/platform values on settings load. Each workspace/platform pair requires a separate secret. Do not commit real secrets, send them to the browser, or reuse one global secret across tenants. Secret values are not returned from any API.

## Signed request

Send the raw JSON body with X-Ad-Performance-Signature containing the hex HMAC. HMAC is SHA-256 with the configured secret over the exact bytes transmitted. A sha256= prefix is also accepted. Changing whitespace or any body byte changes the signature.

Required fields include provider_event_id, campaign_plan_id, platform, creative_id, non-negative impressions/clicks/conversions/spend/commission, currency, and observed_at with an explicit timezone offset. An optional public source reference is also accepted.

The endpoint rejects payload/platform mismatch, unknown plans, absent workspace-platform secrets, invalid HMAC, oversized bodies, naive timestamps and local/private source URLs. A repeated workspace/platform/event ID is returned as duplicate_ignored rather than stored again. The observation records evidence_status=provider_verified and a SHA-256 digest of the signed body, plus an audit event.

## Operational limits

- provider_verified means a configured trusted collector asserted a source-verification step and the endpoint verified that collector HMAC. It does not mean Project1 independently authenticated a native provider response.
- Stop-loss evaluation requires all plan-linked observations to have verified status. If a plan has mixed evidence, evaluation is blocked rather than combining it.
- Stop-latch and kill-switch state are internal review controls only. This endpoint never starts, pauses, edits, or spends on a live ad account.
- Before staging, test key rotation, deployment secret injection, event replay, concurrent duplicate delivery, provider export normalization to daily creative snapshots, and revocation.


## Docker Compose deployment
Set AD_PERFORMANCE_WEBHOOK_SECRETS in the deployment .env as a JSON object keyed by <workspace UUID>:<platform>, for example {} before configuring a collector. Compose forwards the value to the API container. Store real keys in the deployment secret store, not in the repository or frontend. A setting only enables HMAC authentication for a trusted collector; the collector must obtain and verify native provider data through an authorized provider path before signing.
