import uuid

import psycopg
import pytest

from common.aws import resolve_queue_url, sqs_client
from common.config import get_settings
from dashboard.stats import collect_stats

DSN = "postgresql://scheduler:scheduler@localhost:5432/scheduler"


@pytest.fixture
def ctx():
    settings = get_settings()
    try:
        conn = psycopg.connect(DSN, connect_timeout=2)
        sqs = sqs_client(settings.aws_endpoint_url, settings)
        resolve_queue_url(sqs, settings.dispatch_queue)
    except Exception:
        pytest.skip("Postgres/LocalStack not reachable (run `make up`)")
    try:
        yield conn, sqs, settings
    finally:
        conn.rollback()
        conn.close()


def test_snapshot_has_expected_shape(ctx):
    conn, sqs, settings = ctx
    snap = collect_stats(conn, sqs, settings)
    assert set(snap) == {"queues", "concurrency", "task_funnel", "crm", "totals"}
    assert set(snap["queues"]) == {"dispatch", "outcome_delivery", "crm_dlq"}
    assert set(snap["task_funnel"]) >= {"pending", "completed", "exhausted"}
    assert isinstance(snap["queues"]["crm_dlq"]["visible"], int)
    assert isinstance(snap["concurrency"]["capacity"], int)


def test_task_funnel_and_totals_reflect_inserts(ctx):
    conn, sqs, settings = ctx
    before = collect_stats(conn, sqs, settings)

    cid = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO campaigns (id, name, status, max_concurrency, created_at) "
            "VALUES (%s,'c','ready',10, now())", (cid,))
        for _ in range(3):
            contact_id = uuid.uuid4()
            cur.execute(
                "INSERT INTO contacts (id, campaign_id, phone, timezone, metadata, created_at) "
                "VALUES (%s,%s,%s,'America/New_York','{}', now())",
                (contact_id, cid, "+1555" + str(uuid.uuid4().int)[:7]))
            cur.execute(
                "INSERT INTO call_tasks (id, campaign_id, contact_id, status, attempts, created_at) "
                "VALUES (%s,%s,%s,'completed',1, now())",
                (uuid.uuid4(), cid, contact_id))

    after = collect_stats(conn, sqs, settings)
    # >= (not ==): counts only rise, and other workers may complete tasks
    # concurrently — our inserted rows are guaranteed to be included.
    assert after["task_funnel"]["completed"] - before["task_funnel"]["completed"] >= 3
    assert after["totals"]["campaigns"] - before["totals"]["campaigns"] >= 1
    assert after["totals"]["contacts"] - before["totals"]["contacts"] >= 3
