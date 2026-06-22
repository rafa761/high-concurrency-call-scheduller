import pytest
from httpx import ASGITransport, AsyncClient

from mock_crm.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/config", json={"failure_rate": 0.0, "latency_ms": 0})
        yield c


async def test_records_outcome(client):
    resp = await client.post(
        "/crm/outcomes", json={"outcome_id": "o1"}, headers={"Idempotency-Key": "o1"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "recorded"


async def test_duplicate_key_is_deduped(client):
    await client.post("/crm/outcomes", json={"outcome_id": "o2"}, headers={"Idempotency-Key": "o2"})
    resp = await client.post(
        "/crm/outcomes", json={"outcome_id": "o2"}, headers={"Idempotency-Key": "o2"}
    )
    assert resp.json()["status"] == "duplicate"


async def test_failure_rate_one_returns_503(client):
    await client.post("/config", json={"failure_rate": 1.0})
    resp = await client.post(
        "/crm/outcomes", json={"outcome_id": "o3"}, headers={"Idempotency-Key": "o3"}
    )
    assert resp.status_code == 503
