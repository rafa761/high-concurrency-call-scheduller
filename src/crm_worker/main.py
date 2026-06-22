import argparse
import json

import httpx
import psycopg

from common.aws import resolve_queue_url, sqs_client
from common.config import get_settings
from common.db import psycopg_dsn
from crm_worker.adapter import CrmError, backoff_seconds, deliver

_LOG_SQL = (
    "INSERT INTO crm_delivery_attempts "
    "(id, outcome_id, attempt_number, status, response_code, idempotency_key, created_at) "
    "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, now())"
)


def _log(conn, outcome_id, attempt_number, status, response_code, idempotency_key) -> None:
    with conn.cursor() as cur:
        cur.execute(_LOG_SQL, (outcome_id, attempt_number, status, response_code, idempotency_key))
    conn.commit()


def run_tick(conn, sqs, queue_url, http, settings) -> int:
    resp = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=2,
        AttributeNames=["ApproximateReceiveCount"],
    )
    delivered = 0
    for msg in resp.get("Messages", []):
        try:
            body = json.loads(msg["Body"])
            outcome_id = body["outcome_id"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            print(f"crm: discarding malformed message: {exc}")
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])
            continue

        receive_count = int(msg.get("Attributes", {}).get("ApproximateReceiveCount", "1"))
        idempotency_key = outcome_id

        try:
            code = deliver(http, idempotency_key, body)
        except (CrmError, httpx.HTTPError) as exc:
            _log(conn, outcome_id, receive_count, "failed", None, idempotency_key)
            print(f"crm: delivery failed for {outcome_id} (attempt {receive_count}): {exc}")
            # Back off, then let SQS redeliver (and dead-letter after maxReceiveCount).
            sqs.change_message_visibility(
                QueueUrl=queue_url,
                ReceiptHandle=msg["ReceiptHandle"],
                VisibilityTimeout=backoff_seconds(receive_count),
            )
            continue

        _log(conn, outcome_id, receive_count, "delivered", code, idempotency_key)
        sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])
        delivered += 1

    if delivered:
        print(f"crm: delivered {delivered} outcome(s)")
    return delivered


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="one receive batch then exit")
    args = parser.parse_args()

    settings = get_settings()
    sqs = sqs_client(settings.aws_endpoint_url, settings)
    queue_url = resolve_queue_url(sqs, settings.outcome_queue)
    http = httpx.Client(base_url=settings.crm_base_url, timeout=10.0)

    with psycopg.connect(psycopg_dsn(settings)) as conn:
        if args.once:
            run_tick(conn, sqs, queue_url, http, settings)
            return
        while True:
            run_tick(conn, sqs, queue_url, http, settings)


if __name__ == "__main__":
    main()
