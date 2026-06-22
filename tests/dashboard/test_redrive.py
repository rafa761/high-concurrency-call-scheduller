import uuid

import pytest

from common.aws import sqs_client
from common.config import get_settings
from dashboard.redrive import redrive_dlq


@pytest.fixture
def queues():
    # Isolated throwaway queues so the test never races the live CRM worker on
    # the real outcome-delivery queue (and never drains the real DLQ).
    settings = get_settings()
    client = sqs_client(settings.aws_endpoint_url, settings)
    suffix = uuid.uuid4().hex[:8]
    try:
        src = client.create_queue(QueueName=f"test-dlq-{suffix}")["QueueUrl"]
    except Exception:
        pytest.skip("LocalStack SQS not reachable (run `make up`)")
    dst = client.create_queue(QueueName=f"test-dest-{suffix}")["QueueUrl"]
    try:
        yield client, src, dst
    finally:
        client.delete_queue(QueueUrl=src)
        client.delete_queue(QueueUrl=dst)


def test_redrive_moves_messages_and_drains_source(queues):
    client, src, dst = queues
    client.send_message(QueueUrl=src, MessageBody='{"outcome_id": "a"}')
    client.send_message(QueueUrl=src, MessageBody='{"outcome_id": "b"}')

    moved = redrive_dlq(client, src, dst, max_messages=50)
    assert moved == 2

    received = []
    for _ in range(5):
        resp = client.receive_message(QueueUrl=dst, MaxNumberOfMessages=10, WaitTimeSeconds=1)
        received.extend(resp.get("Messages", []))
        if len(received) >= 2:
            break
    assert len(received) == 2

    # source is now empty → a second redrive moves nothing
    assert redrive_dlq(client, src, dst) == 0
