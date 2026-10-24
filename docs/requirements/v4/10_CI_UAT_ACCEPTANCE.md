# CI, UAT and acceptance gates

## GitHub workflow
`.github/workflows/ci.yml` runs on pushes to main/build/**, pull requests to main and manual dispatch. Python verification, Alembic empty SQLite upgrade/drift check, compilation and tests are the backend checks; npm typecheck and Next.js production build are frontend checks.

## Required full release gates
- Exact candidate SHA has clean backend test run, front-end typecheck/build, migration graph/upgrade/drift, and dedicated PostgreSQL integration tests.
- API tests cover auth, positive/negative permission, cross-tenant denials, consent, error paths, idempotency and webhook state transitions.
- RAG gold-query/retrieval and generated claim/evidence metrics meet thresholds; prompt injection/poisoned source tests pass.
- Provider tests use authorized sandboxes/accounts, never fake successful connection responses.
- Browser UAT at all specified viewports; accessibility, keyboard/screen reader, performance and responsive table checks.
- Security, dependency licenses, SBOM, secret scan, backup/restore, rollback and staging smoke tests pass.
- Attach actual commit SHA, workflow links/artifacts and result. Missing/no run is `NOT RUN`, not PASS.
