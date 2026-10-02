"""Async engine, session factory and lifecycle helpers."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zuzenaa.config import settings
from zuzenaa.db.base import Base

engine = create_async_engine(settings.database_url, echo=settings.debug)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_models() -> None:
    """Create the schema if missing.

    Note: temporary convenience for the skeleton; replace with Alembic
    migrations once the models stabilise.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
