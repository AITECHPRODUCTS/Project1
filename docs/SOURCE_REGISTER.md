# Source register

## Sources read/used for this build
- User-provided OmniAffiliateOS v4 engineering contract and follow-on addendum: controls repository target, one-branch strategy, capability status semantics, evidence-first implementation, release gates and truthful reporting.
- User-provided Project1 branch audit dated 2026-10-24: historical findings on branch conflicts, migration collisions, provider coverage, missing CI evidence and skill parity. It is reference evidence, not the target repository.
- User-provided affiliate automation requirement/build ZIPs: product scope, workflows, requirements, source pack and prior implementation files. Selected architecture and service concepts were independently reconstructed into this branch.
- `affiliate-skills-main(1).zip` uploaded on 2026-10-25: MIT-licensed affiliate-skill source package with the 53 skill definitions, shared methodology references, registry/evals, CLI and documentation. It is not a bundled FastAPI/Next.js live application; use its skill behavior as implementation doctrine rather than replacing the Project1 app.
- Source reference doctrine currently in `knowledge/affiliate-skills/shared/references/`; original upstream license is retained at `knowledge/affiliate-skills/LICENSE`.
- Repository-local distilled build contract: `docs/requirements/v4/`.
- Test/CI evidence: actual GitHub Actions runs for exact commit SHAs. See the run links in the GitHub Actions tab.

## Important limitations
This repository does **not** yet contain a byte-for-byte mirror of every source archive, every original source-of-truth file, or all 53 upstream `SKILL.md` files. The requirement pack in `docs/requirements/v4/` is a distilled engineering contract; it must not be misrepresented as the complete raw attachment corpus. Runtime parity is recorded separately in `docs/skill-parity-matrix.csv`. No provider is production-verified just because a catalogue entry or adapter scaffold is present.

## 2026-10-25 continuation note
- The newly uploaded `affiliate-skills-main(1).zip` has been inspected and is a reference skill/specification package, not a deployable web application. The previously shared Library archive `OmniAffiliateOS_build.zip` is an earlier FastAPI/Next.js source snapshot and has been reviewed as a reference; current remote branch code remains authoritative.
- Keep comparing prior attachments and app snapshots against the current branch and traceability backlog. Port only compatible, tested changes; do not overwrite the current app with either archive wholesale.

- Content-decay and content-moat implementations map to the uploaded pack's `skills/blog/content-decay-detector/SKILL.md`, `skills/blog/content-moat-calculator/SKILL.md` and `shared/references/seo-strategy.md`. Their live-source dependencies are intentionally recorded as pending instead of implied by heuristic code.

- Traffic analyzer implementation maps to the uploaded pack's `skills/research/traffic-analyzer/SKILL.md`; the score/compare path uses operator-entered observations only. SimilarWeb/API access and independent traffic-source verification are not implemented by this slice.

- Multi-program portfolio manager maps to `skills/automation/multi-program-manager/SKILL.md`; this slice consumes operator-supplied metrics and is deliberately not represented as a live network integration.


## 2026-10-25 continuation audit
- Re-inventoried prior Library files and inspected the existing `OmniAffiliateOS_build.zip` archive (500 entries; historical FastAPI/Next.js source snapshot) plus `Project1-main(1).zip` (small CI/bootstrap reference). These are earlier project/reference snapshots, not a separate newly uploaded live-app ZIP in the current Library inventory.
- The archived v4 requirements, integration matrix, acceptance traceability, UI/UX, security/privacy, CI/UAT and deployment-operation contracts were used alongside the current branch backlog. Continue porting only changes that can be reconciled with the current branch and tested; do not replace the current application with an archive.
- Current session adds bounded signed-webhook input and serialized full-reversal handling with additional regression coverage. External providers, production PostgreSQL environment and deployment remain unverified until their dedicated gates pass.


