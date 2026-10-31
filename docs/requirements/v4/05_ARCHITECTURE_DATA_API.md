# Architecture, persistence and API

## Baseline
Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy async, PostgreSQL in production, SQLite for local/test only, Alembic migrations, HTTPX, Redis/Valkey for caching/coordination, a durable worker/queue, Next.js App Router/TypeScript/Tailwind, Docker/Compose and GitHub Actions. ChromaDB plus pinned Sentence Transformers embedding profile is the initial local RAG store.

## API discipline
Typed request/response schemas, centralized auth and authorization, tenant boundary, redacted audit trail, request IDs, bounded inputs, timeouts, rate limits, idempotency keys on writes and documented external provider errors. Connected/configured/contract-tested/sandbox-verified/production-verified must remain distinct states.

## Data
Canonical persisted entities include users/workspaces/memberships, offers and terms versions, campaigns, content/asset provenance, consent leads, durable email jobs, workflows/checkpoints/leases, clicks, conversions/reversals, resource reservations, audit events and payout observations.

## Current implementation caveats
Alembic baseline and SQLite upgrade checks have been added. The full workspace/member schema and end-to-end tenant scoping must still be completed and verified. Production must not rely on automatic `create_all` as its migration strategy. Add explicit follow-up migrations for schema changes, PostgreSQL upgrades and restore tests.
