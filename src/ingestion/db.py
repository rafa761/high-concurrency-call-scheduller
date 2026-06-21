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
