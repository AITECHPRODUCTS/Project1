from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


_workspace_id: ContextVar[str | None] = ContextVar("affiliate_os_workspace_id", default=None)


def get_workspace_id() -> str | None:
    return _workspace_id.get()


def set_workspace_id(workspace_id: str | None) -> Token:
    return _workspace_id.set(workspace_id)


def reset_workspace_id(token: Token) -> None:
    _workspace_id.reset(token)


@contextmanager
def workspace_scope(workspace_id: str | None) -> Iterator[None]:
    token = set_workspace_id(workspace_id)
    try:
        yield
    finally:
        reset_workspace_id(token)


class TenantScopedMixin:
    """Rows using this mixin are filtered by the active workspace on ORM queries."""

    @declared_attr
    def workspace_id(cls) -> Mapped[str | None]:
        return mapped_column(
            String(36),
            ForeignKey("workspaces.id", ondelete="RESTRICT"),
            index=True,
            nullable=True,
        )
