from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, UUIDModel


class CostAllocation(AuditMixin, UUIDModel):
    __tablename__ = "cost_allocation"
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    allocation_date: Mapped[date] = mapped_column(Date, nullable=False)
    period: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    basis: Mapped[str] = mapped_column(String(16), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="expense")
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    items_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    __table_args__ = (UniqueConstraint("org_id", "idempotency_key", name="uk_cost_allocation_idempotency"),)


class CostProjectEntry(UUIDModel):
    __tablename__ = "cost_project_entry"
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    allocation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class CostPeriodClose(AuditMixin, UUIDModel):
    __tablename__ = "cost_period_close"
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reopened_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reopened_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    __table_args__ = (UniqueConstraint("org_id", "period", name="uk_cost_period_close_org_period"),)
