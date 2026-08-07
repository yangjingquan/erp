from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_DOWN

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.cost import CostAllocation, CostPeriodClose, CostProjectEntry
from app.models.inventory import InvStock
from app.services.audit_service import write_operation_log
from app.services.auth_service import UserContext

CENT = Decimal("0.01")


def _period(value: date | str) -> str:
    return value[:7] if isinstance(value, str) else value.strftime("%Y-%m")


def assert_period_open(db: Session, org_id: str, business_date: date) -> None:
    row = db.scalar(select(CostPeriodClose).where(CostPeriodClose.org_id == org_id, CostPeriodClose.period == _period(business_date)))
    if row is not None and row.status == "closed":
        raise AppError("会计期间已结账", code=400)


def create_allocation(db: Session, payload: dict, context: UserContext) -> CostAllocation:
    allocation_date = payload.get("allocation_date") or date.today()
    if isinstance(allocation_date, str):
        allocation_date = date.fromisoformat(allocation_date)
    assert_period_open(db, context.org_id, allocation_date)
    key = payload.get("idempotency_key")
    if key:
        existing = db.scalar(select(CostAllocation).where(CostAllocation.org_id == context.org_id, CostAllocation.idempotency_key == key))
        if existing is not None:
            return existing
    amount = Decimal(str(payload["amount"])).quantize(CENT)
    basis = payload["basis"]
    items = payload.get("items") or []
    values = [Decimal(str(item.get(basis, 0))) for item in items]
    if not values or sum(values, Decimal("0")) <= 0:
        raise AppError("分摊基数合计必须大于零", code=400)
    row = CostAllocation(
        org_id=context.org_id, allocation_date=allocation_date, period=_period(allocation_date), amount=amount,
        basis=basis, source_type=payload.get("source_type", "expense"), source_id=payload.get("source_id", ""),
        idempotency_key=key, items_json=[{**item, basis: str(item.get(basis, 0))} for item in items],
    )
    db.add(row)
    db.flush()
    return row


def post_allocation(db: Session, allocation_id: str, context: UserContext) -> CostAllocation:
    row = db.get(CostAllocation, allocation_id)
    if row is None or row.org_id != context.org_id:
        raise AppError("成本分摊单不存在", code=404)
    assert_period_open(db, context.org_id, row.allocation_date)
    if row.status == "posted":
        return row
    basis_values = [Decimal(str(item.get(row.basis, 0))) for item in row.items_json]
    total_basis = sum(basis_values, Decimal("0"))
    allocated = Decimal("0")
    for index, (item, value) in enumerate(zip(row.items_json, basis_values), start=1):
        if index == len(basis_values):
            amount = row.amount - allocated
        else:
            amount = (row.amount * value / total_basis).quantize(CENT, rounding=ROUND_DOWN)
        allocated += amount
        db.add(CostProjectEntry(
            org_id=context.org_id, project_id=item["project_id"], period=row.period, entry_date=row.allocation_date,
            line_no=index, category="expense", source_type=row.source_type, source_id=row.source_id,
            allocation_id=row.id, amount=amount,
        ))
    row.status = "posted"
    db.flush()
    return row


def calculate_project_cost(db: Session, project_id: str, period: str, context: UserContext) -> dict:
    rows = db.scalars(select(CostProjectEntry).where(CostProjectEntry.org_id == context.org_id, CostProjectEntry.project_id == project_id, CostProjectEntry.period == period)).all()
    by_category: dict[str, Decimal] = {}
    for row in rows:
        by_category[row.category] = by_category.get(row.category, Decimal("0")) + row.amount
    by_category = {key: value.quantize(CENT) for key, value in by_category.items()}
    return {"project_id": project_id, "period": period, "total_amount": sum(by_category.values(), Decimal("0")).quantize(CENT), "by_category": by_category}


def close_period(db: Session, org_id: str, period: str, context: UserContext) -> CostPeriodClose:
    negative = db.scalar(select(InvStock.id).where(InvStock.org_id == org_id, InvStock.quantity < 0))
    if negative is not None:
        raise AppError("存在负库存，不能结账", code=400)
    row = db.scalar(select(CostPeriodClose).where(CostPeriodClose.org_id == org_id, CostPeriodClose.period == period))
    if row is None:
        row = CostPeriodClose(org_id=org_id, period=period, status="open")
        db.add(row)
        db.flush()
    if row.status == "closed":
        return row
    row.status = "closed"
    row.closed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    row.closed_by = context.id
    write_operation_log(db, user=context.user, action="close", resource="cost_period_close", target_id=row.id, detail={"period": period})
    db.flush()
    return row


def reopen_period(db: Session, org_id: str, period: str, context: UserContext) -> CostPeriodClose:
    if not ({"*", "cost:period:reopen"} & context.permissions):
        raise AppError("无权重开会计期间", code=403)
    row = db.scalar(select(CostPeriodClose).where(CostPeriodClose.org_id == org_id, CostPeriodClose.period == period))
    if row is None:
        raise AppError("会计期间不存在", code=404)
    row.status = "open"
    row.reopened_at = datetime.now(timezone.utc).replace(tzinfo=None)
    row.reopened_by = context.id
    write_operation_log(db, user=context.user, action="reopen", resource="cost_period_close", target_id=row.id, detail={"period": period})
    db.flush()
    return row
