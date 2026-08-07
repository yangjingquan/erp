from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDModel


MFG_MATERIAL_ISSUE_SOURCE = "mfg_material_issue"
MFG_MATERIAL_RETURN_SOURCE = "mfg_material_return"
MFG_COMPLETION_SOURCE = "mfg_completion"
SUBCONTRACT_MATERIAL_ISSUE_SOURCE = "subcontract_material_issue"
SUBCONTRACT_RECEIPT_SOURCE = "subcontract_receipt"


class InvStock(UUIDModel):
    __tablename__ = "inv_stock"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    locked_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    available_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )


class InvStockTransaction(UUIDModel):
    __tablename__ = "inv_stock_transaction"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    location_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    consumed_layer_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class InvTransfer(UUIDModel):
    __tablename__ = "inv_transfer"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    from_warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    to_warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    transfer_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    items: Mapped[list["InvTransferItem"]] = relationship(
        back_populates="transfer", cascade="all, delete-orphan"
    )


class InvTransferItem(UUIDModel):
    __tablename__ = "inv_transfer_item"

    transfer_id: Mapped[str] = mapped_column(ForeignKey("inv_transfer.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    transfer: Mapped[InvTransfer] = relationship(back_populates="items")


class InvCount(UUIDModel):
    __tablename__ = "inv_count"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    count_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    items: Mapped[list["InvCountItem"]] = relationship(
        back_populates="count", cascade="all, delete-orphan"
    )


class InvCountItem(UUIDModel):
    __tablename__ = "inv_count_item"

    count_id: Mapped[str] = mapped_column(ForeignKey("inv_count.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    system_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    actual_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    difference_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    count: Mapped[InvCount] = relationship(back_populates="items")


class InvWarning(UUIDModel):
    __tablename__ = "inv_warning"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    current_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    min_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
