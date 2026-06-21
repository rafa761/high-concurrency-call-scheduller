#!/usr/bin/env bash
# End-to-end smoke test for the Campaign Upload API:
# create a campaign, upload a CSV straight to S3 via the presigned URL,
# and confirm the object landed. Requires `make start` to be running.
set -euo pipefail

API=${API:-http://localhost:8000}
CSV=${CSV:-data/sample-contacts.csv}

echo "1. Creating campaign..."
RESP=$(curl -s -X POST "$API/campaigns" -H 'content-type: application/json' \
  -d '{"name":"demo","max_concurrency":10}')
echo "$RESP" | python3 -m json.tool

CAMPAIGN_ID=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['campaign_id'])")
UPLOAD_URL=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['upload_url'])")

echo "2. Uploading $CSV straight to S3 via presigned URL..."
curl -s -o /dev/null -w "   PUT -> %{http_code}\n" -X PUT --upload-file "$CSV" "$UPLOAD_URL"

echo "3. Object in S3:"
docker compose exec -T localstack awslocal s3 ls "s3://campaign-uploads/campaigns/$CAMPAIGN_ID/"

echo "4. Campaign record:"
curl -s "$API/campaigns/$CAMPAIGN_ID" | python3 -m json.tool
