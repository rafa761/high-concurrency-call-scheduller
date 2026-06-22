import uuid

import psycopg
import pytest

from common.aws import resolve_queue_url, s3_client, sqs_client
from common.config import get_settings
from outcome_service.processing import WebhookEvent, process_event

DSN = "postgresql://scheduler:scheduler@localhost:5432/scheduler"


@pytest.fixture
def ctx():
    settings = get_settings()
    try:
        conn = psycopg.connect(DSN, connect_timeout=2)
        s3 = s3_client(settings.aws_endpoint_url, settings)
        sqs = sqs_client(settings.aws_endpoint_url, settings)
        queue_url = resolve_queue_url(sqs, settings.outcome_queue)
    except Exception:
        pytest.skip("Postgres/LocalStack not reachable (run `make up`)")
    try:
        yield conn, s3, sqs, queue_url, settings
    finally:
        conn.rollback()
        conn.close()


def _calling_task(conn, provider_call_id: str, attempts: int = 0):
    cid = uuid.uuid4()
    contact_id = uuid.uuid4()
    task_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO campaigns (id, name, status, max_concurrency, created_at) "
            "VALUES (%s,'c','ready',10, now())", (cid,))
        cur.execute(
            "INSERT INTO campaign_concurrency (campaign_id, active_count) VALUES (%s, 1)", (cid,))
        cur.execute(
            "INSERT INTO contacts (id, campaign_id, phone, timezone, metadata, created_at) "
            "VALUES (%s,%s,%s,'America/New_York','{}', now())",
            (contact_id, cid, "+1555" + str(uuid.uuid4().int)[:7]))
        cur.execute(
            "INSERT INTO call_tasks (id, campaign_id, contact_id, status, attempts, provider_call_id, created_at) "
            "VALUES (%s,%s,%s,'calling',%s,%s, now())",
            (task_id, cid, contact_id, attempts, provider_call_id))
    conn.commit()
    return cid, task_id


def _status_attempts(conn, task_id):
    with conn.cursor() as cur:
        cur.execute("SELECT status, attempts FROM call_tasks WHERE id=%s", (task_id,))
        return cur.fetchone()


def _active(conn, cid):
    with conn.cursor() as cur:
        cur.execute("SELECT active_count FROM campaign_concurrency WHERE campaign_id=%s", (cid,))
        return cur.fetchone()[0]


def test_completed_persists_outcome_releases_and_publishes(ctx):
    conn, s3, sqs, queue_url, settings = ctx
    pcid = f"pc-{uuid.uuid4()}"
    cid, task_id = _calling_task(conn, pcid)
    event = WebhookEvent(str(uuid.uuid4()), pcid, "completed", "promise_to_pay", "hello transcript")

    result = process_event(conn, s3, sqs, queue_url, settings, event)
    assert result == "completed"
    assert _status_attempts(conn, task_id)[0] == "completed"
    assert _active(conn, cid) == 0

    with conn.cursor() as cur:
        cur.execute("SELECT outcome_type, transcript_s3_key FROM outcomes WHERE call_task_id=%s", (task_id,))
        row = cur.fetchone()
        assert row[0] == "promise_to_pay"
        assert row[1] is not None
    obj = s3.get_object(Bucket=settings.call_artifacts_bucket, Key=row[1])
    assert obj["Body"].read() == b"hello transcript"


def test_failed_with_attempts_left_retries_and_releases(ctx):
    conn, s3, sqs, queue_url, settings = ctx
    pcid = f"pc-{uuid.uuid4()}"
    cid, task_id = _calling_task(conn, pcid, attempts=0)
    event = WebhookEvent(str(uuid.uuid4()), pcid, "failed", "no_answer", None)

    assert process_event(conn, s3, sqs, queue_url, settings, event) == "retry"
    status, attempts = _status_attempts(conn, task_id)
    assert status == "pending"
    assert attempts == 1
    assert _active(conn, cid) == 0


def test_failed_at_last_attempt_exhausts(ctx):
    conn, s3, sqs, queue_url, settings = ctx
    pcid = f"pc-{uuid.uuid4()}"
    cid, task_id = _calling_task(conn, pcid, attempts=2)
    event = WebhookEvent(str(uuid.uuid4()), pcid, "failed", "busy", None)

    assert process_event(conn, s3, sqs, queue_url, settings, event) == "exhausted"
    assert _status_attempts(conn, task_id)[0] == "exhausted"
    assert _active(conn, cid) == 0


def test_duplicate_event_is_ignored(ctx):
    conn, s3, sqs, queue_url, settings = ctx
    pcid = f"pc-{uuid.uuid4()}"
    cid, task_id = _calling_task(conn, pcid)
    event = WebhookEvent(str(uuid.uuid4()), pcid, "completed", "voicemail", "t")

    assert process_event(conn, s3, sqs, queue_url, settings, event) == "completed"
    assert process_event(conn, s3, sqs, queue_url, settings, event) == "duplicate"
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM outcomes WHERE call_task_id=%s", (task_id,))
        assert cur.fetchone()[0] == 1  # not double-counted


def test_unknown_provider_call_id(ctx):
    conn, s3, sqs, queue_url, settings = ctx
    event = WebhookEvent(str(uuid.uuid4()), "pc-does-not-exist", "completed", "voicemail", "t")
    assert process_event(conn, s3, sqs, queue_url, settings, event) == "unknown"
