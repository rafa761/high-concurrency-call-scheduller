import httpx


class ProviderError(Exception):
    pass


def place_call(client: httpx.Client, task_id: str, phone: str, callback_url: str) -> str:
    resp = client.post(
        "/calls",
        json={"task_id": task_id, "phone": phone, "callback_url": callback_url},
    )
    if resp.status_code != 200:
        raise ProviderError(f"provider returned {resp.status_code}")
    return resp.json()["provider_call_id"]
