from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, UUIDModel


class SalesQuote(AuditMixin, UUIDModel):
    __tablename__ = "sales_quote"
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    quote_date: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    items: Mapped[list["SalesQuoteItem"]] = relationship(cascade="all, delete-orphan", back_populates="quote")


class SalesQuoteItem(UUIDModel):
    __tablename__ = "sales_quote_item"
    quote_id: Mapped[str] = mapped_column(ForeignKey("sales_quote.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    line_no: Mapped[int] = mapped_column(default=1, nullable=False)
    quote: Mapped[SalesQuote] = relationship(back_populates="items")


class PurchaseRequest(UUIDModel):
    __tablename__ = "purchase_request"
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    requester_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    request_date: Mapped[date] = mapped_column(Date, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    items: Mapped[list["PurchaseRequestItem"]] = relationship(cascade="all, delete-orphan", back_populates="request")


class PurchaseRequestItem(UUIDModel):
    __tablename__ = "purchase_request_item"
    request_id: Mapped[str] = mapped_column(ForeignKey("purchase_request.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    estimated_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    line_no: Mapped[int] = mapped_column(default=1, nullable=False)
    request: Mapped[PurchaseRequest] = relationship(back_populates="items")


class SalesReturnItem(UUIDModel):
    __tablename__ = "sales_return_item"
    return_id: Mapped[str] = mapped_column(ForeignKey("sales_return.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)


class PurchaseReturnItem(UUIDModel):
    __tablename__ = "purchase_return_item"
    return_id: Mapped[str] = mapped_column(ForeignKey("purchase_return.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
