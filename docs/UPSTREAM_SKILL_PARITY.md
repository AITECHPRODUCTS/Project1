# Pinned upstream affiliate-skill source and runtime parity

**Audit date:** 25 October 2026  
**Product repository:** AITECHPRODUCTS/Project1  
**Upstream source:** https://github.com/Affitor/affiliate-skills/tree/f4cb063a0ee83b1b9e5167e396ab46cc9123dadc  
**Upstream source commit:** f4cb063a0ee83b1b9e5167e396ab46cc9123dadc  
**User-provided source archive SHA-256:** dc463b31d80d6917142d99d9bc7f7b19385e8e0c74ff5c0cc57f4410ed73e1a6

## Pinned source inventory

The supplied archive was checked for ZIP integrity and contains 289 entries. Both its registry.json and filesystem contain **53 skill definitions** under skills/**/SKILL.md. There are 55 SKILL.md paths overall because the root SKILL.md guidance and template/SKILL.md are not additional app capabilities.

The upstream README says “52 Skills”; this mismatch is preserved and surfaced by the parity guard. The pinned registry/filesystem count of 53 is authoritative; a README badge/text count is not used to determine the runtime inventory.

The current Project1 branch vendors 72 source files under knowledge/affiliate-skills/upstream/: 53 skill definitions, upstream registry, source guidance/template, README, version, MIT license, evaluation cases, and 12 shared reference files. SOURCE_MANIFEST.json records the pinned commit, source archive hash, exact upstream blob SHA and size for each vendored file. The verifier computes Git blob identities over the committed bytes, so unintended edits to pinned source material fail CI.

## Runtime parity is separate

The application’s docs/skill-parity-matrix.csv remains the source of runtime implementation status. At the pre-import verified checkpoint c7ee98e1f6f1eec8e8c6157d16843f06b78648a6, it recorded **47 partial, 6 not implemented, 0 fully implemented end-to-end**. Vendoring source definitions does not promote a skill to implemented and does not imply that a provider is connected.

Each skill still needs its actual typed request/response, service/API, UI or headless trigger, persistence, policy/authorization boundary, failure handling, and unit/contract/integration/security/UAT evidence as applicable. External provider credentials/scopes and provider-specific contract tests remain separate gates.

## CI gate

scripts/verify_skill_registry.py checks:
- the pinned upstream source commit and archive SHA;
- all 72 source-file Git blob hashes and sizes;
- exactly 53 unique upstream registry slugs and SKILL.md paths;
- one-to-one slug coverage against the runtime parity CSV;
- status count consistency with docs/IMPLEMENTATION_STATUS.md;
- the 52-vs-53 README discrepancy as an explicit note, not a false failure.

The workflow’s repo-guard job runs this verifier alongside the existing repository source/syntax verifier. Exact-SHA Actions results for the code adding this gate are recorded separately after the workflow completes.


## 2026-10-29 — executable commission calculator increment

`research/commission-calculator` now has an allowlisted deterministic runtime handler. It estimates earnings only from explicitly provided traffic and conversion assumptions plus payout terms; same-currency comparisons use bounded Decimal calculations. Recurring estimates state the supplied paid duration and assume no churn/refunds. No provider data, guaranteed earnings, or payouts are claimed. Exact-SHA acceptance remains pending until the current push/PR jobs complete.
