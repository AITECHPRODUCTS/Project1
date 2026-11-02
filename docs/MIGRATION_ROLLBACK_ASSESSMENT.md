# Migration and rollback assessment

**Current status (30 October 2026):** the repository has a consolidated, sequential Alembic migration graph. The earlier statement that no Alembic graph exists is stale and superseded.

## Verified repository state

- Alembic environment: `migrations/env.py`, using the async SQLAlchemy engine and `Base.metadata`.
- Migration revisions: **34**, from `0001_initial_schema.py` through `0034_workspace_invitations.py`.
- Single current head: `0034_workspace_invitations`.
- Container startup runs `alembic upgrade head` before starting Uvicorn.
- Exact code/test SHA: `5e4044336df95561c4d3e953ace8929db75435c2`.
- Push CI: [41049558369](https://github.com/AITECHPRODUCTS/Project1/actions/runs/41049558369) — completed successfully.
- PR CI: [41049567637](https://github.com/AITECHPRODUCTS/Project1/actions/runs/41049567637) — completed successfully.

## Automated migration evidence

The configured CI executes the following checks against a fresh SQLite database and PostgreSQL service:

1. `alembic heads` confirms a single migration head.
2. `alembic upgrade head` applies the full migration chain.
3. `alembic current` confirms the resulting revision.
4. `alembic check` verifies metadata/schema drift.
5. `alembic downgrade -1` exercises a one-revision downgrade.
6. `alembic upgrade head` reapplies the latest revision.
7. A second `alembic check` verifies the resulting schema.

The PostgreSQL integration job also runs 9 tests covering selected concurrent conversion reversals, durable workflow lease claims, workspace budget reservations and comparison revision sequencing. On the exact SHA above, the Python suite passed 845 tests (9 skipped, 5 warnings), and PostgreSQL integration passed 9 tests.

## Remaining production migration and recovery gates

The hosted checks use fresh test databases; they do **not** establish that an existing production data set can be safely upgraded or rolled back. Before production:

1. Create a sanitized, representative copy of the current production-like schema/data and run the entire upgrade against it.
2. Validate row counts, foreign keys, tenant isolation, indexes, monetary precision and critical ledger/workflow invariants before and after migration.
3. Take a pre-migration backup and restore it in a separate environment. Record recovery point and recovery time.
4. Rehearse application rollback together with compatible schema rollback/forward-fix strategy; do not assume a database downgrade is always safe after writes.
5. Confirm the deployed image SHA, Alembic revision, readiness endpoint and worker/queue health during the staging deployment.
6. Keep payout, live spend, external publication and destructive data operations disabled while migration or rollback gates remain open.

`Base.metadata.create_all` may still be used by selected test fixtures or development helpers; it is not the production migration path. Production schema changes must use reviewed Alembic revisions.

**Conclusion:** migration graph and automated fresh-database CI checks are present and pass on the exact SHA above. Existing-data upgrade, production backup/restore, deployed-image rollback and disaster-recovery rehearsal are still pending. Do not mark production migration readiness as complete until those separate gates pass.
