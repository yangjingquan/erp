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


class ExtEventSubscription(AuditMixin, UUIDModel):
    __tablename__ = "ext_event_subscription"
    __table_args__ = (UniqueConstraint("org_id", "name", name="uk_ext_event_subscription_name"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint_url: Mapped[str] = mapped_column(String(500), nullable=False)
    event_types: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    secret_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    signing_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ExtEventDelivery(AuditMixin, UUIDModel):
    __tablename__ = "ext_event_delivery"
    __table_args__ = (UniqueConstraint("event_id", "subscription_id", name="uk_ext_event_delivery_event_subscription"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    subscription_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
