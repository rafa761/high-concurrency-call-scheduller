import asyncio
import json
import os
import random
import time
import uuid

import httpx
from fastapi import BackgroundTasks, FastAPI, Response
from pydantic import BaseModel

from common.signing import sign_payload

app = FastAPI(title="Mock Telephony Provider")

_SECRET = os.environ.get("MOCK_PROVIDER_SIGNING_SECRET", "dev-signing-secret")
_COMPLETED_OUTCOMES = ["promise_to_pay", "callback_requested", "voicemail", "not_interested"]

_chaos = {
    "failure_rate": float(os.environ.get("MOCK_PROVIDER_FAILURE_RATE", "0.0")),
    "latency_ms": int(os.environ.get("MOCK_PROVIDER_LATENCY_MS", "0")),
    "call_failure_rate": float(os.environ.get("MOCK_PROVIDER_CALL_FAILURE_RATE", "0.0")),
    "duplicate_rate": float(os.environ.get("MOCK_PROVIDER_DUPLICATE_RATE", "0.0")),
    "drop_callback_rate": float(os.environ.get("MOCK_PROVIDER_DROP_CALLBACK_RATE", "0.0")),
    # Simulated call duration: the webhook fires after a random delay in this
    # range, so a task realistically dwells in "calling" for a few seconds.
    "call_duration_min_ms": int(os.environ.get("MOCK_PROVIDER_CALL_DURATION_MIN_MS", "3000")),
    "call_duration_max_ms": int(os.environ.get("MOCK_PROVIDER_CALL_DURATION_MAX_MS", "8000")),
}


class CallRequest(BaseModel):
    task_id: str
    phone: str
    callback_url: str | None = None


class ChaosConfig(BaseModel):
    failure_rate: float | None = None
    latency_ms: int | None = None
    call_failure_rate: float | None = None
    duplicate_rate: float | None = None
    drop_callback_rate: float | None = None
    call_duration_min_ms: int | None = None
    call_duration_max_ms: int | None = None


@app.get("/config")
def get_config() -> dict:
    return _chaos


@app.post("/config")
def set_config(cfg: ChaosConfig) -> dict:
    for key, value in cfg.model_dump(exclude_none=True).items():
        _chaos[key] = value
    return _chaos


def _call_duration_seconds() -> float:
    lo = _chaos["call_duration_min_ms"]
    hi = _chaos["call_duration_max_ms"]
    return random.uniform(min(lo, hi), max(lo, hi)) / 1000


async def _fire_callback(provider_call_id: str, callback_url: str) -> None:
    # asyncio.sleep (not time.sleep) so thousands of calls can be "in progress"
    # concurrently without blocking the server's thread pool.
    await asyncio.sleep(_call_duration_seconds())

    if random.random() < _chaos["call_failure_rate"]:
        payload = {"provider_call_id": provider_call_id, "status": "failed",
                   "outcome_type": "no_answer", "transcript": None}
    else:
        payload = {"provider_call_id": provider_call_id, "status": "completed",
                   "outcome_type": random.choice(_COMPLETED_OUTCOMES),
                   "transcript": f"[mock transcript for {provider_call_id}]"}
    payload["event_id"] = str(uuid.uuid4())

    body = json.dumps(payload).encode()
    headers = {"X-Signature": sign_payload(_SECRET, body), "content-type": "application/json"}
    deliveries = 2 if random.random() < _chaos["duplicate_rate"] else 1
    async with httpx.AsyncClient(timeout=10.0) as client:
        for _ in range(deliveries):
            try:
                await client.post(callback_url, content=body, headers=headers)
            except httpx.HTTPError:
                pass


@app.post("/calls")
def place_call(req: CallRequest, response: Response, background: BackgroundTasks) -> dict:
    if _chaos["latency_ms"]:
        time.sleep(_chaos["latency_ms"] / 1000)
    if random.random() < _chaos["failure_rate"]:
        response.status_code = 503
        return {"error": "provider unavailable"}

    provider_call_id = str(uuid.uuid4())
    # drop_callback_rate simulates a lost webhook: the call is "placed" but no
    # outcome is ever reported, leaving the task stuck for the reaper to reclaim.
    if req.callback_url and random.random() >= _chaos["drop_callback_rate"]:
        background.add_task(_fire_callback, provider_call_id, req.callback_url)
    return {"provider_call_id": provider_call_id, "status": "accepted"}
