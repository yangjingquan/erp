from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDModel


class SalesReceivable(UUIDModel):
    __tablename__ = "sales_receivable"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    reconciled_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class PurchasePayable(UUIDModel):
    __tablename__ = "purchase_payable"
    __table_args__ = (UniqueConstraint("source_type", "source_id", name="uk_purchase_payable_source"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    reconciled_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class FinReceipt(UUIDModel):
    __tablename__ = "fin_receipt"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    account_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    reconciles: Mapped[list["FinReceiptReconcile"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )


class FinReceiptReconcile(UUIDModel):
    __tablename__ = "fin_receipt_reconcile"

    receipt_id: Mapped[str] = mapped_column(ForeignKey("fin_receipt.id"), nullable=False)
    receivable_id: Mapped[str] = mapped_column(String(36), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    receipt: Mapped[FinReceipt] = relationship(back_populates="reconciles")


class FinPayment(UUIDModel):
    __tablename__ = "fin_payment"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    account_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)


class FinExpense(UUIDModel):
    __tablename__ = "fin_expense"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    applicant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    expense_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)


class FinAsset(UUIDModel):
    __tablename__ = "fin_asset"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    asset_code: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    original_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    accumulated_depreciation: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class FinVoucher(UUIDModel):
    __tablename__ = "fin_voucher"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    voucher_no: Mapped[str] = mapped_column(String(64), nullable=False)
    voucher_date: Mapped[date] = mapped_column(Date, nullable=False)
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    total_debit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    total_credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    entries: Mapped[list["FinVoucherEntry"]] = relationship(
        back_populates="voucher", cascade="all, delete-orphan"
    )


class FinVoucherEntry(UUIDModel):
    __tablename__ = "fin_voucher_entry"

    voucher_id: Mapped[str] = mapped_column(ForeignKey("fin_voucher.id"), nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False)
    account_code: Mapped[str] = mapped_column(String(64), nullable=False)
    account_name: Mapped[str] = mapped_column(String(128), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    voucher: Mapped[FinVoucher] = relationship(back_populates="entries")
