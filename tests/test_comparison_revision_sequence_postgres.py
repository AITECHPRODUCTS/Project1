from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models import ComparisonDraftRevisionSequence, ContentAsset, Workspace
from backend.services.comparison_draft_revisions import reserve_content_revision_number
from backend.tenancy import workspace_scope


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("POSTGRES_WEBHOOK_INTEGRATION") != "1",
    reason="requires the dedicated PostgreSQL integration job",
)
@pytest.mark.parametrize("asset_type", ["comparison_post", "listicle_post"])
async def test_concurrent_postgres_revision_reservations_are_unique_and_monotonic(asset_type: str):
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("postgresql+asyncpg://"):
        pytest.fail("the revision concurrency acceptance test requires PostgreSQL")
    engine = create_async_engine(database_url, pool_size=12, max_overflow=4)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    workspace_id = str(uuid.uuid4())
    root_id = str(uuid.uuid4())

    async def prepare():
        async with sessions() as session:
            session.add(Workspace(id=workspace_id, name="Concurrent revisions", slug=f"rev-{asset_type[:4]}-{workspace_id[:12]}"))
            await session.flush()
            with workspace_scope(workspace_id):
                session.add(ContentAsset(
                    id=root_id,
                    workspace_id=workspace_id,
                    asset_type=asset_type,
                    title="Original",
                    body="<article>Original</article>",
                    status="draft",
                    source_urls=[],
                    metadata_json={"revision_number": 1, "revision_root_asset_id": root_id},
                ))
                await session.commit()

    async def allocate():
        async with sessions() as session:
            with workspace_scope(workspace_id):
                number = await reserve_content_revision_number(
                    session,
                    workspace_id=workspace_id,
                    root_asset_id=root_id,
                    asset_type=asset_type,
                )
                await session.commit()
                return number

    try:
        await prepare()
        semaphore = asyncio.Semaphore(12)

        async def guarded_allocate():
            async with semaphore:
                return await allocate()

        allocated = await asyncio.gather(*(guarded_allocate() for _ in range(24)))
        assert sorted(allocated) == list(range(2, 26))
        assert len(set(allocated)) == 24
        async with sessions() as session:
            counter = await session.scalar(select(ComparisonDraftRevisionSequence).where(
                ComparisonDraftRevisionSequence.workspace_id == workspace_id,
                ComparisonDraftRevisionSequence.root_asset_id == root_id,
            ))
        assert counter is not None and counter.next_revision_number == 26
    finally:
        async with sessions() as session:
            await session.execute(delete(ComparisonDraftRevisionSequence).where(
                ComparisonDraftRevisionSequence.workspace_id == workspace_id,
                ComparisonDraftRevisionSequence.root_asset_id == root_id,
            ))
            await session.execute(delete(ContentAsset).where(
                ContentAsset.id == root_id,
                ContentAsset.workspace_id == workspace_id,
            ))
            await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
            await session.commit()
        await engine.dispose()
