import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _created_at_column() -> Column:
    # Timezone-aware so the model matches the timestamptz columns in Postgres
    # (otherwise alembic autogenerate keeps trying to "revert" it to naive).
    return Column(DateTime(timezone=True), nullable=False)


class Campaign(SQLModel, table=True):
    __tablename__ = "campaigns"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    status: str = Field(default="created")
    max_concurrency: int
    s3_key: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_column())


class Contact(SQLModel, table=True):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("campaign_id", "phone", name="uq_contact_campaign_phone"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    phone: str
    timezone: str
    meta: dict = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON().with_variant(JSONB, "postgresql")),
    )
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_column())
