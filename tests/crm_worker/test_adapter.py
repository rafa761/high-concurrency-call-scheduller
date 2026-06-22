import httpx
import pytest

from crm_worker.adapter import CrmError, backoff_seconds, deliver


def test_deliver_sends_idempotency_key_and_returns_code():
    seen = {}

    def handler(request):
        seen["key"] = request.headers.get("Idempotency-Key")
        return httpx.Response(200, json={"status": "recorded"})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://crm")
    assert deliver(client, "out-1", {"outcome_id": "out-1"}) == 200
    assert seen["key"] == "out-1"


def test_deliver_raises_on_failure():
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(503)), base_url="http://crm"
    )
    with pytest.raises(CrmError):
        deliver(client, "out-1", {"outcome_id": "out-1"})


def test_backoff_grows_then_caps():
    assert backoff_seconds(1) == 2
    assert backoff_seconds(2) == 4
    assert backoff_seconds(3) == 8
    assert backoff_seconds(10) == 20  # capped
