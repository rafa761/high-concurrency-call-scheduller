import uuid
from dataclasses import dataclass
from datetime import datetime

from psycopg.rows import dict_row

# Claim due, in-window, pending tasks. FOR UPDATE OF call_tasks SKIP LOCKED lets
# many schedulers run concurrently without ever grabbing the same row.
_CLAIM_SQL = """
    SELECT ct.id, ct.campaign_id, ct.attempts, c.phone, c.timezone
    FROM call_tasks ct
    JOIN contacts c ON c.id = ct.contact_id
    WHERE ct.status = 'pending'
      AND (ct.next_eligible_at IS NULL OR ct.next_eligible_at <= %(now)s)
      AND EXTRACT(HOUR FROM (%(now)s AT TIME ZONE c.timezone)) >= %(wstart)s
      AND EXTRACT(HOUR FROM (%(now)s AT TIME ZONE c.timezone)) < %(wend)s
    ORDER BY ct.next_eligible_at NULLS FIRST
    FOR UPDATE OF ct SKIP LOCKED
    LIMIT %(batch)s
"""

# Atomic reservation: succeeds only while there is headroom under the cap.
# The cap lives in campaigns.max_concurrency (single source of truth).
_RESERVE_SQL = """
    UPDATE campaign_concurrency cc
    SET active_count = cc.active_count + 1
    FROM campaigns c
    WHERE cc.campaign_id = %(cid)s
      AND c.id = cc.campaign_id
      AND cc.active_count < c.max_concurrency
    RETURNING cc.active_count
"""

_MARK_SQL = "UPDATE call_tasks SET status = 'dispatching', last_attempt_at = %(now)s WHERE id = %(id)s"


@dataclass
class ClaimedTask:
    task_id: uuid.UUID
    campaign_id: uuid.UUID
    phone: str
    timezone: str
    attempts: int


def claim_and_reserve(
    conn,
    now: datetime,
    batch_size: int,
    window_start_hour: int = 8,
    window_end_hour: int = 21,
) -> list[ClaimedTask]:
    claimed: list[ClaimedTask] = []
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            _CLAIM_SQL,
            {
                "now": now,
                "wstart": window_start_hour,
                "wend": window_end_hour,
                "batch": batch_size,
            },
        )
        candidates = cur.fetchall()
        for row in candidates:
            cur.execute(_RESERVE_SQL, {"cid": row["campaign_id"]})
            if cur.fetchone() is None:
                continue  # cap reached for this campaign; leave the task pending
            cur.execute(_MARK_SQL, {"id": row["id"], "now": now})
            claimed.append(
                ClaimedTask(
                    task_id=row["id"],
                    campaign_id=row["campaign_id"],
                    phone=row["phone"],
                    timezone=row["timezone"],
                    attempts=row["attempts"],
                )
            )
    return claimed
