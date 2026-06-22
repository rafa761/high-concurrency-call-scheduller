import httpx


class CrmError(Exception):
    pass


def deliver(client: httpx.Client, idempotency_key: str, payload: dict) -> int:
    resp = client.post(
        "/crm/outcomes", json=payload, headers={"Idempotency-Key": idempotency_key}
    )
    if resp.status_code // 100 != 2:
        raise CrmError(f"crm returned {resp.status_code}")
    return resp.status_code


def backoff_seconds(receive_count: int) -> int:
    return min(2 ** receive_count, 20)
