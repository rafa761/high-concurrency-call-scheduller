import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from scheduler.reaper import reap_stuck_tasks

DSN = "postgresql://scheduler:scheduler@localhost:5432/scheduler"
# A reference time in the distant past so real (2026) committed rows never fall
# inside the reaped window — only this test's own backdated tasks do.
NOW = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)


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


def _campaign(conn, active_count: int) -> uuid.UUID:
    cid = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO campaigns (id, name, status, max_concurrency, created_at) "
            "VALUES (%s,'c','ready',10, now())", (cid,))
        cur.execute(
            "INSERT INTO campaign_concurrency (campaign_id, active_count) VALUES (%s, %s)",
            (cid, active_count))
    return cid


def _task(conn, cid, status, attempts, last_attempt_at, provider_call_id="pc-x") -> uuid.UUID:
    contact_id = uuid.uuid4()
    task_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO contacts (id, campaign_id, phone, timezone, metadata, created_at) "
            "VALUES (%s,%s,%s,'America/New_York','{}', now())",
            (contact_id, cid, "+1555" + str(uuid.uuid4().int)[:7]))
        cur.execute(
            "INSERT INTO call_tasks (id, campaign_id, contact_id, status, attempts, provider_call_id, last_attempt_at, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s, now())",
            (task_id, cid, contact_id, status, attempts, provider_call_id, last_attempt_at))
    return task_id


def _row(conn, task_id):
    with conn.cursor() as cur:
        cur.execute("SELECT status, attempts, provider_call_id FROM call_tasks WHERE id=%s", (task_id,))
        return cur.fetchone()


def _active(conn, cid):
    with conn.cursor() as cur:
        cur.execute("SELECT active_count FROM campaign_concurrency WHERE campaign_id=%s", (cid,))
        return cur.fetchone()[0]


def test_reaps_stuck_calling_task_back_to_pending(conn):
    cid = _campaign(conn, active_count=1)
    stuck_at = NOW - timedelta(seconds=300)
    task_id = _task(conn, cid, "calling", attempts=0, last_attempt_at=stuck_at)

    assert reap_stuck_tasks(conn, NOW, stuck_after_seconds=120) == 1
    status, attempts, pcid = _row(conn, task_id)
    assert status == "pending"
    assert attempts == 1
    assert pcid is None
    assert _active(conn, cid) == 0  # slot released


def test_reaps_stuck_task_at_last_attempt_to_exhausted(conn):
    cid = _campaign(conn, active_count=1)
    stuck_at = NOW - timedelta(seconds=300)
    task_id = _task(conn, cid, "dispatching", attempts=2, last_attempt_at=stuck_at)

    assert reap_stuck_tasks(conn, NOW, stuck_after_seconds=120) == 1
    assert _row(conn, task_id)[0] == "exhausted"
    assert _active(conn, cid) == 0


def test_does_not_reap_recent_task(conn):
    cid = _campaign(conn, active_count=1)
    recent = NOW - timedelta(seconds=10)
    task_id = _task(conn, cid, "calling", attempts=0, last_attempt_at=recent)

    assert reap_stuck_tasks(conn, NOW, stuck_after_seconds=120) == 0
    assert _row(conn, task_id)[0] == "calling"
    assert _active(conn, cid) == 1
