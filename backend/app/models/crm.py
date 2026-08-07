from datetime import datetime
from sqlalchemy import DateTime, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import AuditMixin, UUIDModel

class CrmLead(AuditMixin, UUIDModel):
    __tablename__ = "crm_lead"
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(128))
    source: Mapped[str | None] = mapped_column(String(64))
    owner_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(32), default="new", nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(36))
    contact_id: Mapped[str | None] = mapped_column(String(36))
    opportunity_id: Mapped[str | None] = mapped_column(String(36))

class CrmOpportunity(AuditMixin, UUIDModel):
    __tablename__ = "crm_opportunity"
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(36))
    owner_id: Mapped[str | None] = mapped_column(String(36))
    stage: Mapped[str] = mapped_column(String(32), default="new", nullable=False)
    loss_reason: Mapped[str | None] = mapped_column(String(255))

class CrmContact(AuditMixin, UUIDModel):
    __tablename__ = "crm_contact"
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    customer_id: Mapped[str | None] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(128))
    __table_args__ = (UniqueConstraint("org_id", "phone", name="uk_crm_contact_phone"),)

class CrmFollowUp(AuditMixin, UUIDModel):
    __tablename__ = "crm_follow_up"
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    opportunity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    content: Mapped[str] = mapped_column(String(1000), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
