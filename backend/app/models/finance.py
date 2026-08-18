from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, UUIDModel


class FinAccount(AuditMixin, UUIDModel):
    __tablename__ = "fin_account"
    __table_args__ = (UniqueConstraint("org_id", "code", name="uk_fin_account_org_code"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False)
    balance_direction: Mapped[str] = mapped_column(String(8), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    allow_posting: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class FinAccountingDimension(AuditMixin, UUIDModel):
    __tablename__ = "fin_accounting_dimension"
    __table_args__ = (UniqueConstraint("org_id", "code", name="uk_fin_dimension_org_code"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    dimension_type: Mapped[str] = mapped_column(String(32), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class FinFiscalPeriod(AuditMixin, UUIDModel):
    __tablename__ = "fin_fiscal_period"
    __table_args__ = (UniqueConstraint("org_id", "period", name="uk_fin_fiscal_period_org"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    reopened_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class FinBankAccount(AuditMixin, UUIDModel):
    __tablename__ = "fin_bank_account"
    __table_args__ = (UniqueConstraint("org_id", "account_no", name="uk_fin_bank_account_org_no"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(128), nullable=False)
    account_no: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="CNY", nullable=False)
    ledger_account_id: Mapped[str] = mapped_column(ForeignKey("fin_account.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class FinCurrency(AuditMixin, UUIDModel):
    __tablename__ = "fin_currency"
    __table_args__ = (UniqueConstraint("org_id", "code", name="uk_fin_currency_org_code"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(8), nullable=True)
    decimal_places: Mapped[int] = mapped_column(default=2, nullable=False)
    is_base: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class FinExchangeRate(AuditMixin, UUIDModel):
    __tablename__ = "fin_exchange_rate"
    __table_args__ = (UniqueConstraint("org_id", "base_currency", "quote_currency", "rate_date", name="uk_fin_exchange_rate_day"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="manual", nullable=False)


class FinBudget(AuditMixin, UUIDModel):
    __tablename__ = "fin_budget"
    __table_args__ = (UniqueConstraint("org_id", "budget_period", "account_code", "department_id", name="uk_fin_budget_scope"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    budget_period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    account_code: Mapped[str] = mapped_column(String(64), nullable=False)
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class FinCashForecast(AuditMixin, UUIDModel):
    __tablename__ = "fin_cash_forecast"
    __table_args__ = (UniqueConstraint("org_id", "forecast_date", name="uk_fin_cash_forecast_day"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    inflow_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    outflow_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="manual", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class FinReconciliationStatement(AuditMixin, UUIDModel):
    __tablename__ = "fin_reconciliation_statement"
    __table_args__ = (UniqueConstraint("org_id", "statement_no", name="uk_fin_reconciliation_statement_no"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    statement_no: Mapped[str] = mapped_column(String(64), nullable=False)
    statement_type: Mapped[str] = mapped_column(String(8), nullable=False)
    party_id: Mapped[str] = mapped_column(String(36), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    statement_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    reconciled_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class FinBankStatement(AuditMixin, UUIDModel):
    __tablename__ = "fin_bank_statement"
    __table_args__ = (UniqueConstraint("org_id", "statement_no", name="uk_fin_bank_statement_no"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    statement_no: Mapped[str] = mapped_column(String(64), nullable=False)
    bank_account_id: Mapped[str] = mapped_column(ForeignKey("fin_bank_account.id"), nullable=False, index=True)
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    source_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lines: Mapped[list["FinBankStatementLine"]] = relationship(back_populates="statement", cascade="all, delete-orphan")


class FinBankStatementLine(AuditMixin, UUIDModel):
    __tablename__ = "fin_bank_statement_line"
    __table_args__ = (UniqueConstraint("statement_id", "line_no", name="uk_fin_bank_statement_line_no"),)

    statement_id: Mapped[str] = mapped_column(ForeignKey("fin_bank_statement.id"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    counterparty: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reference_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    matched_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="unmatched", nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    statement: Mapped[FinBankStatement] = relationship(back_populates="lines")


class FinReconciliationMatch(AuditMixin, UUIDModel):
    __tablename__ = "fin_reconciliation_match"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    statement_line_id: Mapped[str] = mapped_column(ForeignKey("fin_bank_statement_line.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    matched_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    match_type: Mapped[str] = mapped_column(String(32), default="rule", nullable=False)
    override_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class FinPeriodCloseChecklist(AuditMixin, UUIDModel):
    __tablename__ = "fin_period_close_checklist"
    __table_args__ = (UniqueConstraint("org_id", "period", "item_code", name="uk_fin_period_checklist_item"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    item_name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    blocking: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    evidence: Mapped[str | None] = mapped_column(String(500), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


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
    reconciles: Mapped[list["FinPaymentReconcile"]] = relationship(
        back_populates="payment", cascade="all, delete-orphan"
    )


class FinPaymentReconcile(UUIDModel):
    __tablename__ = "fin_payment_reconcile"

    payment_id: Mapped[str] = mapped_column(ForeignKey("fin_payment.id"), nullable=False)
    payable_id: Mapped[str] = mapped_column(String(36), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    payment: Mapped[FinPayment] = relationship(back_populates="reconciles")


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
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class FinAsset(UUIDModel):
    __tablename__ = "fin_asset"
    __table_args__ = (UniqueConstraint("org_id", "asset_code", name="uk_fin_asset_org_code"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    asset_code: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    original_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    accumulated_depreciation: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    useful_life_months: Mapped[int] = mapped_column(default=60, nullable=False)
    residual_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0, nullable=False)
    depreciation_method: Mapped[str] = mapped_column(String(32), default="straight_line", nullable=False)
    depreciation_account_code: Mapped[str] = mapped_column(String(64), default="1602", nullable=False)
    expense_account_code: Mapped[str] = mapped_column(String(64), default="6602", nullable=False)
    last_depreciation_period: Mapped[str | None] = mapped_column(String(7), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class FinAssetDepreciation(AuditMixin, UUIDModel):
    __tablename__ = "fin_asset_depreciation"
    __table_args__ = (UniqueConstraint("asset_id", "period", name="uk_fin_asset_depreciation_period"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("fin_asset.id"), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    voucher_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="posted", nullable=False)


class FinVoucher(UUIDModel):
    __tablename__ = "fin_voucher"
    __table_args__ = (
        UniqueConstraint("org_id", "voucher_no", name="uk_fin_voucher_no"),
        UniqueConstraint("org_id", "source_type", "source_id", name="uk_fin_voucher_source"),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    voucher_no: Mapped[str] = mapped_column(String(64), nullable=False)
    voucher_date: Mapped[date] = mapped_column(Date, nullable=False)
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    total_debit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    total_credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    posted_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reversed_from_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    reversal_voucher_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    entries: Mapped[list["FinVoucherEntry"]] = relationship(
        back_populates="voucher", cascade="all, delete-orphan"
    )


class FinVoucherEntry(UUIDModel):
    __tablename__ = "fin_voucher_entry"

    voucher_id: Mapped[str] = mapped_column(ForeignKey("fin_voucher.id"), nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("fin_account.id"), nullable=True)
    account_code: Mapped[str] = mapped_column(String(64), nullable=False)
    account_name: Mapped[str] = mapped_column(String(128), nullable=False)
    dimensions_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    voucher: Mapped[FinVoucher] = relationship(back_populates="entries")
