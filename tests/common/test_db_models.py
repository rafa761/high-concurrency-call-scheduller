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


async def test_contact_persists_and_enforces_unique_phone(session):
    from common.models import Contact

    campaign = Campaign(name="c", max_concurrency=1)
    session.add(campaign)
    await session.commit()

    c1 = Contact(
        campaign_id=campaign.id,
        phone="+15551230001",
        timezone="America/New_York",
        meta={"first_name": "Ann"},
    )
    session.add(c1)
    await session.commit()

    fetched = await session.get(Contact, c1.id)
    assert fetched.phone == "+15551230001"
    assert fetched.meta == {"first_name": "Ann"}
    assert fetched.timezone == "America/New_York"


async def test_call_task_persists_with_defaults(session):
    from common.models import CallTask, Contact

    campaign = Campaign(name="c", max_concurrency=1)
    session.add(campaign)
    await session.commit()
    contact = Contact(campaign_id=campaign.id, phone="+15551239999", timezone="America/New_York")
    session.add(contact)
    await session.commit()

    task = CallTask(campaign_id=campaign.id, contact_id=contact.id)
    session.add(task)
    await session.commit()

    fetched = await session.get(CallTask, task.id)
    assert fetched.status == "pending"
    assert fetched.attempts == 0
    assert fetched.next_eligible_at is None
    assert fetched.last_attempt_at is None
    assert fetched.created_at is not None
