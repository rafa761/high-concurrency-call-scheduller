from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from common.config import Settings, get_settings


def psycopg_dsn(settings: Settings | None = None) -> str:
    # Raw libpq DSN for psycopg.connect(): drop SQLAlchemy's "+psycopg" driver tag.
    settings = settings or get_settings()
    return settings.database_url.replace("+psycopg", "")


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, echo=False)


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session
