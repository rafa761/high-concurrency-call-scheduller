import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index, UniqueConstraint
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


class CampaignConcurrency(SQLModel, table=True):
    __tablename__ = "campaign_concurrency"

    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", primary_key=True)
    active_count: int = Field(default=0)


class CallTask(SQLModel, table=True):
    __tablename__ = "call_tasks"
    __table_args__ = (
        Index("ix_call_tasks_status_next_eligible", "status", "next_eligible_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    contact_id: uuid.UUID = Field(foreign_key="contacts.id", unique=True)
    status: str = Field(default="pending")
    attempts: int = Field(default=0)
    next_eligible_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_attempt_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_column())
