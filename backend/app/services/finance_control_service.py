from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.finance import (
    FinAccount,
    FinBudget,
    FinCashForecast,
    FinReconciliationStatement,
    FinVoucher,
    FinVoucherEntry,
    PurchasePayable,
    SalesReceivable,
)
from app.services.auth_service import UserContext


def _money(value) -> str:
    return f"{Decimal(value or 0):.2f}"


def _aging_row(row, as_of: date, party_key: str) -> dict:
    outstanding = Decimal(row.total_amount or 0) - Decimal(row.reconciled_amount or 0)
    days = max((as_of - row.due_date).days, 0) if row.due_date else 0
    bucket = "current" if not row.due_date or days == 0 else "1_30" if days <= 30 else "31_60" if days <= 60 else "61_90" if days <= 90 else "91_plus"
    return {"id": row.id, "doc_no": row.doc_no, party_key: getattr(row, f"{party_key}_id"), "due_date": row.due_date.isoformat() if row.due_date else None, "outstanding_amount": _money(outstanding), "days_overdue": days, "bucket": bucket}


def aging_report(db: Session, context: UserContext, statement_type: str, as_of: date) -> dict:
    model = SalesReceivable if statement_type == "ar" else PurchasePayable
    party_key = "customer" if statement_type == "ar" else "supplier"
    rows = db.scalars(select(model).where(model.org_id == context.org_id, model.total_amount > model.reconciled_amount)).all()
    items = [_aging_row(row, as_of, party_key) for row in rows]
    summary = {key: Decimal("0") for key in ("current", "1_30", "31_60", "61_90", "91_plus")}
    for item in items:
        summary[item["bucket"]] += Decimal(item["outstanding_amount"])
    total = sum(summary.values(), Decimal("0"))
    return {"as_of": as_of.isoformat(), "statement_type": statement_type, "items": items, "summary": {key: _money(value) for key, value in summary.items()} | {"total_outstanding": _money(total)}}


def create_budget(db: Session, payload, context: UserContext) -> FinBudget:
    account = db.scalar(select(FinAccount).where(FinAccount.org_id == context.org_id, FinAccount.code == payload.account_code, FinAccount.status == "active", FinAccount.is_deleted.is_(False)))
    if account is None:
        raise AppError("预算科目不存在或已停用", code=404)
    row = db.scalar(select(FinBudget).where(FinBudget.org_id == context.org_id, FinBudget.budget_period == payload.budget_period, FinBudget.account_code == payload.account_code, FinBudget.department_id == payload.department_id, FinBudget.is_deleted.is_(False)))
    if row is None:
        row = FinBudget(org_id=context.org_id, budget_period=payload.budget_period, account_code=payload.account_code, department_id=payload.department_id, budget_amount=payload.budget_amount, note=payload.note)
        db.add(row)
    else:
        if row.status != "draft":
            raise AppError("已审批预算不能直接修改", code=409)
        row.budget_amount = payload.budget_amount
        row.note = payload.note
    db.flush()
    return row


def list_budgets(db: Session, context: UserContext, period: str | None = None) -> list[dict]:
    conditions = [FinBudget.org_id == context.org_id, FinBudget.is_deleted.is_(False)]
    if period:
        conditions.append(FinBudget.budget_period == period)
    rows = db.scalars(select(FinBudget).where(*conditions).order_by(FinBudget.budget_period.desc(), FinBudget.account_code)).all()
    result = []
    for row in rows:
        actual = db.scalar(select(func.coalesce(func.sum(FinVoucherEntry.debit_amount - FinVoucherEntry.credit_amount), 0)).join(FinVoucher, FinVoucher.id == FinVoucherEntry.voucher_id).where(FinVoucher.org_id == context.org_id, FinVoucher.period == row.budget_period, FinVoucher.status == "posted", FinVoucherEntry.account_code == row.account_code)) or 0
        result.append({"id": row.id, "budget_period": row.budget_period, "account_code": row.account_code, "department_id": row.department_id, "budget_amount": _money(row.budget_amount), "actual_amount": _money(actual), "variance_amount": _money(Decimal(row.budget_amount or 0) - Decimal(actual)), "status": row.status, "note": row.note})
    return result


