import argparse
import time
from datetime import datetime, timezone

import psycopg

from common.aws import resolve_queue_url, send_message, sqs_client
from common.config import get_settings
from common.db import psycopg_dsn
from scheduler.claim import claim_and_reserve


def run_tick(conn, sqs, queue_url, settings) -> int:
    now = datetime.now(timezone.utc)
    claimed = claim_and_reserve(
        conn,
        now=now,
        batch_size=settings.batch_size,
        window_start_hour=settings.window_start_hour,
        window_end_hour=settings.window_end_hour,
    )
    conn.commit()  # make 'dispatching' durable before enqueuing

    for task in claimed:
        send_message(
            sqs,
            queue_url,
            {
                "task_id": str(task.task_id),
                "campaign_id": str(task.campaign_id),
                "phone": task.phone,
                "timezone": task.timezone,
                "attempts": task.attempts,
            },
        )
    if claimed:
        print(f"scheduler: dispatched {len(claimed)} task(s)")
    return len(claimed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="run a single tick and exit")
    args = parser.parse_args()

    settings = get_settings()
    sqs = sqs_client(settings.aws_endpoint_url, settings)
    queue_url = resolve_queue_url(sqs, settings.dispatch_queue)

    with psycopg.connect(psycopg_dsn(settings)) as conn:
        if args.once:
            run_tick(conn, sqs, queue_url, settings)
            return
        while True:
            run_tick(conn, sqs, queue_url, settings)
            time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
