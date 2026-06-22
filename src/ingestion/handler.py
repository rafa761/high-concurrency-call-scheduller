import os
import uuid

import boto3
import psycopg

from ingestion.db import bulk_insert_contacts, create_call_tasks, mark_campaign_ready
from ingestion.parser import iter_valid_contacts


def extract_campaign_id(key: str) -> uuid.UUID:
    parts = key.split("/")
    if len(parts) != 3 or parts[0] != "campaigns" or parts[2] != "contacts.csv":
        raise ValueError(f"unexpected object key: {key!r}")
    return uuid.UUID(parts[1])


def _s3_client():
    return boto3.client("s3", endpoint_url=os.environ.get("AWS_ENDPOINT_URL"))


def handler(event, context) -> dict:
    s3 = _s3_client()
    dsn = os.environ["DATABASE_URL"]
    total_ingested = 0
    total_errors = 0

    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        campaign_id = extract_campaign_id(key)

        obj = s3.get_object(Bucket=bucket, Key=key)
        # Stream the object line-by-line; never load the whole file into memory.
        lines = (raw.decode("utf-8") for raw in obj["Body"].iter_lines())

        with psycopg.connect(dsn) as conn:
            inserted = bulk_insert_contacts(conn, campaign_id, iter_valid_contacts(lines))
            tasks_created = create_call_tasks(conn, campaign_id)
            mark_campaign_ready(conn, campaign_id)
            conn.commit()

        total_ingested += inserted
        print(f"ingested campaign={campaign_id} key={key} inserted={inserted} tasks={tasks_created}")

    return {"ingested": total_ingested, "errors": total_errors}
