from dataclasses import dataclass
from datetime import datetime, timezone

from psycopg.types.json import Jsonb

from common.aws import put_text, send_message
from common.call_task import CallTaskStatus, plan_retry


@dataclass
class WebhookEvent:
    event_id: str
    provider_call_id: str
    status: str
    outcome_type: str | None = None
    transcript: str | None = None


def _release(cur, campaign_id) -> None:
    cur.execute(
        "UPDATE campaign_concurrency SET active_count = active_count - 1 "
        "WHERE campaign_id = %s AND active_count > 0",
        (campaign_id,),
    )


def _publish(sqs, queue_url, outcome_id, task_id, campaign_id, outcome_type) -> None:
    send_message(
        sqs,
        queue_url,
        {
            "outcome_id": str(outcome_id),
            "task_id": str(task_id),
            "campaign_id": str(campaign_id),
            "outcome_type": outcome_type,
        },
    )


def process_event(conn, s3, sqs, queue_url: str, settings, event: WebhookEvent) -> str:
    with conn.cursor() as cur:
        # 1. Dedupe: first writer wins; a repeat delivery is a no-op.
        cur.execute(
            "INSERT INTO provider_events (event_id, received_at) VALUES (%s, now()) "
            "ON CONFLICT (event_id) DO NOTHING",
            (event.event_id,),
        )
        if cur.rowcount == 0:
            conn.commit()
            return "duplicate"

        # 2. Correlate by provider_call_id (only a task still 'calling').
        cur.execute(
            "SELECT id, campaign_id, attempts FROM call_tasks "
            "WHERE provider_call_id = %s AND status = 'calling'",
            (event.provider_call_id,),
        )
        row = cur.fetchone()
        if row is None:
            conn.commit()
            return "unknown"
        task_id, campaign_id, attempts = row

        # 3a. Completed: transcript -> S3, outcome row, complete, release, publish.
        if event.status == "completed":
            key = f"{task_id}/{event.event_id}.txt"
            put_text(s3, settings.call_artifacts_bucket, key, event.transcript or "")
            cur.execute(
                "INSERT INTO outcomes (id, call_task_id, outcome_type, payload, transcript_s3_key, created_at) "
                "VALUES (gen_random_uuid(), %s, %s, %s, %s, now()) RETURNING id",
                (task_id, event.outcome_type or "completed",
                 Jsonb({"provider_call_id": event.provider_call_id}), key),
            )
            outcome_id = cur.fetchone()[0]
            cur.execute("UPDATE call_tasks SET status = 'completed' WHERE id = %s", (task_id,))
            _release(cur, campaign_id)
            conn.commit()
            _publish(sqs, queue_url, outcome_id, task_id, campaign_id, event.outcome_type or "completed")
            return "completed"

        # 3b. Failed: retry with backoff, or exhaust.
        decision = plan_retry(attempts, datetime.now(timezone.utc))
        if decision.status == CallTaskStatus.PENDING:
            cur.execute(
                "UPDATE call_tasks SET status = 'pending', attempts = %s, "
                "next_eligible_at = %s, provider_call_id = NULL WHERE id = %s",
                (decision.attempts, decision.next_eligible_at, task_id),
            )
            _release(cur, campaign_id)
            conn.commit()
            return "retry"

        cur.execute(
            "INSERT INTO outcomes (id, call_task_id, outcome_type, payload, transcript_s3_key, created_at) "
            "VALUES (gen_random_uuid(), %s, 'exhausted', %s, NULL, now()) RETURNING id",
            (task_id, Jsonb({"provider_call_id": event.provider_call_id})),
        )
        outcome_id = cur.fetchone()[0]
        cur.execute(
            "UPDATE call_tasks SET status = 'exhausted', attempts = %s, provider_call_id = NULL WHERE id = %s",
            (decision.attempts, task_id),
        )
        _release(cur, campaign_id)
        conn.commit()
        _publish(sqs, queue_url, outcome_id, task_id, campaign_id, "exhausted")
        return "exhausted"
