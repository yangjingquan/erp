from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, UUIDModel


class ExtEventOutbox(AuditMixin, UUIDModel):
    __tablename__ = "ext_event_outbox"
    __table_args__ = (
        UniqueConstraint(
            "event_type",
            "aggregate_type",
            "aggregate_id",
            name="uk_ext_event_outbox_aggregate_event",
        ),
    )

    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    org_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

class SysApiClient(AuditMixin, UUIDModel):
    __tablename__ = "sys_api_client"
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    client_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    secret_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
