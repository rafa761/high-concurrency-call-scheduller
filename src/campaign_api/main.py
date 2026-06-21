import uuid

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from campaign_api.schemas import (
    CampaignResponse,
    CreateCampaignRequest,
    CreateCampaignResponse,
)
from common import aws
from common.config import get_settings
from common.db import get_session
from common.models import Campaign

app = FastAPI(title="Campaign Upload API")


@app.post("/campaigns", response_model=CreateCampaignResponse, status_code=201)
async def create_campaign(
    body: CreateCampaignRequest,
    session: AsyncSession = Depends(get_session),
) -> CreateCampaignResponse:
    settings = get_settings()
    campaign = Campaign(name=body.name, max_concurrency=body.max_concurrency)
    campaign.s3_key = f"campaigns/{campaign.id}/contacts.csv"
    session.add(campaign)
    await session.commit()

    upload_url = aws.presign_put_url(settings.campaign_uploads_bucket, campaign.s3_key)
    return CreateCampaignResponse(
        campaign_id=campaign.id,
        s3_key=campaign.s3_key,
        upload_url=upload_url,
    )


@app.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Campaign:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    return campaign
