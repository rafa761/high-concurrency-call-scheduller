import argparse
import json

import httpx
import psycopg

from common.aws import resolve_queue_url, sqs_client
from common.config import get_settings
from common.db import psycopg_dsn
from dispatch_worker.adapter import ProviderError, place_call

_MARK_CALLING = (
    "UPDATE call_tasks SET status = 'calling', provider_call_id = %s "
    "WHERE id = %s AND status = 'dispatching'"
)


def run_tick(conn, sqs, queue_url, http, settings) -> int:
    resp = sqs.receive_message(
        QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=2
    )
    placed = 0
    for msg in resp.get("Messages", []):
        try:
            body = json.loads(msg["Body"])
            task_id = body["task_id"]
            phone = body["phone"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            # Poison message: it can never be processed, so drop it rather than
            # let it redeliver forever (or crash the worker).
            print(f"dispatch: discarding malformed message: {exc}")
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])
            continue

        try:
            provider_call_id = place_call(http, task_id, phone, settings.provider_callback_url)
        except (ProviderError, httpx.HTTPError) as exc:
            print(f"dispatch: placement failed for {task_id}: {exc}; leaving for redelivery")
            continue  # do NOT delete -> SQS redelivers after the visibility timeout

        with conn.cursor() as cur:
            cur.execute(_MARK_CALLING, (provider_call_id, task_id))
        conn.commit()
        sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])
        placed += 1

    if placed:
        print(f"dispatch: placed {placed} call(s)")
    return placed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="one receive batch then exit")
    args = parser.parse_args()

    settings = get_settings()
    sqs = sqs_client(settings.aws_endpoint_url, settings)
    queue_url = resolve_queue_url(sqs, settings.dispatch_queue)
    http = httpx.Client(base_url=settings.provider_base_url, timeout=10.0)

    with psycopg.connect(psycopg_dsn(settings)) as conn:
        if args.once:
            run_tick(conn, sqs, queue_url, http, settings)
            return
        while True:
            run_tick(conn, sqs, queue_url, http, settings)


if __name__ == "__main__":
    main()
