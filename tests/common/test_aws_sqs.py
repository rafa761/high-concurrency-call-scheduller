import uuid

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
def temp_queue():
    # An isolated queue so the test never collides with the shared dispatch queue.
    settings = get_settings()
    client = sqs_client(settings.aws_endpoint_url, settings)
    name = f"test-{uuid.uuid4().hex[:8]}"
    try:
        client.create_queue(QueueName=name)
    except (ClientError, BotoCoreError):
        pytest.skip("LocalStack SQS not reachable (run `make up`)")
    url = resolve_queue_url(client, name)
    try:
        yield client, url
    finally:
        client.delete_queue(QueueUrl=url)


def test_send_and_receive_roundtrip(temp_queue):
    client, url = temp_queue
    msg_id = send_message(client, url, {"hello": "world", "n": 1})
    assert msg_id

    resp = client.receive_message(QueueUrl=url, MaxNumberOfMessages=1, WaitTimeSeconds=2)
    bodies = [m["Body"] for m in resp.get("Messages", [])]
    assert any('"hello": "world"' in b for b in bodies)
