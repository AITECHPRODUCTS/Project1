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


## 2026-10-25 security-audit first result and remediation
- The newly added `security-audit` job on `f129ecf4576f1d35229525669613ecebcf17d65b` failed on `pip-audit -r requirements-dev.txt`: Pillow 12.3.0 has advisories whose listed fix is 13.0.0; pytest 8.4.2 has a PYSEC advisory whose listed fix is 9.0.3. The optional AI/RAG profile and npm audit steps were not reached in that job.
- Updated requirement bounds to `Pillow>=13.0.0,<14.0` and `pytest>=9.0.3,<10.0` without allowlisting the vulnerabilities. Full compatibility and scan status are pending the new exact-SHA workflow runs.


## 2026-10-25 dependency resolver compatibility correction
- The first fixed-range retry exposed a conflict in the manifest rather than another vulnerability: `pytest>=9.0.3` cannot resolve with `pytest-asyncio<1.0`. The requirement now allows `pytest-asyncio>=1.3.0,<2.0`, whose upstream release notes identify pytest 9 support from 1.3.0. No scan is considered passed until all exact-SHA jobs finish.


## 2026-10-25 AI/RAG dependency audit and Chroma security boundary
- The core/test dependency audit passed after updated Pillow/pytest ranges and the pytest-asyncio resolver fix. The first optional AI/RAG scan found fixable pre-1.0 LangChain packages plus ChromaDB 1.5.9 advisories `PYSEC-2026-311`, `PYSEC-2026-3814`, `PYSEC-2026-3815`, and `PYSEC-2026-3813`; the cited upstream records had no fixed PyPI release as of this review.
- Requirements are moving to compatible audited LangChain 1.x releases; legacy `RetrievalQA` is switched to `langchain-classic`. A local-only Chroma boundary checker/test is added before the temporary audit exception. Only those four exact IDs may be excepted after the guard passes; the workflow emits a warning and product release remains blocked. Exact-SHA verification is pending.


## 2026-10-28 source review checkpoint
- Inspected the current uploaded build brief and prior Library archives, including the 2,273-line master build guide, product requirements, S1–S8 functional contract, security/privacy/compliance contract, CI/UAT acceptance, and requirement traceability backlog.
- Verified that duplicate copies of `100%AutopilotAffiliatesystem_24102026.zip` and `AutopilotaffiliateRequirement_231026_0850.zip` are byte-identical by SHA-256. The nested `omnichannel_affiliate_os_source.zip` is an older code snapshot; it is not evidence of a separately live app. Keep the live Project1 branch authoritative.
- The public landing-form re-subscription checkbox passed exact-SHA push/PR CI on `f97c30d8ff3486da361f93a2de31ac514b5bc671` (push [40645702983](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40645702983), PR [40645707260](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40645707260)). The current slice nets partial reversal ledger entries into learning commission and excludes fully reversed outcomes; verify exact-SHA CI before closure.


## 2026-10-28 attachment review follow-up — latest user file and verified learning regression
- Latest Library attachment reviewed: `Pasted text(10).txt`, 740 lines, 24,361 bytes, SHA-256 `5b92fe25513316f13557f1783e3d27e1448e117e317cd91a609aae03195bd297`. It restates the full OmniAffiliateOS product scope: FastAPI + Next.js, AI research/content/offer/landing/distribution/analytics/learning flows, adapter extensibility, S1–S8 orchestration, governance, and real test/CI evidence. It does not supply the separate newer live-application ZIP mentioned in earlier chats.
- Preserve the existing full-source register and deduplicate identical attachment copies by content hash. Historical ZIPs/bundles remain reference snapshots, never the current GitHub source of truth.
- The previous 2026-10-28 note saying the reversal-aware learning change awaited CI is superseded: commit `f2bc061ed41b799cb44132ba887b791851304df3` introduced the behavior; regression coverage was extended at `899265bb9cba7db973b7b91d0aa95c7e2052d34f`. Exact-SHA push [40648503523](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40648503523) and PR [40648508574](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40648508574) both passed, including PostgreSQL integration (7 passed in 1.69s). The durable implementation status is recorded in `docs/IMPLEMENTATION_STATUS.md`; external provider UAT and production release gates remain open.
- The next known acceptance gap is browser-level journey/accessibility verification. Existing Next.js typecheck, production build and container HTTP smoke tests are not browser UAT.
