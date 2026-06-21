import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Campaign(SQLModel, table=True):
    __tablename__ = "campaigns"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    status: str = Field(default="created")
    max_concurrency: int
    s3_key: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
