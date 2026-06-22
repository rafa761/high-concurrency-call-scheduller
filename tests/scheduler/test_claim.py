import uuid
from datetime import datetime, timezone

import psycopg
import pytest

from scheduler.claim import claim_and_reserve

DSN = "postgresql://scheduler:scheduler@localhost:5432/scheduler"
# 2026-06-21 15:00 UTC -> New_York (EDT, UTC-4) = 11:00 (in window),
#                         Honolulu (HST, UTC-10) = 05:00 (out of window).
NOW = datetime(2026, 6, 21, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    try:
        c = psycopg.connect(DSN, connect_timeout=2)
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable (run `make up` + migrations)")
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def _campaign(conn, max_concurrency: int) -> uuid.UUID:
    cid = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO campaigns (id, name, status, max_concurrency, created_at) "
            "VALUES (%s, 'c', 'ready', %s, now())",
            (cid, max_concurrency),
        )
        cur.execute(
            "INSERT INTO campaign_concurrency (campaign_id, active_count) VALUES (%s, 0)",
            (cid,),
        )
    return cid


def _task(conn, campaign_id, tz: str, next_eligible_at=None) -> uuid.UUID:
    contact_id = uuid.uuid4()
    task_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO contacts (id, campaign_id, phone, timezone, metadata, created_at) "
            "VALUES (%s, %s, %s, %s, '{}', now())",
            (contact_id, campaign_id, "+1555" + str(uuid.uuid4().int)[:7], tz),
        )
        cur.execute(
            "INSERT INTO call_tasks (id, campaign_id, contact_id, status, attempts, next_eligible_at, created_at) "
            "VALUES (%s, %s, %s, 'pending', 0, %s, now())",
            (task_id, campaign_id, contact_id, next_eligible_at),
        )
    return task_id


def _status(conn, task_id) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM call_tasks WHERE id = %s", (task_id,))
        return cur.fetchone()[0]


def test_claims_only_in_window_tasks(conn):
    cid = _campaign(conn, max_concurrency=10)
    in_window = _task(conn, cid, "America/New_York")
    out_window = _task(conn, cid, "Pacific/Honolulu")

    claimed = claim_and_reserve(conn, now=NOW, batch_size=10)

    ids = {c.task_id for c in claimed}
    assert in_window in ids
    assert out_window not in ids
    assert _status(conn, in_window) == "dispatching"
    assert _status(conn, out_window) == "pending"

    with conn.cursor() as cur:
        cur.execute("SELECT last_attempt_at FROM call_tasks WHERE id = %s", (in_window,))
        assert cur.fetchone()[0] is not None


def test_respects_concurrency_cap(conn):
    cid = _campaign(conn, max_concurrency=2)
    tasks = [_task(conn, cid, "America/New_York") for _ in range(5)]

    claimed = claim_and_reserve(conn, now=NOW, batch_size=10)
    assert len(claimed) == 2

    with conn.cursor() as cur:
        cur.execute("SELECT active_count FROM campaign_concurrency WHERE campaign_id = %s", (cid,))
        assert cur.fetchone()[0] == 2
        cur.execute(
            "SELECT count(*) FROM call_tasks WHERE campaign_id = %s AND status = 'dispatching'",
            (cid,),
        )
        assert cur.fetchone()[0] == 2


def test_skips_tasks_not_yet_due(conn):
    cid = _campaign(conn, max_concurrency=10)
    future = datetime(2099, 1, 1, tzinfo=timezone.utc)
    not_due = _task(conn, cid, "America/New_York", next_eligible_at=future)

    claimed = claim_and_reserve(conn, now=NOW, batch_size=10)
    assert not_due not in {c.task_id for c in claimed}
    assert _status(conn, not_due) == "pending"
