# CI, UAT and acceptance gates

## GitHub workflow
`.github/workflows/ci.yml` runs on pushes to main/build/**, pull requests to main and manual dispatch. Python verification, Alembic empty SQLite upgrade/drift check, compilation and tests are the backend checks; the frontend uses the committed npm lockfile and `npm ci`, followed by TypeScript typecheck and Next.js production build. A separate `security-audit` job runs `pip-audit` on core/test and optional AI/RAG requirements plus `npm audit --audit-level=high`; its findings must be remediated rather than waived without documented review.

## Required full release gates
- Exact candidate SHA has clean backend test run, front-end typecheck/build, migration graph/upgrade/drift, and dedicated PostgreSQL integration tests.
- API tests cover auth, positive/negative permission, cross-tenant denials, consent, error paths, idempotency and webhook state transitions.
- RAG gold-query/retrieval and generated claim/evidence metrics meet thresholds; prompt injection/poisoned source tests pass.
- Provider tests use authorized sandboxes/accounts, never fake successful connection responses.
- Browser UAT at all specified viewports; accessibility, keyboard/screen reader, performance and responsive table checks.
- Security, dependency licenses, SBOM, secret scan, backup/restore, rollback and staging smoke tests pass.
- Attach actual commit SHA, workflow links/artifacts and result. Missing/no run is `NOT RUN`, not PASS.


## Last verified dependency baseline
- Exact candidate SHA: `e6e6eb4e552b4887da252db0df172dd25ee79561`.
- Push: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40213802242 (success).
- Pull request: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40213808545 (success).
- The successful candidate's regular frontend job used `npm ci`, passed typecheck and production build, and the push-only lockfile sync job passed. Security-audit was added after this checkpoint and needs fresh exact-SHA CI evidence.


## Dependency audit findings — remediation required
- Initial scan of candidate `f129ecf4576f1d35229525669613ecebcf17d65b` reported Pillow 12.3.0 advisories fixed in 13.0.0 and pytest 8.4.2 advisory fixed in 9.0.3. The repository now requires Pillow 13.0.0+ and pytest 9.0.3+; this is not considered resolved until the full Python regression suite and all audit profiles pass on the new exact SHA.
- Because the first Python audit failed early, it did not complete the optional AI/RAG scan or npm audit. Those outcomes must come from a subsequent full run; do not infer a clean result.

- Follow-up dependency resolver finding: the repository previously restricted pytest-asyncio to `<1.0`, which conflicts with the fixed pytest 9.0.3 range. The declared plugin range is now `>=1.3.0,<2.0`; verify installation, test compatibility and audit results on the next candidate SHA.


## AI/RAG dependency-audit exception
- The current ChromaDB 1.5.9 advisory records identify four unpatched IDs and no fixed PyPI release at the time of review. The only permitted temporary CI exception is enumerated in `docs/SECURITY_EXCEPTIONS.md` and is conditional on `scripts/verify_chroma_security_boundary.py` passing. This is not a clean dependency scan or production approval. Replace Chroma or remove the exception after an upstream fix, then rerun audits and full RAG retrieval evaluation.
