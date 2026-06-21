import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from campaign_api.main import app
from common import aws
from common.db import get_session


@pytest.fixture
async def client(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _session_override():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _session_override
    # Presigning hits no network, but stub it so tests need no AWS at all.
    monkeypatch.setattr(
        aws,
        "presign_put_url",
        lambda bucket, key, **kw: f"http://localhost:4566/{bucket}/{key}?signed=1",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()


async def test_create_campaign_returns_id_key_and_url(client):
    resp = await client.post("/campaigns", json={"name": "demo", "max_concurrency": 10})
    assert resp.status_code == 201
    body = resp.json()
    assert body["s3_key"] == f"campaigns/{body['campaign_id']}/contacts.csv"
    assert body["upload_url"].startswith("http://localhost:4566/campaign-uploads/")
    assert "signed=1" in body["upload_url"]


async def test_create_campaign_rejects_nonpositive_concurrency(client):
    resp = await client.post("/campaigns", json={"name": "bad", "max_concurrency": 0})
    assert resp.status_code == 422


async def test_get_campaign_roundtrip(client):
    created = (
        await client.post("/campaigns", json={"name": "demo", "max_concurrency": 7})
    ).json()
    resp = await client.get(f"/campaigns/{created['campaign_id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["campaign_id"]
    assert body["name"] == "demo"
    assert body["status"] == "created"
    assert body["max_concurrency"] == 7


async def test_get_missing_campaign_returns_404(client):
    resp = await client.get("/campaigns/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
