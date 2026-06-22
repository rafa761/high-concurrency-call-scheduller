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
    # no callback_url -> no background callback fires (keeps the test fast)
    resp = await client.post("/calls", json={"task_id": "t1", "phone": "+15551112222"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["provider_call_id"]


async def test_fails_when_failure_rate_is_one(client):
    await client.post("/config", json={"failure_rate": 1.0})
    resp = await client.post("/calls", json={"task_id": "t1", "phone": "+15551112222"})
    assert resp.status_code == 503


async def test_config_accepts_drop_callback_rate(client):
    resp = await client.post("/config", json={"drop_callback_rate": 1.0})
    assert resp.json()["drop_callback_rate"] == 1.0


async def test_config_accepts_call_duration_range(client):
    resp = await client.post(
        "/config", json={"call_duration_min_ms": 4000, "call_duration_max_ms": 6000}
    )
    body = resp.json()
    assert body["call_duration_min_ms"] == 4000
    assert body["call_duration_max_ms"] == 6000
