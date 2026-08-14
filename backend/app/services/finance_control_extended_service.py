from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError
from app.core.time import local_now
from app.models.finance import FinBankAccount, FinBankStatement, FinBankStatementLine, FinPeriodCloseChecklist, FinPayment, FinReceipt, FinReconciliationMatch
from app.services.auth_service import UserContext


DEFAULT_CHECKLIST = [
    ("inventory", "库存结账与未完成盘点"),
    ("receivable", "应收核销与账龄"),
    ("payable", "应付核销与三单匹配"),
    ("depreciation", "固定资产折旧"),
    ("cost", "成本分摊与生产成本"),
    ("voucher", "凭证全部记账"),
    ("bank", "银行流水全部对账"),
]


def _money(value) -> str:
    return f"{Decimal(value or 0):.2f}"


def _line(row: FinBankStatementLine) -> dict:
    return {"id": row.id, "line_no": row.line_no, "transaction_date": row.transaction_date.isoformat(), "amount": _money(row.amount), "direction": row.direction, "counterparty": row.counterparty, "reference_no": row.reference_no, "matched_amount": _money(row.matched_amount), "status": row.status, "note": row.note}


def _statement(row: FinBankStatement) -> dict:
    return {"id": row.id, "statement_no": row.statement_no, "bank_account_id": row.bank_account_id, "statement_date": row.statement_date.isoformat(), "opening_balance": _money(row.opening_balance), "closing_balance": _money(row.closing_balance), "status": row.status, "source_file": row.source_file, "lines": [_line(item) for item in row.lines if not item.is_deleted], "unmatched_count": len([item for item in row.lines if not item.is_deleted and item.status != "matched"])}


def create_bank_statement(db: Session, payload, context: UserContext) -> FinBankStatement:
    account = db.scalar(select(FinBankAccount).where(FinBankAccount.id == payload.bank_account_id, FinBankAccount.org_id == context.org_id, FinBankAccount.status == "active", FinBankAccount.is_deleted.is_(False)))
    if account is None:
        raise AppError("银行账户不存在或已停用", code=404)
    statement = FinBankStatement(org_id=context.org_id, statement_no=payload.statement_no or f"BANK-{payload.statement_date:%Y%m%d}-{uuid4().hex[:8].upper()}", bank_account_id=account.id, statement_date=payload.statement_date, opening_balance=payload.opening_balance, closing_balance=payload.closing_balance, source_file=payload.source_file, status="imported")
    statement.lines = [FinBankStatementLine(line_no=item.line_no, transaction_date=item.transaction_date, amount=item.amount, direction=item.direction, counterparty=item.counterparty, reference_no=item.reference_no, note=item.note) for item in payload.lines]
    db.add(statement)
    db.flush()
    return statement


def list_bank_statements(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(FinBankStatement).options(selectinload(FinBankStatement.lines)).where(FinBankStatement.org_id == context.org_id, FinBankStatement.is_deleted.is_(False)).order_by(FinBankStatement.statement_date.desc(), FinBankStatement.created_at.desc())).all()
    return [_statement(row) for row in rows]


def match_bank_statement_line(db: Session, line_id: str, payload, context: UserContext) -> dict:
    line = db.scalar(select(FinBankStatementLine).join(FinBankStatement, FinBankStatement.id == FinBankStatementLine.statement_id).where(FinBankStatementLine.id == line_id, FinBankStatement.org_id == context.org_id, FinBankStatementLine.is_deleted.is_(False)))
    if line is None:
        raise AppError("银行流水不存在", code=404)
    amount = Decimal(payload.matched_amount)
    if amount + Decimal(line.matched_amount or 0) > Decimal(line.amount):
        raise AppError("核销金额不能超过流水金额", code=422)
    match = FinReconciliationMatch(org_id=context.org_id, statement_line_id=line.id, source_type=payload.source_type, source_id=payload.source_id, matched_amount=amount, match_type=payload.match_type, override_reason=payload.override_reason)
    db.add(match)
    line.matched_amount = Decimal(line.matched_amount or 0) + amount
    line.status = "matched" if line.matched_amount == line.amount else "partial"
    db.flush()
    return {"match_id": match.id, "line": _line(line), "source_type": match.source_type, "source_id": match.source_id, "audit": {"match_type": match.match_type, "override_reason": match.override_reason}}


