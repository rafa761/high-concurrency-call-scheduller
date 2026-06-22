import asyncio
import json
from pathlib import Path

import psycopg
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from common.aws import sqs_client
from common.config import get_settings
from common.db import psycopg_dsn
from dashboard.stats import collect_stats

app = FastAPI(title="Dashboard")

_STATIC = Path(__file__).parent / "static" / "index.html"


def _snapshot() -> dict:
    settings = get_settings()
    sqs = sqs_client(settings.aws_endpoint_url, settings)
    with psycopg.connect(psycopg_dsn(settings)) as conn:
        return collect_stats(conn, sqs, settings)


@app.get("/stats")
async def stats() -> dict:
    return await run_in_threadpool(_snapshot)


@app.get("/stats/stream")
async def stats_stream() -> StreamingResponse:
    interval = get_settings().dashboard_interval_seconds

    async def gen():
        while True:
            try:
                snap = await run_in_threadpool(_snapshot)
                yield f"data: {json.dumps(snap)}\n\n"
            except Exception as exc:  # never let one bad tick kill the stream
                yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
            await asyncio.sleep(interval)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    if _STATIC.exists():
        return _STATIC.read_text()
    return "<!doctype html><meta charset=utf-8><title>Dashboard</title><p>dashboard</p>"
