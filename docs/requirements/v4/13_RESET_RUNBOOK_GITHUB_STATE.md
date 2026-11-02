# GitHub reset and release runbook

- Verified connected GitHub identity: `AITECHPRODUCTS`.
- User-directed target: public `AITECHPRODUCTS/Project1`; do not redirect to the old `learnplayai73-rgb/Project1`.
- Keep `main` plus one active implementation branch: `build/omni-affiliate-os-production`. No additional feature branches are required.
- Keep source, fix and test commits on that branch and maintain one PR to main after the branch is coherent. Do not merge until all gates pass on the exact candidate SHA.
- Public repository check: no secrets, provider tokens, user data, source media or model artifacts. Any provider secret must be set through authorized secret storage.
- Actual action URLs and commit SHAs are recorded by GitHub; do not copy stale run IDs from older attachments.
- Latest verified passing candidate prior to Alembic gate: `a1adc037d4b00e42d116e4e83b4fa1d927b7706c` (Python verifier/compile/tests and frontend checks passed). The Alembic-enhanced candidate is subject to the new run.
- If provider credentials, KYC or external approval are missing, finish all code/tests not dependent on them and mark exact capability as blocked; do not call the system production-live.