## 2026-10-25 verified checkpoint continuation
- Re-checked the current implementation branch and exact hosted Actions runs before editing. The push and pull-request runs for `da5c0c76286df5a7f4ff2fc67d10cd3f3b44fee4` both completed successfully across Python/tests, frontend build, AI/RAG dependency verification and PostgreSQL 16 migration/concurrent-reversal checks.
- Reviewed `Pasted text(6).txt` and `Pasted markdown (2).md` requirements for secure webhooks, deduplication, reversal handling, provider-specific auth/scopes, human-reviewed financial outputs and evidence-based analytics. The existing archive inventory still contains earlier project snapshots, not a distinct newly uploaded live-app ZIP.
- Next security increment adds independent per-network webhook secrets. It does not claim a live network connection or remove the requirement for official provider contract tests.


## 2026-10-25 S6 ledger build
- Conversion/commission ledger increment ports the requirement for idempotent source events, reversal tracking, explicit evidence quality, human-review-safe reporting and currency isolation into a separate append-only table.
- Historical rows are explicitly marked `legacy_unverified`, signed provider webhook observations `signed_webhook_verified`, and compatibility API submissions `api_submitted_unverified`; no provider authorization or real payout is implied.
- The new migration, PostgreSQL direct-SQL immutability tests, SQLite/ORM regression tests and exact-SHA GitHub Actions checks are the current acceptance gates.


## 2026-10-25 — Full Blueprint v3 and pinned source-skill integration
- Reviewed the attached OmniAffiliateOS_Project1_Full_Blueprint_v3(1).md in full (SHA-256 bfc07bdb85388c3a0b62aa168b167b3f378f0384abd223a55dc8d9f50bf104c1). Binding priorities include exact-SHA evidence, no branch creation, current-tree verification, tenant/security checks, provider-state truthfulness, draft-first side effects, durable workflows and production-release gates.
- Pinned source: Affitor/affiliate-skills commit f4cb063a0ee83b1b9e5167e396ab46cc9123dadc; user archive SHA-256 dc463b31d80d6917142d99d9bc7f7b19385e8e0c74ff5c0cc57f4410ed73e1a6. The registry and skills filesystem both contain 53 definitions; upstream README says 52. Registry/filesystem are authoritative and the discrepancy is surfaced in docs/UPSTREAM_SKILL_PARITY.md.
- Source docs/registry/evals/shared references are vendored under knowledge/affiliate-skills/upstream/ with upstream Git blob hashes in SOURCE_MANIFEST.json. They are reference doctrine, not a claim that all 53 app capabilities are implemented. Runtime status remains sourced from docs/skill-parity-matrix.csv.
- scripts/verify_skill_registry.py and a new independent repo-guard Actions job enforce source-blob integrity, 53 source/registry/matrix parity, status-ledger consistency, duplicate detection and the documented README-count mismatch.


## 2026-10-25 verified checkpoint — frontend dependency reproducibility
- The runner-resolved `frontend/package-lock.json` was validated against `frontend/package.json`, passed a clean `npm ci` plus typecheck/build in the lockfile-sync job, and was committed on the existing implementation branch at `4ca16c395a8cd0ac0007848703d7fd71ec23babd`.
- Follow-up workflow commit `e6e6eb4e552b4887da252db0df172dd25ee79561` switched the regular frontend CI install to `npm ci --no-audit --no-fund`. Exact-SHA push run [40213802242](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40213802242) and PR run [40213808545](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40213808545) both passed across Python, PostgreSQL, AI/RAG, frontend and repo-guard jobs. Push-only lockfile sync also passed; it did not create a second commit because the committed lockfile was unchanged.
- Lockfile verification: npm lockfile version 3; 141 package entries, all with resolved tarball identities; root dependency and devDependency declarations match the manifest.
- A separate pip-audit/npm-audit CI gate is now being added as the next P0 security step. Treat its results as pending until new exact-SHA runs complete. Remaining release blockers include secret/SBOM scans, broader tenant/RBAC tests, browser UAT, provider contracts, and backup/restore/staging verification.
