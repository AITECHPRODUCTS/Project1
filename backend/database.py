from __future__ import annotations
from pathlib import Path
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from backend.config import get_settings

class Base(DeclarativeBase): pass
settings = get_settings()
if settings.database_url.startswith("sqlite"): Path("./storage").mkdir(parents=True, exist_ok=True)
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session: yield session

async def init_db() -> None:
    from backend import models  # noqa: F401
    async with engine.begin() as connection: await connection.run_sync(Base.metadata.create_all)

async def close_db() -> None: await engine.dispose()
