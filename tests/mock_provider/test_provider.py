import pytest
from httpx import ASGITransport, AsyncClient

from mock_provider.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # reset chaos to a known state for each test
        await c.post("/config", json={"failure_rate": 0.0, "latency_ms": 0})
        yield c


async def test_places_call_when_healthy(client):
    resp = await client.post(
        "/calls", json={"task_id": "t1", "phone": "+15551112222", "callback_url": "http://cb"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["provider_call_id"]


async def test_fails_when_failure_rate_is_one(client):
    await client.post("/config", json={"failure_rate": 1.0})
    resp = await client.post(
        "/calls", json={"task_id": "t1", "phone": "+15551112222", "callback_url": "http://cb"}
    )
    assert resp.status_code == 503
