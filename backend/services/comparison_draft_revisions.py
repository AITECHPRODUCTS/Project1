from __future__ import annotations

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ComparisonDraftRevisionSequence, ContentAsset, new_id
from backend.tenancy import workspace_scope


MAX_REVISION_NUMBER = 100_000


async def reserve_comparison_revision_number(
    db: AsyncSession,
    *,
    workspace_id: str,
    root_asset_id: str,
) -> int:
    """Atomically reserve the next unique revision number for one workspace root.

    The sequence row update is committed by the caller together with its audit event
    before any LLM/network work. A failed generation can leave a gap, but concurrent
    requests cannot reuse a number or mutate the original draft body.
    """
    workspace_id = str(workspace_id or "").strip()
    root_asset_id = str(root_asset_id or "").strip()
    if not workspace_id or not root_asset_id:
        raise ValueError("A workspace and revision root are required")

    with workspace_scope(workspace_id):
        root = await db.scalar(
            select(ContentAsset.id).where(
                ContentAsset.id == root_asset_id,
                ContentAsset.workspace_id == workspace_id,
                ContentAsset.asset_type == "comparison_post",
            )
        )
        if root is None:
            raise ValueError("Revision root was not found in this workspace")

        history = await db.scalars(
            select(ContentAsset.metadata_json).where(
                ContentAsset.workspace_id == workspace_id,
                ContentAsset.asset_type == "comparison_post",
                or_(
                    ContentAsset.id == root_asset_id,
                    ContentAsset.metadata_json["revision_root_asset_id"].as_string() == root_asset_id,
                ),
            )
        )
        max_existing_revision = 1
        for metadata in history:
            if not isinstance(metadata, dict):
                continue
            try:
                number = int(metadata.get("revision_number") or 1)
            except (TypeError, ValueError):
                continue
            if 1 <= number <= MAX_REVISION_NUMBER:
                max_existing_revision = max(max_existing_revision, number)
        if max_existing_revision >= MAX_REVISION_NUMBER:
            raise ValueError("This comparison draft has reached the supported revision limit")
        initial_next = max_existing_revision + 1

        dialect = db.get_bind().dialect.name
        values = {
            "id": new_id(),
            "workspace_id": workspace_id,
            "root_asset_id": root_asset_id,
            "next_revision_number": initial_next,
        }
        if dialect == "postgresql":
            statement = postgres_insert(ComparisonDraftRevisionSequence).values(**values)
        elif dialect == "sqlite":
            statement = sqlite_insert(ComparisonDraftRevisionSequence).values(**values)
        else:
            raise RuntimeError("Comparison revision allocation supports PostgreSQL and SQLite only")
        statement = statement.on_conflict_do_nothing(
            index_elements=["workspace_id", "root_asset_id"]
        )
        await db.execute(statement)

        # Raise the sequence to the highest persisted historical revision when it
        # is first initialized, but never move an already-reserved counter backward.
        current_or_seeded = case(
            (
                ComparisonDraftRevisionSequence.next_revision_number < initial_next,
                initial_next,
            ),
            else_=ComparisonDraftRevisionSequence.next_revision_number,
        )
        result = await db.execute(
            update(ComparisonDraftRevisionSequence)
            .where(
                ComparisonDraftRevisionSequence.workspace_id == workspace_id,
                ComparisonDraftRevisionSequence.root_asset_id == root_asset_id,
                ComparisonDraftRevisionSequence.next_revision_number <= MAX_REVISION_NUMBER,
            )
            .values(
                next_revision_number=current_or_seeded + 1,
                updated_at=func.now(),
            )
            .returning(ComparisonDraftRevisionSequence.next_revision_number)
        )
        stored_next = result.scalar_one_or_none()
        if stored_next is None:
            raise ValueError("This comparison draft has reached the supported revision limit")
        allocated = int(stored_next) - 1
        if not 2 <= allocated <= MAX_REVISION_NUMBER:
            raise ValueError("The comparison draft revision sequence is outside supported bounds")
        return allocated
