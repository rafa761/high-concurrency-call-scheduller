import json

import pytest
from httpx import ASGITransport, AsyncClient

from common.signing import sign_payload
import outcome_service.main as svc


@pytest.fixture
async def client(monkeypatch):
    # Stub the DB/S3/SQS work; this test only covers the HTTP + signature layer.
    monkeypatch.setattr(svc, "_run_processing", lambda event: "completed")
    transport = ASGITransport(app=svc.app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_rejects_bad_signature(client):
    body = json.dumps({"event_id": "e1", "provider_call_id": "pc1", "status": "completed"}).encode()
    resp = await client.post(
        "/provider/webhook", content=body, headers={"X-Signature": "wrong"}
    )
    assert resp.status_code == 401


async def test_accepts_valid_signature(client):
    payload = {"event_id": "e1", "provider_call_id": "pc1", "status": "completed", "outcome_type": "voicemail", "transcript": "t"}
    body = json.dumps(payload).encode()
    sig = sign_payload(svc.get_settings().webhook_signing_secret, body)
    resp = await client.post("/provider/webhook", content=body, headers={"X-Signature": sig})
    assert resp.status_code == 200
    assert resp.json() == {"result": "completed"}
