from __future__ import annotations

from pathlib import Path
from collections.abc import AsyncIterator
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, with_loader_criteria
from backend.config import get_settings
from backend.tenancy import TenantScopedMixin, get_workspace_id


class Base(DeclarativeBase):
    pass


settings = get_settings()
if settings.database_url.startswith("sqlite"):
    Path("./storage").mkdir(parents=True, exist_ok=True)
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(Session, "do_orm_execute")
def _apply_workspace_query_scope(execute_state) -> None:
    workspace_id = get_workspace_id()
    if workspace_id is None:
        # Explicitly unscoped access is reserved for public lookup flows and internal workers.
        return
    if execute_state.is_select:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                TenantScopedMixin,
                lambda entity: entity.workspace_id == workspace_id,
                include_aliases=True,
            )
        )


@event.listens_for(Session, "before_flush")
def _enforce_workspace_on_flush(session: Session, flush_context, instances) -> None:
    workspace_id = get_workspace_id()
    production = get_settings().app_env == "production"
    for entity in session.new:
        if not isinstance(entity, TenantScopedMixin):
            continue
        current = getattr(entity, "workspace_id", None)
        if workspace_id is None:
            if production:
                raise RuntimeError("Tenant-scoped writes require an authenticated workspace context")
            continue
        if current is None:
            entity.workspace_id = workspace_id
        elif current != workspace_id:
            raise RuntimeError("Cross-workspace insert blocked")
    for entity in session.dirty:
        if not isinstance(entity, TenantScopedMixin):
            continue
        current = getattr(entity, "workspace_id", None)
        if workspace_id is not None and current != workspace_id:
            raise RuntimeError("Cross-workspace update blocked")
        if session.is_modified(entity, include_collections=False):
            state = __import__("sqlalchemy").inspect(entity)
            if state.attrs.workspace_id.history.has_changes():
                raise RuntimeError("workspace_id is immutable after row creation")


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create schema only in development/test. Production uses Alembic migrations."""
    from backend import models  # noqa: F401
    if settings.app_env == "production":
        return
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()
