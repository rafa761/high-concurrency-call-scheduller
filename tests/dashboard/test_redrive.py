import json
import uuid

import pytest

from common.aws import resolve_queue_url, sqs_client
from common.config import get_settings
from dashboard.redrive import redrive_dlq


@pytest.fixture
def sqs_ctx():
    settings = get_settings()
    try:
        sqs = sqs_client(settings.aws_endpoint_url, settings)
        src = resolve_queue_url(sqs, settings.crm_dlq)
        dst = resolve_queue_url(sqs, settings.outcome_queue)
    except Exception:
        pytest.skip("LocalStack SQS not reachable (run `make up`)")
    return sqs, src, dst


def test_redrive_moves_messages_to_destination(sqs_ctx):
    sqs, src, dst = sqs_ctx
    marker = f"redrive-test-{uuid.uuid4()}"
    sqs.send_message(QueueUrl=src, MessageBody=json.dumps({"marker": marker}))

    moved = redrive_dlq(sqs, src, dst, max_messages=50)
    assert moved >= 1

    # the marked message should now be on the destination queue; drain it out so
    # we leave the destination as we found it
    found = False
    for _ in range(10):
        resp = sqs.receive_message(QueueUrl=dst, MaxNumberOfMessages=10, WaitTimeSeconds=1)
        msgs = resp.get("Messages", [])
        if not msgs:
            break
        for m in msgs:
            if marker in m["Body"]:
                found = True
            sqs.delete_message(QueueUrl=dst, ReceiptHandle=m["ReceiptHandle"])
        if found:
            break
    assert found
