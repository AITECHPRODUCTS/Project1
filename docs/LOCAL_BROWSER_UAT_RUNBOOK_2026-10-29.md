
# OmniAffiliateOS — Local Browser User-Acceptance Runbook

**Repository:** https://github.com/AITECHPRODUCTS/Project1  
**Working branch:** build/omni-affiliate-os-production  
**UI:** http://localhost:3000  
**API liveness:** http://localhost:8000/health  
**API readiness:** http://localhost:8000/health/ready

## Important test boundary

The latest hosted Chromium UAT passed 30 browser tests, using the production Next.js build and a test API inside an isolated GitHub Actions runner. That does **not** constitute a test in your personal Windows browser. This document guides a local hands-on acceptance test; do not mark it complete until you actually run it and record the observed results.

Use a local development/test environment only. Do not enter production customer data, commit .env, paste secrets into chat, or enable paid ads, publishing or email writes merely to test the interface.

## 1. Confirm the existing branch and protect local changes

Open PowerShell in your existing repository clone:

    git status --short
    git branch --show-current
    git fetch origin

The target branch is build/omni-affiliate-os-production. If git status --short shows edits you need, stop before pulling and preserve them using your normal backup process. Do not reset or discard local work. If the existing local branch is clean, update it by fast-forward only:

    git switch build/omni-affiliate-os-production
    git pull --ff-only origin build/omni-affiliate-os-production
    git rev-parse HEAD

Record the SHA returned by git rev-parse HEAD in your UAT notes. The verified code checkpoint recorded on 29 October 2026 is 0fc63b68e53385479f6c1ab69791fbb869719edd; later documentation-only commits may advance the branch head.

## 2. Configure a safe local environment

Prerequisites: Git, Docker Desktop with Compose support, and a modern browser. From the repository root:

    Copy-Item .env.example .env

Edit .env locally. Set APP_ENV=development, APP_PUBLIC_URL=http://localhost:8000, CORS_ORIGINS=http://localhost:3000, and NEXT_PUBLIC_API_BASE_URL=http://localhost:8000. Generate distinct random values for APP_SESSION_SECRET, TRACKING_HMAC_SECRET, AFFILIATE_WEBHOOK_SECRET and POSTGRES_PASSWORD. For example, generate one value at a time with:

    python -c "import secrets; print(secrets.token_urlsafe(48))"

Use a different generated value for every variable; do not use example/test-only credentials from CI. Configure a fresh local INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD.

Keep external actions disabled for this test:

    LLM_BACKEND=offline
    PUBLISHING_DRY_RUN=true
    AD_AUTOMATION_EXECUTE=false
    CMS_PUBLISH_EXECUTE=false
    GITHUB_PAGES_DEPLOY_EXECUTE=false
    API_BIND_ADDRESS=127.0.0.1
    UI_BIND_ADDRESS=127.0.0.1

Leave affiliate, social/CMS, email, ad-network and CRM production credentials unset unless you are deliberately testing a separately approved sandbox account. Do not set live execution flags to true.

## 3. Start the app and verify service health

    docker compose config --quiet
    docker compose up --build -d
    docker compose ps
    Invoke-RestMethod http://localhost:8000/health
    Invoke-RestMethod http://localhost:8000/health/ready

Both health endpoints should return successful responses. The API readiness check proves database reachability, not full production readiness. If a service is unhealthy, inspect:

    docker compose logs --tail 200 api
    docker compose logs --tail 200 frontend
    docker compose logs --tail 100 postgres
    docker compose logs --tail 100 redis

Then open http://localhost:3000 in your local browser, sign in with the local initial-admin account configured above, and create/select a local test workspace if prompted.

## 4. Hands-on acceptance checklist

Mark every item PASS, FAIL or BLOCKED and write down the actual observed result. Do not treat sample data or a successful UI message as proof of provider activity.

| Area | Local browser action | Acceptance criterion |
|---|---|---|
| Startup and authentication | Open dashboard, sign in, refresh, sign out/in again | Session and protected-route behavior is correct |
| Workspace boundary | Select a local workspace; inspect its records; attempt foreign-record access only if you have a deliberately prepared second test workspace | No data from another workspace is disclosed |
| S1 research/offers | Search/filter/sort offers, create a shortlist, add a note, reopen it, remove an item | Unknown provider metrics remain unknown; shortlist actions do not mutate shared catalogue rows |
| Offer qualification | Open the qualification queue, filter and page through results, inspect incomplete evidence | Internal operator qualification is not presented as affiliate-network approval |
| S2 content research | Submit a public HTTPS source and inspect status, excerpt/hash and claim ledger | Failed sources remain failed; quote match is not presented as independent truth verification |
| S2 comparison/listicle | Create a test comparison/listicle, inspect unknown/failed/observed facts, save/reload/reopen and create a revision | Draft/evidence states persist, unknowns remain explicit, original revision remains unchanged |
| S3 freshness/compliance | Inspect freshness/compliance coverage; attempt approval against stale or missing evidence | Required approvals fail closed where evidence is stale/missing; UI does not claim a complete worldwide legal database |
| S4 lead/consent | Use a test email in an authorized local flow; inspect consent and suppression state | Consent/disclosure state is explicit; do not send real marketing email during this test |
| S5 distribution/ads | Create a draft/queue item; inspect approval, budget and execution status | It remains draft/review/dry-run; no live post, paid spend or provider write occurs |
| S6 commission/analytics | Inspect empty finance ledgers and any clearly labelled test record | Empty ledger remains empty; estimates are not presented as earned/paid commissions |
| Platform execution pause | If the local account is explicitly Platform Super Admin, inspect pause/resume controls and verify blocked actions do not call providers | Missing controls fail closed; do not test by sending real posts/emails |
| Error/recovery | Stop/restart the local stack after saving a draft; reload the saved record | Errors are visible; saved data recovers without false provider-success claims |

Use the rendered navigation instead of assuming every route name remains unchanged. Some generation actions may be unavailable with offline LLM configuration; that configuration limitation is not proof of a connected model/provider.

## 5. Optional automated browser suite against the local UI

Install the development test dependencies and Chromium in the same local Python environment:

    python -m pip install -r requirements-dev.txt
    python -m playwright install chromium
    $env:BROWSER_BASE_URL = "http://127.0.0.1:3000"
    python -m pytest -q browser_tests

Some browser tests intercept individual API contracts with test fixtures. Run them alongside—not instead of—the manual checks against your local API/database above.

## 6. Save evidence and stop safely

Record the source SHA, browser/OS version, start time, test account/workspace identifiers using non-sensitive IDs, each PASS/FAIL/BLOCKED result, screenshots with secrets/customer data removed, and sanitized logs. Never include passwords, cookies, access tokens, webhook secrets or private lead information.

To stop containers without deleting persistent local database volumes:

    docker compose down

Do not run docker compose down -v unless you explicitly intend to delete the local test database and uploaded test artifacts.

## Current status

- Hosted exact-head Chromium UAT on 29 October 2026: **30 passed**.
- Manual test in the user's personal local browser: **not yet performed/observed by the agent**.
- Provider/account live UAT and production deployment: **not established by this runbook or CI**.
