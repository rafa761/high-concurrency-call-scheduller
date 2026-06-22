import json

import psycopg
from fastapi import FastAPI, Request, Response
from starlette.concurrency import run_in_threadpool

from common.aws import resolve_queue_url, s3_client, sqs_client
from common.config import get_settings
from common.db import psycopg_dsn
from common.signing import verify_signature
from outcome_service.processing import WebhookEvent, process_event

app = FastAPI(title="Outcome Service")

_clients: dict = {}


def _get_clients():
    # Lazy init so the app imports even before infra (the queue) exists.
    if "queue_url" not in _clients:
        settings = get_settings()
        sqs = sqs_client(settings.aws_endpoint_url, settings)
        _clients["s3"] = s3_client(settings.aws_endpoint_url, settings)
        _clients["sqs"] = sqs
        _clients["queue_url"] = resolve_queue_url(sqs, settings.outcome_queue)
    return _clients["s3"], _clients["sqs"], _clients["queue_url"]


def _run_processing(event: WebhookEvent) -> str:
    settings = get_settings()
    s3, sqs, queue_url = _get_clients()
    with psycopg.connect(psycopg_dsn(settings)) as conn:
        return process_event(conn, s3, sqs, queue_url, settings, event)


@app.post("/provider/webhook")
async def webhook(request: Request):
    raw = await request.body()
    signature = request.headers.get("X-Signature", "")
    if not verify_signature(get_settings().webhook_signing_secret, raw, signature):
        return Response(status_code=401)

    data = json.loads(raw)
    event = WebhookEvent(
        event_id=data["event_id"],
        provider_call_id=data["provider_call_id"],
        status=data["status"],
        outcome_type=data.get("outcome_type"),
        transcript=data.get("transcript"),
    )
    result = await run_in_threadpool(_run_processing, event)
    return {"result": result}
