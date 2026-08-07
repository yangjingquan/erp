from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, UUIDModel


class PurchaseOrder(AuditMixin, UUIDModel):
    __tablename__ = "purchase_order"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(36), nullable=False)
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    payable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class PurchaseOrderItem(UUIDModel):
    __tablename__ = "purchase_order_item"

    order_id: Mapped[str] = mapped_column(ForeignKey("purchase_order.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    warehouse_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    returned_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    line_no: Mapped[int] = mapped_column(default=1, nullable=False)
    order: Mapped[PurchaseOrder] = relationship(back_populates="items")


class PurchaseReceipt(AuditMixin, UUIDModel):
    __tablename__ = "purchase_receipt"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[str] = mapped_column(ForeignKey("purchase_order.id"), nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(36), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    items: Mapped[list["PurchaseReceiptItem"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )


class PurchaseReceiptItem(UUIDModel):
    __tablename__ = "purchase_receipt_item"

    receipt_id: Mapped[str] = mapped_column(ForeignKey("purchase_receipt.id"), nullable=False)
    order_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    receipt: Mapped[PurchaseReceipt] = relationship(back_populates="items")


class PurchaseReturn(AuditMixin, UUIDModel):
    __tablename__ = "purchase_return"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    source_receipt_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    supplier_id: Mapped[str] = mapped_column(String(36), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    items: Mapped[list["PurchaseReturnItem"]] = relationship(cascade="all, delete-orphan")
