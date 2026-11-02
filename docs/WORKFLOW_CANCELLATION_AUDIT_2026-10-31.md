# OmniAffiliateOS — GitHub Actions cancellation and failure audit

**Audit date:** 31 October 2026 (Asia/Kolkata)  
**Repository:** https://github.com/AITECHPRODUCTS/Project1  
**Implementation branch:** `build/omni-affiliate-os-production`  
**Branch head at audit:** `b9e17023ae0f3fe453a09dc83986af184dd0c5ce`  
**Policy:** preserve the existing branch; no new branch created.

## Executive finding

The cancelled runs are not evidence that the corresponding product features are missing. The workflow file used a concurrency group scoped by workflow, event type and branch with `cancel-in-progress: true`. A new push run for the same branch/event therefore cancelled the previous in-flight push run; the same behavior applied independently to pull-request runs. Rapid iterative commits created many superseded runs.

At the time of the audit, GitHub reported 1,131 total workflow runs. The latest 100 returned by the Actions API contained:

| Conclusion/status | Count in latest 100 |
|---|---:|
| Cancelled | 85 |
| Failed | 8 |
| Successful | 6 |
| In progress | 1 |

These counts describe the latest 100 returned runs only, not all 1,131 historical runs. Most cancellations were associated with successive commits on the implementation branch. The cancellations should not be counted as 85 product-feature failures.

## Workflow policy correction

Changed the CI concurrency policy from `cancel-in-progress: true` to `false` on the existing implementation branch. This prevents a newer commit from terminating an already-running test matrix in the same concurrency group. GitHub concurrency still permits only one running and one pending run per group; a newer pending run can replace an older pending run. This is intentional queue protection, not a test pass.

The CI workflow still runs on pushes to `main` and `build/**`, pull requests targeting `main`, and manual dispatch. The implementation work remains on the pre-existing `build/omni-affiliate-os-production` branch.

## Failure investigation — known examples

The recent failed runs were genuine test/migration failures on older candidate commits, not evidence that every feature was absent:

- Run [41107942711](https://github.com/AITECHPRODUCTS/Project1/actions/runs/41107942711), PR event: browser UAT had two failures. The ClickBank provider-order reconciliation row did not render in the asserted UI state; the Flipkart product price assertion expected an exact display string that did not match the rendered output.
- Run [41106517080](https://github.com/AITECHPRODUCTS/Project1/actions/runs/41106517080), PR event: browser UAT exposed ambiguous Playwright locators in the ClickBank/Flipkart connection tests.
- Run [41096651926](https://github.com/AITECHPRODUCTS/Project1/actions/runs/41096651926), PR event: SQLite migration upgrade failed because migration 0037 attempted to add a check constraint with a dialect operation unsupported by SQLite outside batch mode.

Later commits updated the relevant tests and migration handling. These failures remain in Actions history and are not retroactively changed to green.

## Exact-head verification evidence

- PR run [41109402634](https://github.com/AITECHPRODUCTS/Project1/actions/runs/41109402634) completed successfully on candidate SHA `41d86dd9e3e23f50f093de643e7bb9e1a3855023`. All configured required jobs passed, including Python, PostgreSQL integration, frontend build/typecheck/Docker smoke, AI/RAG, security audit, secret scan, repository guard and browser UAT. The push run for that same SHA was cancelled, so it is not counted as a push pass.
- The branch subsequently advanced to `b9e17023ae0f3fe453a09dc83986af184dd0c5ce`. Its newer push/PR runs must complete on that exact SHA before this branch head is called verified.
- Historical failed/cancelled runs are retained for audit. Re-run only the latest relevant candidate or a specific failed job when its code is still current; do not rerun obsolete commits as a substitute for validating the current head.

## Product status — do not overstate

The application has real foundations for the commission-earner dashboard (`/`), merchant/product-publisher dashboard (`/merchant`) and platform Super Admin (`/admin`), plus `FULL_AUTONOMOUS`, `SEMI_AUTONOMOUS` and `MANUAL_OVERRIDE` workflow modes. They are not complete production-grade end-to-end applications.

The current skill parity register contains 53 rows, all partial and zero end-to-end complete. Provider catalogues/adapters are not equivalent to connected, authorized accounts. Real provider authorization, account-specific sandbox/contract acceptance, paid-ad write operations, live publishing, full CRM, commission statement reconciliation, merchant lifecycle, Super Admin operations, staging, backup/restore, monitoring and release acceptance remain open. External actions remain approval-gated or disabled.

## Next checkpoint

1. Allow the current exact-head CI runs to complete under the updated no-cancel-in-flight policy.
2. Inspect every failed job log on the current candidate SHA; fix only reproducible/current defects on this same branch.
3. Verify the complete migration graph and PostgreSQL concurrency tests, browser journeys, Python suite, frontend production build and security/SBOM jobs.
4. Continue the production backlog from `docs/REQUIREMENTS_TRACEABILITY_MASTER.md`, `docs/IMPLEMENTATION_STATUS.md` and `docs/skill-parity-matrix.csv`.
5. Keep PR #1 draft and do not merge/deploy until provider, operational and release gates are evidenced.
