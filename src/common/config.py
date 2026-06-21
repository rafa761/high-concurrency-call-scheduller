from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCHEDULER_", extra="ignore")

    aws_region: str = "us-east-1"
    aws_endpoint_url: str = "http://localhost:4566"
    database_url: str = "postgresql://scheduler:scheduler@localhost:5432/scheduler"

    campaign_uploads_bucket: str = "campaign-uploads"
    call_artifacts_bucket: str = "call-artifacts"

    dispatch_queue: str = "dispatch"
    outcome_queue: str = "outcome-delivery"
    crm_dlq: str = "crm-dlq"


def get_settings() -> Settings:
    return Settings()
