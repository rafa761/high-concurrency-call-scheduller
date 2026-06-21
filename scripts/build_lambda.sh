#!/usr/bin/env bash
# Build the ingestion Lambda deployment zip. Host is linux/amd64 glibc, which
# matches the Lambda runtime, so psycopg manylinux wheels are compatible.
set -euo pipefail

BUILD_DIR=build/ingestion-lambda
ZIP_OUT=infra/terraform/build/ingestion.zip

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$(dirname "$ZIP_OUT")"

# Runtime dependency (boto3 is provided by the Lambda runtime, so not vendored).
uv pip install --target "$BUILD_DIR" --quiet "psycopg[binary]"

# Application code: the ingestion package only (handler imports parser + db).
cp -r src/ingestion "$BUILD_DIR/ingestion"

# Zip the *contents* of the build dir at the archive root. Use Python's zipfile
# (the `zip` CLI is not guaranteed to be installed).
rm -f "$ZIP_OUT"
python3 - "$BUILD_DIR" "$ZIP_OUT" <<'PY'
import os
import sys
import zipfile

build_dir, zip_out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(zip_out, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, _, files in os.walk(build_dir):
        for name in files:
            full = os.path.join(root, name)
            zf.write(full, os.path.relpath(full, build_dir))
PY
echo "built $ZIP_OUT"
