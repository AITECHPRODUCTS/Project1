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

## Optional runtime dependency profiles

The base `requirements.txt` installs the FastAPI/database/security runtime without pulling the CUDA-enabled PyTorch stack into routine test environments.

- Core API and unit tests: `pip install -r requirements-dev.txt`
- RAG and hosted-model adapters on CPU: `pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements-ai.txt`
- Video/TTS rendering: `pip install -r requirements-video.txt`
- Optional local Transformers/LoRA runtime: install the desired CPU/CUDA PyTorch build, then `pip install -r requirements-local-model.txt`

The Docker image enables the AI/RAG and video profiles by default. Set the corresponding `INSTALL_*_PROFILE` build arguments to opt out; local-model dependencies are disabled by default. GitHub Actions validates core behavior and checks AI/RAG imports in a separate CPU-only job.


### Signed ad performance collector

See docs/SIGNED_AD_PERFORMANCE_INGESTION.md. A per-workspace/per-platform HMAC key authenticates a trusted collector-provided normalized daily report. The collector must independently verify the underlying ad-platform source before signing. The endpoint does not establish a native provider account connection and does not execute ad changes.


### Frontend production dependency boundary

The current UI does not import next/image, so the optimizer is disabled. The frontend Docker build prunes optional/native image packages before the final image layer is committed and verifies the actual runtime dependency tree. CI emits both a complete build/install SBOM and a separate production SBOM; only the production SBOM is evaluated as the shipped runtime, with the license checker invoked without exceptions. Do not add next/image until its dependency and license impact has been reviewed and the runtime policy/test is intentionally revised.


The signed ad-performance collector can be configured with AD_PERFORMANCE_WEBHOOK_SECRETS in .env as a JSON map keyed by <workspace UUID>:<platform>. Start with {}; provision fresh per-workspace/platform secrets out of band. See docs/SIGNED_AD_PERFORMANCE_INGESTION.md. This HMAC authenticates a trusted collector, not the native ad network, and never enables live ad changes.


### Jurisdiction compliance evidence

Open \`/compliance\` to register cited source evidence per activity, channel and target jurisdiction, inspect missing/stale coverage, and record a human review decision. Newly initiated live social/CMS publications and S5 live distribution require current matching approval. Drafts and dry-runs remain available. The product does not automatically determine all countries' laws or provide legal advice; qualified reviewers must validate authoritative sources and applicability. Other paid-media, email, lead-capture and tracking integrations require separate live-action integration/UAT.
