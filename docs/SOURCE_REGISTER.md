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
