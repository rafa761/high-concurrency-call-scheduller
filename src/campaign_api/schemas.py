import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateCampaignRequest(BaseModel):
    name: str
    max_concurrency: int = Field(gt=0)


class CreateCampaignResponse(BaseModel):
    campaign_id: uuid.UUID
    s3_key: str
    upload_url: str


class CampaignResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    max_concurrency: int
    s3_key: str | None
    created_at: datetime
