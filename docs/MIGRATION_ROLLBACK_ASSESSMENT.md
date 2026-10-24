# Migration and rollback assessment
Current code uses SQLAlchemy metadata creation at startup for the development baseline. It does not yet include a consolidated Alembic migration graph; production migrations are therefore blocked. Do not treat create_all as a production migration strategy.

Before production:
1. Add Alembic and a single linear initial migration from the current SQLAlchemy models.
2. Test an empty PostgreSQL database and an existing database upgrade; confirm `alembic heads` has a single supported head and metadata drift is absent.
3. Take backup and restore it in a separate environment; exercise the rollback plan for schema and deployable images.
4. Keep payout, spend, external publication and deletion side effects disabled while migration or rollback checks are outstanding.
