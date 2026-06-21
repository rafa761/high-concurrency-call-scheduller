import uuid

import psycopg
import pytest

from ingestion.db import insert_contacts, mark_campaign_ready
from ingestion.parser import ContactRow

DSN = "postgresql://scheduler:scheduler@localhost:5432/scheduler"


@pytest.fixture
def conn():
    try:
        c = psycopg.connect(DSN, connect_timeout=2)
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable on localhost:5432 (run `make up` + migrations)")
    try:
        yield c
    finally:
        c.rollback()  # leave the DB clean — nothing from the test persists
        c.close()


def _make_campaign(conn) -> uuid.UUID:
    cid = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO campaigns (id, name, status, max_concurrency, created_at) "
            "VALUES (%s, %s, 'created', %s, now())",
            (cid, "test", 5),
        )
    return cid


def test_insert_contacts_is_idempotent(conn):
    cid = _make_campaign(conn)
    rows = [
        ContactRow("+15551230001", "America/New_York", {"first_name": "Ann"}),
        ContactRow("+15551230002", "America/Chicago", {"first_name": "Bob"}),
    ]

    first = insert_contacts(conn, cid, rows)
    assert first == 2

    # Re-running the same rows inserts nothing (ON CONFLICT DO NOTHING).
    second = insert_contacts(conn, cid, rows)
    assert second == 0

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM contacts WHERE campaign_id = %s", (cid,))
        assert cur.fetchone()[0] == 2
        cur.execute("SELECT metadata FROM contacts WHERE phone = %s", ("+15551230001",))
        assert cur.fetchone()[0] == {"first_name": "Ann"}


def test_mark_campaign_ready(conn):
    cid = _make_campaign(conn)
    mark_campaign_ready(conn, cid)
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM campaigns WHERE id = %s", (cid,))
        assert cur.fetchone()[0] == "ready"


def test_create_call_tasks_is_idempotent_and_set_based(conn):
    cid = _make_campaign(conn)
    rows = [
        ContactRow("+15551240001", "America/New_York", {}),
        ContactRow("+15551240002", "America/Chicago", {}),
        ContactRow("+15551240003", "America/Denver", {}),
    ]
    insert_contacts(conn, cid, rows)

    from ingestion.db import create_call_tasks

    created = create_call_tasks(conn, cid)
    assert created == 3

    # Re-running creates nothing (one task per contact).
    assert create_call_tasks(conn, cid) == 0

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM call_tasks WHERE campaign_id = %s", (cid,))
        assert cur.fetchone()[0] == 3
        cur.execute(
            "SELECT count(*) FROM call_tasks WHERE campaign_id = %s AND status = 'pending'",
            (cid,),
        )
        assert cur.fetchone()[0] == 3
