import boto3
from botocore.config import Config

from common.config import Settings, get_settings

# LocalStack accepts any credentials; these are the conventional dummy values.
_DUMMY_KEY = "test"
_DUMMY_SECRET = "test"


def s3_client(endpoint_url: str, settings: Settings | None = None):
    settings = settings or get_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=settings.aws_region,
        aws_access_key_id=_DUMMY_KEY,
        aws_secret_access_key=_DUMMY_SECRET,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


def presign_put_url(
    bucket: str,
    key: str,
    expires_in: int = 3600,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    client = s3_client(settings.s3_public_endpoint_url, settings)
    return client.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )
