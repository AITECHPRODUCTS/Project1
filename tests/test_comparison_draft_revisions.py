from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models import ComparisonDraftRevisionSequence, ContentAsset, Workspace
from backend.services.comparison_draft_revisions import reserve_comparison_revision_number
from backend.tenancy import workspace_scope


@pytest.mark.asyncio
async def test_revision_sequence_is_monotonic_and_seeds_from_existing_history():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    workspace_id = "revision-sequence-workspace"
    root_id = "revision-sequence-root"

    async def prepare():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            session.add(Workspace(id=workspace_id, name="Revision sequence", slug="revision-sequence"))
            await session.flush()
            with workspace_scope(workspace_id):
                session.add(ContentAsset(
                    id=root_id,
                    workspace_id=workspace_id,
                    asset_type="comparison_post",
                    title="Original",
                    body="<article>Original</article>",
                    status="draft",
                    source_urls=[],
                    metadata_json={"revision_number": 1, "revision_root_asset_id": root_id},
                ))
                session.add(ContentAsset(
                    id="revision-sequence-old-v4",
                    workspace_id=workspace_id,
                    asset_type="comparison_post",
                    title="Existing revision four",
                    body="<article>Existing</article>",
                    status="draft",
                    source_urls=[],
                    metadata_json={"revision_number": 4, "revision_of_asset_id": root_id, "revision_root_asset_id": root_id},
                ))
                await session.commit()

    async def allocate():
        async with sessions() as session:
            with workspace_scope(workspace_id):
                value = await reserve_comparison_revision_number(
                    session,
                    workspace_id=workspace_id,
                    root_asset_id=root_id,
                )
                await session.commit()
                return value

    try:
        await prepare()
        reserved = [await allocate(), await allocate(), await allocate()]
        assert reserved == [5, 6, 7]
        async with sessions() as session:
            with workspace_scope(workspace_id):
                counter = await session.scalar(select(ComparisonDraftRevisionSequence).where(
                    ComparisonDraftRevisionSequence.workspace_id == workspace_id,
                    ComparisonDraftRevisionSequence.root_asset_id == root_id,
                ))
                original = await session.get(ContentAsset, root_id)
            assert counter is not None and counter.next_revision_number == 8
            assert original is not None and original.body == "<article>Original</article>"
            assert original.metadata_json["revision_number"] == 1
    finally:
        await engine.dispose()
