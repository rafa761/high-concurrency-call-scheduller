import os
import random
import time

from fastapi import FastAPI, Header, Response
from pydantic import BaseModel

app = FastAPI(title="Mock CRM")

_chaos = {
    "failure_rate": float(os.environ.get("MOCK_CRM_FAILURE_RATE", "0.0")),
    "latency_ms": int(os.environ.get("MOCK_CRM_LATENCY_MS", "0")),
}
_received: dict[str, dict] = {}


class ChaosConfig(BaseModel):
    failure_rate: float | None = None
    latency_ms: int | None = None


@app.get("/config")
def get_config() -> dict:
    return _chaos


@app.post("/config")
def set_config(cfg: ChaosConfig) -> dict:
    for key, value in cfg.model_dump(exclude_none=True).items():
        _chaos[key] = value
    return _chaos


@app.get("/crm/outcomes")
def list_outcomes() -> dict:
    return {"count": len(_received)}


@app.post("/crm/outcomes")
def receive_outcome(
    payload: dict, response: Response, idempotency_key: str = Header(...)
) -> dict:
    if _chaos["latency_ms"]:
        time.sleep(_chaos["latency_ms"] / 1000)
    if random.random() < _chaos["failure_rate"]:
        response.status_code = 503
        return {"error": "crm unavailable"}
    if idempotency_key in _received:
        return {"status": "duplicate"}
    _received[idempotency_key] = payload
    return {"status": "recorded"}