def approve_budget(db: Session, budget_id: str, context: UserContext) -> FinBudget:
    row = db.scalar(select(FinBudget).where(FinBudget.id == budget_id, FinBudget.org_id == context.org_id, FinBudget.is_deleted.is_(False)))
    if row is None:
        raise AppError("预算不存在", code=404)
    if row.status != "draft":
        raise AppError("预算当前不可审批", code=409)
    row.status = "approved"
    db.flush()
    return row


def create_cash_forecast(db: Session, payload, context: UserContext) -> FinCashForecast:
    row = db.scalar(select(FinCashForecast).where(FinCashForecast.org_id == context.org_id, FinCashForecast.forecast_date == payload.forecast_date, FinCashForecast.is_deleted.is_(False)))
    if row is None:
        row = FinCashForecast(org_id=context.org_id, forecast_date=payload.forecast_date)
        db.add(row)
    row.inflow_amount = payload.inflow_amount
    row.outflow_amount = payload.outflow_amount
    row.net_amount = payload.inflow_amount - payload.outflow_amount
    row.source = payload.source
    row.note = payload.note
    db.flush()
    return row


def list_cash_forecasts(db: Session, context: UserContext, date_from: date | None = None, date_to: date | None = None) -> list[dict]:
    conditions = [FinCashForecast.org_id == context.org_id, FinCashForecast.is_deleted.is_(False)]
    if date_from:
        conditions.append(FinCashForecast.forecast_date >= date_from)
    if date_to:
        conditions.append(FinCashForecast.forecast_date <= date_to)
    rows = db.scalars(select(FinCashForecast).where(*conditions).order_by(FinCashForecast.forecast_date)).all()
    return [{"id": row.id, "forecast_date": row.forecast_date.isoformat(), "inflow_amount": _money(row.inflow_amount), "outflow_amount": _money(row.outflow_amount), "net_amount": _money(row.net_amount), "source": row.source, "status": row.status, "note": row.note} for row in rows]


def create_reconciliation_statement(db: Session, payload, context: UserContext) -> FinReconciliationStatement:
    model = SalesReceivable if payload.statement_type == "ar" else PurchasePayable
    party_field = model.customer_id if payload.statement_type == "ar" else model.supplier_id
    reconciled = db.scalar(select(func.coalesce(func.sum(model.total_amount - model.reconciled_amount), 0)).where(model.org_id == context.org_id, party_field == payload.party_id)) or Decimal("0")
    row = FinReconciliationStatement(org_id=context.org_id, statement_no=f"RECON-{payload.statement_type.upper()}-{payload.period}-{uuid4().hex[:8].upper()}", statement_type=payload.statement_type, party_id=payload.party_id, period=payload.period, statement_amount=payload.statement_amount, reconciled_amount=reconciled, status="matched" if Decimal(reconciled) == payload.statement_amount else "difference", note=payload.note)
    db.add(row)
    db.flush()
    return row


def list_reconciliation_statements(db: Session, context: UserContext, statement_type: str | None = None) -> list[dict]:
    conditions = [FinReconciliationStatement.org_id == context.org_id, FinReconciliationStatement.is_deleted.is_(False)]
    if statement_type:
        conditions.append(FinReconciliationStatement.statement_type == statement_type)
    rows = db.scalars(select(FinReconciliationStatement).where(*conditions).order_by(FinReconciliationStatement.created_at.desc())).all()
    return [{"id": row.id, "statement_no": row.statement_no, "statement_type": row.statement_type, "party_id": row.party_id, "period": row.period, "statement_amount": _money(row.statement_amount), "reconciled_amount": _money(row.reconciled_amount), "difference_amount": _money(Decimal(row.statement_amount or 0) - Decimal(row.reconciled_amount or 0)), "status": row.status, "note": row.note} for row in rows]
