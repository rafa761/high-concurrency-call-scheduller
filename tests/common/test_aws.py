from urllib.parse import parse_qs, urlparse

from common.aws import presign_put_url


def test_presign_put_url_targets_public_endpoint(monkeypatch):
    monkeypatch.setenv("SCHEDULER_S3_PUBLIC_ENDPOINT_URL", "http://localhost:4566")

    url = presign_put_url("campaign-uploads", "campaigns/abc/contacts.csv")

    parsed = urlparse(url)
    assert parsed.hostname == "localhost"
    assert parsed.port == 4566
    # path-style addressing: bucket and key are in the path
    assert parsed.path == "/campaign-uploads/campaigns/abc/contacts.csv"

    qs = parse_qs(parsed.query)
    assert "X-Amz-Signature" in qs
    assert "X-Amz-Expires" in qs
