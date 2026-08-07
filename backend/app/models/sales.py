from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, UUIDModel


class SalesOrder(AuditMixin, UUIDModel):
    __tablename__ = "sales_order"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    receivable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    items: Mapped[list["SalesOrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class SalesOrderItem(UUIDModel):
    __tablename__ = "sales_order_item"

    order_id: Mapped[str] = mapped_column(ForeignKey("sales_order.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    warehouse_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    delivered_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    returned_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    line_no: Mapped[int] = mapped_column(default=1, nullable=False)
    order: Mapped[SalesOrder] = relationship(back_populates="items")


class SalesDelivery(AuditMixin, UUIDModel):
    __tablename__ = "sales_delivery"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[str] = mapped_column(ForeignKey("sales_order.id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    items: Mapped[list["SalesDeliveryItem"]] = relationship(
        back_populates="delivery", cascade="all, delete-orphan"
    )


class SalesDeliveryItem(UUIDModel):
    __tablename__ = "sales_delivery_item"

    delivery_id: Mapped[str] = mapped_column(ForeignKey("sales_delivery.id"), nullable=False)
    order_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    delivery: Mapped[SalesDelivery] = relationship(back_populates="items")


class SalesReturn(AuditMixin, UUIDModel):
    __tablename__ = "sales_return"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    source_delivery_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    items: Mapped[list["SalesReturnItem"]] = relationship(cascade="all, delete-orphan")
