import uuid

from psycopg.types.json import Jsonb

from ingestion.parser import ContactRow

_INSERT_SQL = """
    INSERT INTO contacts (id, campaign_id, phone, timezone, metadata, created_at)
    VALUES (gen_random_uuid(), %s, %s, %s, %s, now())
    ON CONFLICT (campaign_id, phone) DO NOTHING
"""


def insert_contacts(conn, campaign_id: uuid.UUID, rows: list[ContactRow]) -> int:
    inserted = 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                _INSERT_SQL,
                (campaign_id, row.phone, row.timezone, Jsonb(row.metadata)),
            )
            inserted += cur.rowcount  # 1 if inserted, 0 if it conflicted
    return inserted


def mark_campaign_ready(conn, campaign_id: uuid.UUID) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE campaigns SET status = 'ready' WHERE id = %s",
            (campaign_id,),
        )


# 'pending' matches common.call_task.CallTaskStatus.PENDING (kept as a literal
# so the Lambda package need not vendor the common package).
_CREATE_TASKS_SQL = """
    INSERT INTO call_tasks (id, campaign_id, contact_id, status, attempts, next_eligible_at, created_at)
    SELECT gen_random_uuid(), c.campaign_id, c.id, 'pending', 0, now(), now()
    FROM contacts c
    WHERE c.campaign_id = %s
    ON CONFLICT (contact_id) DO NOTHING
"""


def create_call_tasks(conn, campaign_id) -> int:
    with conn.cursor() as cur:
        cur.execute(_CREATE_TASKS_SQL, (campaign_id,))
        return cur.rowcount
