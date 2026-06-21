import uuid

import pytest

from ingestion.handler import extract_campaign_id


def test_extract_campaign_id_from_valid_key():
    cid = uuid.uuid4()
    key = f"campaigns/{cid}/contacts.csv"
    assert extract_campaign_id(key) == cid


def test_extract_campaign_id_rejects_bad_key():
    with pytest.raises(ValueError):
        extract_campaign_id("uploads/not-a-campaign.csv")
