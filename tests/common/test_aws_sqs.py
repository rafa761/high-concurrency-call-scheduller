import pytest
from botocore.exceptions import BotoCoreError, ClientError

from common.aws import resolve_queue_url, send_message, sqs_client
from common.config import get_settings
from common.db import psycopg_dsn


def test_psycopg_dsn_strips_sqlalchemy_driver(monkeypatch):
    monkeypatch.setenv(
        "SCHEDULER_DATABASE_URL", "postgresql+psycopg://u:p@host:5432/db"
    )
    assert psycopg_dsn() == "postgresql://u:p@host:5432/db"


@pytest.fixture
def sqs():
    settings = get_settings()
    client = sqs_client(settings.aws_endpoint_url, settings)
    try:
        url = resolve_queue_url(client, settings.dispatch_queue)
    except (ClientError, BotoCoreError):
        pytest.skip("LocalStack SQS not reachable / dispatch queue missing (run `make up`)")
    return client, url


def test_send_and_receive_roundtrip(sqs):
    client, url = sqs
    msg_id = send_message(client, url, {"hello": "world", "n": 1})
    assert msg_id

    resp = client.receive_message(QueueUrl=url, MaxNumberOfMessages=1, WaitTimeSeconds=2)
    bodies = [m["Body"] for m in resp.get("Messages", [])]
    # cleanup any received messages so the queue stays tidy
    for m in resp.get("Messages", []):
        client.delete_message(QueueUrl=url, ReceiptHandle=m["ReceiptHandle"])
    assert any('"hello": "world"' in b for b in bodies)
