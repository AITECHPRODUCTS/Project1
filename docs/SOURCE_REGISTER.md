# Source register

## Sources read/used for this build
- User-provided OmniAffiliateOS v4 engineering contract and follow-on addendum: controls repository target, one-branch strategy, capability status semantics, evidence-first implementation, release gates and truthful reporting.
- User-provided Project1 branch audit dated 2026-10-24: historical findings on branch conflicts, migration collisions, provider coverage, missing CI evidence and skill parity. It is reference evidence, not the target repository.
- User-provided affiliate automation requirement/build ZIPs: product scope, workflows, requirements, source pack and prior implementation files. Selected architecture and service concepts were independently reconstructed into this branch.
- Source reference doctrine currently in `knowledge/affiliate-skills/shared/references/`; original upstream license is retained at `knowledge/affiliate-skills/LICENSE`.
- Repository-local distilled build contract: `docs/requirements/v4/`.
- Test/CI evidence: actual GitHub Actions runs for exact commit SHAs. See the run links in the GitHub Actions tab.

## Important limitations
This repository does **not** yet contain a byte-for-byte mirror of every source archive, every original source-of-truth file, or all 53 upstream `SKILL.md` files. The requirement pack in `docs/requirements/v4/` is a distilled engineering contract; it must not be misrepresented as the complete raw attachment corpus. Runtime parity is recorded separately in `docs/skill-parity-matrix.csv`. No provider is production-verified just because a catalogue entry or adapter scaffold is present.

## 2026-10-25 continuation note
- The user advised that a ZIP of an already-live application will be supplied later on 2026-10-25. It is not yet available in this repository, so no claim is made that its code has been reviewed. A reminder is scheduled for 18:30 Asia/Kolkata. Continue from the available requirements and code until the file is provided; then audit and port selected code safely.
