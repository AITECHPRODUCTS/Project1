# OmniAffiliateOS — Omnichannel Affiliate Marketing OS

OmniAffiliateOS is an evidence-first affiliate operations platform designed to connect offer discovery, content production, SEO, compliant landing pages, consent-based lead capture, authorized publishing, attribution, commission reporting, and a reviewable S1–S8 performance loop.

## Current build

- **Repository:** https://github.com/AITECHPRODUCTS/Project1
- **Build branch:** `build/omni-affiliate-os-production`
- **Development:** Python 3.11+, FastAPI, SQLAlchemy, Next.js App Router, TypeScript and Tailwind.
- **Local workflow:** copy `.env.example` to `.env`; install `requirements-dev.txt`; install `frontend/package.json`; run `python scripts/verify_project.py`, `pytest -q`, `npm run typecheck` and `npm run build`.
- **Containers:** `docker compose up --build` once secrets in `.env` are configured.

## Non-negotiable boundaries

A network listing or config flag is not an account connection, provider approval, current commission, or write permission. Publishing, emails, paid media and application submissions must pass authorization, budget, disclosure, idempotency and audit gates. Dry-run is the default. Do not use prohibited scraping/UI automation, evade platform restrictions, or publish bulk unsolicited content. Payouts are observations and reconciliation only—no automatic transfer. No revenue is promised.

## Verification status

GitHub Actions runs on pushes to `main` and `build/**`, pull requests to `main`, and manual dispatch. The authoritative run/check result must be reviewed before release. This repository is not considered production-ready until tests, migrations, provider authorization, security, accessibility and staging health checks pass on a single candidate SHA.

See `docs/IMPLEMENTATION_STATUS.md`, `docs/REQUIREMENTS_TRACEABILITY_MASTER.md` and `docs/skill-parity-matrix.csv` for the status of each tracked capability.
