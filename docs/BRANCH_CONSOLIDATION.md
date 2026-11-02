# Branch consolidation
- `main` is the minimal repository bootstrap baseline.
- `build/omni-affiliate-os-production` is the one active implementation branch.
- All current implementation changes are serialized on that branch; no feature branches are intended.
- The first target branch push created the CI workflow run. The initial run is expected to expose missing or failing checks; subsequent changes must rerun the affected checks.
- Do not merge to main until Python tests, source checks, frontend typecheck and production build pass on the exact PR head, with remaining external blockers recorded.
