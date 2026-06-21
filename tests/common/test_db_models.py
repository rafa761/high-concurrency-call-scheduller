import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select

from common.models import Campaign


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def test_campaign_persists_with_defaults(session):
    c = Campaign(name="demo", max_concurrency=10)
    session.add(c)
    await session.commit()

    fetched = await session.get(Campaign, c.id)
    assert fetched is not None
    assert fetched.name == "demo"
    assert fetched.status == "created"
    assert fetched.max_concurrency == 10
    assert fetched.s3_key is None
    assert fetched.created_at is not None


async def test_campaign_query_by_name(session):
    session.add(Campaign(name="alpha", max_concurrency=5))
    session.add(Campaign(name="beta", max_concurrency=5))
    await session.commit()

    result = await session.execute(select(Campaign).where(Campaign.name == "alpha"))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].name == "alpha"
