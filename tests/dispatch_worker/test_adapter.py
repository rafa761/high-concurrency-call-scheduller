import httpx
import pytest

from dispatch_worker.adapter import ProviderError, place_call


def test_place_call_returns_provider_call_id():
    def handler(request):
        return httpx.Response(200, json={"provider_call_id": "pc-123", "status": "accepted"})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://prov")
    assert place_call(client, "t1", "+15551112222", "http://cb") == "pc-123"


def test_place_call_raises_on_provider_error():
    def handler(request):
        return httpx.Response(503, json={"error": "unavailable"})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://prov")
    with pytest.raises(ProviderError):
        place_call(client, "t1", "+15551112222", "http://cb")
