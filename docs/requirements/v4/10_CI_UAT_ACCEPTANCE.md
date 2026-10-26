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


## 2026-10-26 exact-SHA full matrix
- Candidate `668b33670ea11e30f97ccc3c6e50180124609207`: push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264037056 and PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264040473 both passed.
- Confirmed: repository guard/53-skill parity, Python suite, SQLite migration/drift, PostgreSQL migration/concurrency, AI/RAG imports, frontend `npm ci`/typecheck/build, core/test and AI/RAG audits, frontend `npm audit --audit-level=high`, and lockfile sync.
- The ChromaDB temporary exception remains a release blocker; these successful runs must not be presented as complete production release approval.

## 2026-10-26 CI runtime maintenance
- Workflow actions were using old releases with Node 20 runtime warnings. Node 20 was removed from GitHub-hosted Actions on 23 September 2026; action releases must support Node 24. This checkpoint updates those action versions; validate the exact updated workflow before advancing.


## 2026-10-26 CI runtime update verified
- Exact SHA `70dd041a8c27607467f8605d1eabad09f815d2bf`: https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264278741 — success using Node 24-compatible `checkout@v7`, `setup-python@v7`, `setup-node@v7`, `upload-artifact@v7`, and `download-artifact@v8`.
- Next: the newly added auth/tenancy regression tests are not yet verified; require full CI on their commit. The Chroma exception remains a production security blocker.


## 2026-10-26 WebSocket tenancy P0 regression gate
- Require passing tests showing workflow/HITL events reach only sockets registered to the matching workspace, scope-less event payloads reach no client, and a connection using a revoked workspace membership is rejected.
- This candidate source fix and tests are not complete until the full Python, PostgreSQL, AI/RAG, frontend, repository guard and security-audit jobs pass on the exact new commit SHA.


## 2026-10-26 WebSocket tenant isolation — exact-SHA verification
- Verified fix and tests on `65a5a884acf0195a2720cb6de76a5279fd4e5dde`: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265255592 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265259440 both passed.
- Required test assertions include workspace-matched event delivery only, scope-less event dropping, workflow emitter scope propagation, and denied connection for revoked membership.
- Next: workflow run status/pause/resume/retry/cancel must verify actor and workspace ownership, with negative cross-tenant tests.


## 2026-10-26 workflow lifecycle ownership — verified
- Candidate SHA 16eee55a6935e9afa1d5f2b020c867713754aa67: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265845238 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265848400 both completed successfully.
- Checks include Python suite with workflow/tenant tests, PostgreSQL migrations and concurrent reversal test, AI/RAG imports, frontend checks/build, 53-skill source guard, audits and lockfile verification.
- Remaining conditional exception: four documented ChromaDB advisories still prevent a clean AI/RAG security result and production approval.
- Next P0 review: gate shared knowledge-index ingestion to platform operations and remove internal absolute path leakage.
