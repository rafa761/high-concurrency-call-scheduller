from common.aws import resolve_queue_url

_FUNNEL_STATUSES = ["pending", "dispatching", "calling", "completed", "exhausted"]


def _queue_depth(sqs, queue_url: str) -> dict:
    attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
    )["Attributes"]
    return {
        "visible": int(attrs.get("ApproximateNumberOfMessages", 0)),
        "in_flight": int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0)),
    }


def _queues(sqs, settings) -> dict:
    return {
        "dispatch": _queue_depth(sqs, resolve_queue_url(sqs, settings.dispatch_queue)),
        "outcome_delivery": _queue_depth(sqs, resolve_queue_url(sqs, settings.outcome_queue)),
        "crm_dlq": _queue_depth(sqs, resolve_queue_url(sqs, settings.crm_dlq)),
    }


def _concurrency(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(active_count), 0) FROM campaign_concurrency")
        active = int(cur.fetchone()[0])
        cur.execute("SELECT COALESCE(SUM(max_concurrency), 0) FROM campaigns")
        capacity = int(cur.fetchone()[0])
    return {"active": active, "capacity": capacity}


def _task_funnel(conn) -> dict:
    funnel = {status: 0 for status in _FUNNEL_STATUSES}
    with conn.cursor() as cur:
        cur.execute("SELECT status, count(*) FROM call_tasks GROUP BY status")
        for status, count in cur.fetchall():
            funnel[status] = int(count)
    return funnel


def _crm(conn) -> dict:
    result = {"delivered": 0, "failed": 0}
    with conn.cursor() as cur:
        cur.execute("SELECT status, count(*) FROM crm_delivery_attempts GROUP BY status")
        for status, count in cur.fetchall():
            if status in result:
                result[status] = int(count)
    return result


def _totals(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM campaigns")
        campaigns = int(cur.fetchone()[0])
        cur.execute("SELECT count(*) FROM contacts")
        contacts = int(cur.fetchone()[0])
        cur.execute("SELECT count(*) FROM call_tasks")
        call_tasks = int(cur.fetchone()[0])
    return {"campaigns": campaigns, "contacts": contacts, "call_tasks": call_tasks}


def collect_stats(conn, sqs, settings) -> dict:
    return {
        "queues": _queues(sqs, settings),
        "concurrency": _concurrency(conn),
        "task_funnel": _task_funnel(conn),
        "crm": _crm(conn),
        "totals": _totals(conn),
    }