def auto_match_bank_statement(db: Session, statement_id: str, context: UserContext) -> dict:
    statement = db.scalar(select(FinBankStatement).options(selectinload(FinBankStatement.lines)).where(FinBankStatement.id == statement_id, FinBankStatement.org_id == context.org_id, FinBankStatement.is_deleted.is_(False)))
    if statement is None:
        raise AppError("银行对账单不存在", code=404)
    suggestions = []
    for line in statement.lines:
        if line.is_deleted or line.status == "matched":
            continue
        model = FinReceipt if line.direction == "in" else FinPayment
        date_field = model.receipt_date if line.direction == "in" else model.payment_date
        candidates = db.scalars(select(model).where(
            model.org_id == context.org_id,
            model.amount == line.amount,
            date_field.between(line.transaction_date, line.transaction_date),
            model.status.in_({"draft", "submitted", "approved", "posted"}),
        ).order_by(model.doc_no).limit(10)).all()
        suggestions.append({
            "line_id": line.id,
            "reason": "金额、方向、交易日自动匹配",
            "candidates": [{"source_type": "receipt" if line.direction == "in" else "payment", "source_id": item.id, "doc_no": item.doc_no, "amount": _money(item.amount), "match_score": 100} for item in candidates],
            "status": "suggested" if candidates else "unmatched",
        })
    return {"statement_id": statement.id, "suggestions": suggestions, "matched_count": len(statement.lines) - len(suggestions), "unmatched_count": len(suggestions)}


def list_checklist(db: Session, period: str, context: UserContext) -> list[dict]:
    rows = db.scalars(select(FinPeriodCloseChecklist).where(FinPeriodCloseChecklist.org_id == context.org_id, FinPeriodCloseChecklist.period == period, FinPeriodCloseChecklist.is_deleted.is_(False)).order_by(FinPeriodCloseChecklist.id)).all()
    existing = {row.item_code for row in rows}
    for code, name in DEFAULT_CHECKLIST:
        if code not in existing:
            row = FinPeriodCloseChecklist(org_id=context.org_id, period=period, item_code=code, item_name=name, blocking=True, status="pending", owner_id=context.id)
            db.add(row)
            rows.append(row)
    db.flush()
    return [_check_item(row) for row in rows]


def _check_item(row: FinPeriodCloseChecklist) -> dict:
    return {"id": row.id, "period": row.period, "item_code": row.item_code, "item_name": row.item_name, "owner_id": row.owner_id, "blocking": row.blocking, "status": row.status, "evidence": row.evidence, "completed_at": row.completed_at.isoformat() if row.completed_at else None}


def update_checklist_item(db: Session, item_id: str, payload, context: UserContext) -> dict:
    row = db.scalar(select(FinPeriodCloseChecklist).where(FinPeriodCloseChecklist.id == item_id, FinPeriodCloseChecklist.org_id == context.org_id, FinPeriodCloseChecklist.is_deleted.is_(False)))
    if row is None:
        raise AppError("关账检查项不存在", code=404)
    row.status = payload.status
    row.owner_id = payload.owner_id or row.owner_id
    row.evidence = payload.evidence
    row.completed_at = local_now() if payload.status in {"completed", "waived"} else None
    row.completed_by = context.id if row.completed_at else None
    db.flush()
    return _check_item(row)


def ensure_close_ready(db: Session, period: str, context: UserContext) -> list[dict]:
    # Keep legacy periods closable until a checklist has been explicitly opened
    # in the control center. Once rows exist, every blocking item is enforced.
    rows = db.scalars(select(FinPeriodCloseChecklist).where(FinPeriodCloseChecklist.org_id == context.org_id, FinPeriodCloseChecklist.period == period, FinPeriodCloseChecklist.is_deleted.is_(False))).all()
    items = [_check_item(row) for row in rows]
    return [item for item in items if item["blocking"] and item["status"] not in {"completed", "waived"}]
