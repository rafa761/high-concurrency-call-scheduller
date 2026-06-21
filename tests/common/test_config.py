from common.config import Settings, get_settings


def test_settings_defaults():
    s = Settings()
    assert s.aws_region == "us-east-1"
    assert s.aws_endpoint_url == "http://localhost:4566"
    assert s.campaign_uploads_bucket == "campaign-uploads"
    assert s.call_artifacts_bucket == "call-artifacts"
    assert s.dispatch_queue == "dispatch"
    assert s.outcome_queue == "outcome-delivery"
    assert s.crm_dlq == "crm-dlq"


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("SCHEDULER_AWS_REGION", "eu-west-1")
    monkeypatch.setenv("SCHEDULER_DISPATCH_QUEUE", "dispatch-test")
    s = Settings()
    assert s.aws_region == "eu-west-1"
    assert s.dispatch_queue == "dispatch-test"


def test_get_settings_returns_settings():
    assert isinstance(get_settings(), Settings)
