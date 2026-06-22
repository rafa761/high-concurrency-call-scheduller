def redrive_dlq(sqs, source_url: str, dest_url: str, max_messages: int = 200) -> int:
    """Move messages from a DLQ back to its source queue (bounded per call).

    The CRM worker re-delivers them; because delivery uses a stable idempotency
    key, re-delivering a message that already succeeded is a safe no-op.
    """
    moved = 0
    while moved < max_messages:
        resp = sqs.receive_message(QueueUrl=source_url, MaxNumberOfMessages=10, WaitTimeSeconds=0)
        messages = resp.get("Messages", [])
        if not messages:
            break
        for msg in messages:
            sqs.send_message(QueueUrl=dest_url, MessageBody=msg["Body"])
            sqs.delete_message(QueueUrl=source_url, ReceiptHandle=msg["ReceiptHandle"])
            moved += 1
            if moved >= max_messages:
                break
    return moved
