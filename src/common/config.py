from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCHEDULER_", extra="ignore")

    aws_region: str = "us-east-1"
    aws_endpoint_url: str = "http://localhost:4566"
    # Endpoint embedded in presigned URLs — must be reachable by the *client*
    # (host), not the in-network localstack hostname.
    s3_public_endpoint_url: str = "http://localhost:4566"
    database_url: str = "postgresql+psycopg://scheduler:scheduler@localhost:5432/scheduler"

    campaign_uploads_bucket: str = "campaign-uploads"
    call_artifacts_bucket: str = "call-artifacts"

    dispatch_queue: str = "dispatch"
    outcome_queue: str = "outcome-delivery"
    crm_dlq: str = "crm-dlq"

    scheduler_window_start_hour: int = 8
    scheduler_window_end_hour: int = 21
    scheduler_batch_size: int = 50
    scheduler_poll_interval_seconds: float = 5.0


def get_settings() -> Settings:
    return Settings()
