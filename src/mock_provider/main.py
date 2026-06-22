import os
import random
import time
import uuid

from fastapi import FastAPI, Response
from pydantic import BaseModel

app = FastAPI(title="Mock Telephony Provider")

# Mutable chaos state, seeded from env, adjustable at runtime via POST /config.
_chaos = {
    "failure_rate": float(os.environ.get("MOCK_PROVIDER_FAILURE_RATE", "0.0")),
    "latency_ms": int(os.environ.get("MOCK_PROVIDER_LATENCY_MS", "0")),
}


class CallRequest(BaseModel):
    task_id: str
    phone: str
    callback_url: str | None = None


class ChaosConfig(BaseModel):
    failure_rate: float | None = None
    latency_ms: int | None = None


@app.get("/config")
def get_config() -> dict:
    return _chaos


@app.post("/config")
def set_config(cfg: ChaosConfig) -> dict:
    if cfg.failure_rate is not None:
        _chaos["failure_rate"] = cfg.failure_rate
    if cfg.latency_ms is not None:
        _chaos["latency_ms"] = cfg.latency_ms
    return _chaos


@app.post("/calls")
def place_call(req: CallRequest, response: Response) -> dict:
    if _chaos["latency_ms"]:
        time.sleep(_chaos["latency_ms"] / 1000)
    if random.random() < _chaos["failure_rate"]:
        response.status_code = 503
        return {"error": "provider unavailable"}
    return {"provider_call_id": str(uuid.uuid4()), "status": "accepted"}
