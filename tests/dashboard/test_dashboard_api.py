import json

import pytest
from httpx import ASGITransport, AsyncClient

import dashboard.main as dash

_FAKE = {
    "queues": {"dispatch": {"visible": 0, "in_flight": 0},
               "outcome_delivery": {"visible": 0, "in_flight": 0},
               "crm_dlq": {"visible": 0, "in_flight": 0}},
    "concurrency": {"active": 0, "capacity": 0},
    "task_funnel": {"pending": 0, "dispatching": 0, "calling": 0, "completed": 0, "exhausted": 0},
    "crm": {"delivered": 0, "failed": 0},
    "totals": {"campaigns": 0, "contacts": 0, "call_tasks": 0},
}


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(dash, "_snapshot", lambda: _FAKE)
    transport = ASGITransport(app=dash.app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_stats_returns_json(client):
    resp = await client.get("/stats")
    assert resp.status_code == 200
    assert resp.json() == _FAKE


async def test_redrive_returns_moved_count(monkeypatch):
    monkeypatch.setattr(dash, "_snapshot", lambda: _FAKE)
    monkeypatch.setattr(dash, "_redrive", lambda: 2)
    transport = ASGITransport(app=dash.app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/redrive")
    assert resp.status_code == 200
    assert resp.json() == {"moved": 2}


async def test_index_serves_html(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_stream_emits_an_sse_event(monkeypatch):
    # Call the streaming route directly and pull one event off its body
    # iterator — consuming the *infinite* stream over the ASGI transport and
    # tearing it down is harness-flaky, so we test the response object itself.
    monkeypatch.setattr(dash, "_snapshot", lambda: _FAKE)
    resp = await dash.stats_stream()
    assert resp.media_type == "text/event-stream"

    body = resp.body_iterator
    first = await body.__anext__()
    assert first.startswith("data:")
    assert json.loads(first[len("data:"):].strip()) == _FAKE
    await body.aclose()
