from datetime import datetime, timedelta

from psycopg.rows import dict_row

from common.call_task import CallTaskStatus, plan_retry

_FIND_SQL = """
    SELECT id, campaign_id, attempts
    FROM call_tasks
    WHERE status IN ('dispatching', 'calling')
      AND last_attempt_at < %(cutoff)s
    FOR UPDATE SKIP LOCKED
"""

_RELEASE_SQL = (
    "UPDATE campaign_concurrency SET active_count = active_count - 1 "
    "WHERE campaign_id = %s AND active_count > 0"
)


def reap_stuck_tasks(conn, now: datetime, stuck_after_seconds: int) -> int:
    cutoff = now - timedelta(seconds=stuck_after_seconds)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(_FIND_SQL, {"cutoff": cutoff})
        stuck = cur.fetchall()
        for task in stuck:
            decision = plan_retry(task["attempts"], now)
            if decision.status == CallTaskStatus.PENDING:
                cur.execute(
                    "UPDATE call_tasks SET status = 'pending', attempts = %s, "
                    "next_eligible_at = %s, provider_call_id = NULL WHERE id = %s",
                    (decision.attempts, decision.next_eligible_at, task["id"]),
                )
            else:
                cur.execute(
                    "UPDATE call_tasks SET status = 'exhausted', attempts = %s, "
                    "provider_call_id = NULL WHERE id = %s",
                    (decision.attempts, task["id"]),
                )
            cur.execute(_RELEASE_SQL, (task["campaign_id"],))
    return len(stuck)
