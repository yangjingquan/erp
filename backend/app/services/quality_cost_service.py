from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_today
from app.models.advanced_operations import QaCustomerClaim, QaQualityCost, QaSupplierQuality
from app.models.quality import QaInspection, QaNonconformity
from app.services.auth_service import UserContext


QUALITY_COST_TYPES = {"prevention", "appraisal", "internal_failure", "external_failure"}
QUALITY_COST_SOURCE_TYPES = {"inspection", "nonconformance", "supplier_quality", "customer_claim"}
APPRAISAL_UNIT_COST = Decimal("50.00")
PREVENTION_CAPA_COST = Decimal("200.00")
FAILURE_COST_BY_SEVERITY = {
    "critical": Decimal("1000.00"),
    "major": Decimal("500.00"),
    "minor": Decimal("100.00"),
}


def _period(value: date | None = None) -> str:
    return (value or local_today()).strftime("%Y-%m")


def _validate_cost_type(cost_type: str) -> None:
    if cost_type not in QUALITY_COST_TYPES:
        raise AppError("质量成本类型不合法", code=422)


def ensure_quality_cost(
    db: Session,
    context: UserContext,
    *,
    period: str,
    cost_type: str,
    amount: Decimal,
    source_type: str,
    source_id: str,
    note: str,
) -> QaQualityCost:
    _validate_cost_type(cost_type)
    if source_type not in QUALITY_COST_SOURCE_TYPES:
        raise AppError("质量成本来源类型不合法", code=422)
    existing = db.scalar(
        select(QaQualityCost).where(
            QaQualityCost.org_id == context.org_id,
            QaQualityCost.cost_type == cost_type,
            QaQualityCost.source_type == source_type,
            QaQualityCost.source_id == source_id,
            QaQualityCost.is_deleted.is_(False),
        )
    )
    if existing is not None:
        if existing.auto_generated:
            existing.period = period
            existing.amount = amount
            existing.note = note
        db.flush()
        return existing
    row = QaQualityCost(
        org_id=context.org_id,
        period=period,
        cost_type=cost_type,
        amount=amount,
        source_type=source_type,
        source_id=source_id,
        status="estimated",
        auto_generated=True,
        note=note,
    )
    db.add(row)
    db.flush()
    return row


def create_quality_cost(db: Session, payload, context: UserContext) -> QaQualityCost:
    data = payload.model_dump()
    _validate_cost_type(data["cost_type"])
    source_type = data.get("source_type") or None
    source_id = data.get("source_id") or None
    if bool(source_type) != bool(source_id):
        raise AppError("质量成本来源类型和来源单据必须同时填写", code=422)
    if source_type and source_type not in QUALITY_COST_SOURCE_TYPES:
        raise AppError("质量成本来源类型不合法", code=422)
    if source_type and source_id:
        existing = db.scalar(
            select(QaQualityCost).where(
                QaQualityCost.org_id == context.org_id,
                QaQualityCost.cost_type == data["cost_type"],
                QaQualityCost.source_type == source_type,
                QaQualityCost.source_id == source_id,
                QaQualityCost.is_deleted.is_(False),
            )
        )
        if existing is not None:
            if existing.auto_generated:
                existing.amount = data["amount"]
                existing.status = "confirmed"
                existing.auto_generated = False
                existing.note = data.get("note") or existing.note
                db.flush()
                return existing
            raise AppError("该来源已存在同类型质量成本，不能重复录入", code=409)
    row = QaQualityCost(
        org_id=context.org_id,
        period=data["period"],
        cost_type=data["cost_type"],
        amount=data["amount"],
        source_type=source_type,
        source_id=source_id,
        status="confirmed",
        auto_generated=False,
        note=data.get("note"),
    )
    db.add(row)
    db.flush()
    return row


def confirm_quality_cost(db: Session, cost_id: str, payload, context: UserContext) -> QaQualityCost:
    row = db.scalar(
        select(QaQualityCost).where(
            QaQualityCost.id == cost_id,
            QaQualityCost.org_id == context.org_id,
            QaQualityCost.is_deleted.is_(False),
        )
    )
    if row is None:
        raise AppError("质量成本记录不存在", code=404)
    if payload.amount is not None:
        row.amount = payload.amount
    if payload.note:
        row.note = payload.note
    row.status = "confirmed"
    db.flush()
    return row


def record_inspection_appraisal_cost(db: Session, inspection: QaInspection, context: UserContext) -> QaQualityCost:
    sample_count = max(int(inspection.sample_size or len(inspection.results_json or []) or 1), 1)
    amount = APPRAISAL_UNIT_COST * Decimal(sample_count)
    return ensure_quality_cost(
        db,
        context,
        period=_period(),
        cost_type="appraisal",
        amount=amount,
        source_type="inspection",
        source_id=inspection.id,
        note=f"检验自动估算：{sample_count} 个样本 × {APPRAISAL_UNIT_COST}，可在质量成本台账中确认实际金额",
    )


def record_nonconformance_failure_cost(db: Session, row: QaNonconformity, context: UserContext) -> QaQualityCost:
    amount = FAILURE_COST_BY_SEVERITY.get(row.severity or "major", FAILURE_COST_BY_SEVERITY["major"])
    return ensure_quality_cost(
        db,
        context,
        period=_period(),
        cost_type="internal_failure",
        amount=amount,
        source_type="nonconformance",
        source_id=row.id,
        note=f"NCR 关闭自动估算：{row.severity or 'major'}等级，标准估算 {amount}",
    )


def record_nonconformance_prevention_cost(db: Session, row: QaNonconformity, context: UserContext) -> QaQualityCost:
    return ensure_quality_cost(
        db,
        context,
        period=_period(),
        cost_type="prevention",
        amount=PREVENTION_CAPA_COST,
        source_type="nonconformance",
        source_id=row.id,
        note=f"NCR CAPA 自动估算：标准预防成本 {PREVENTION_CAPA_COST}",
    )


def record_supplier_prevention_cost(db: Session, row: QaSupplierQuality, context: UserContext) -> QaQualityCost | None:
    if not row.capa_required:
        return None
    return ensure_quality_cost(
        db,
        context,
        period=row.period,
        cost_type="prevention",
        amount=PREVENTION_CAPA_COST,
        source_type="supplier_quality",
        source_id=row.id,
        note=f"供应商质量 CAPA 自动估算：标准预防成本 {PREVENTION_CAPA_COST}",
    )


def record_customer_claim_failure_cost(db: Session, row: QaCustomerClaim, context: UserContext) -> QaQualityCost:
    amount = row.approved_amount if row.approved_amount is not None else row.amount
    return ensure_quality_cost(
        db,
        context,
        period=_period(),
        cost_type="external_failure",
        amount=Decimal(amount or 0),
        source_type="customer_claim",
        source_id=row.id,
        note=f"客户索赔关闭自动归集：{row.claim_no}",
    )


def source_label(db: Session, row: QaQualityCost, context: UserContext) -> str:
    if row.source_type == "inspection":
        inspection = db.scalar(select(QaInspection).where(QaInspection.id == row.source_id, QaInspection.org_id == context.org_id))
        return f"检验单 · {inspection.source_type}" if inspection else f"检验单 · {row.source_id}"
    if row.source_type == "nonconformance":
        ncr = db.scalar(select(QaNonconformity).where(QaNonconformity.id == row.source_id, QaNonconformity.org_id == context.org_id))
        return f"NCR · {ncr.description[:24]}" if ncr else f"NCR · {row.source_id}"
    if row.source_type == "supplier_quality":
        quality = db.scalar(select(QaSupplierQuality).where(QaSupplierQuality.id == row.source_id, QaSupplierQuality.org_id == context.org_id))
        return f"供应商质量 · {quality.period}" if quality else f"供应商质量 · {row.source_id}"
    if row.source_type == "customer_claim":
        claim = db.scalar(select(QaCustomerClaim).where(QaCustomerClaim.id == row.source_id, QaCustomerClaim.org_id == context.org_id))
        return f"客户索赔 · {claim.claim_no}" if claim else f"客户索赔 · {row.source_id}"
    return row.source_id or "手工录入"


def serialize_quality_cost(db: Session, row: QaQualityCost, context: UserContext) -> dict:
    return {
        "id": row.id,
        "period": row.period,
        "cost_type": row.cost_type,
        "amount": str(row.amount),
        "source_type": row.source_type,
        "source_id": row.source_id,
        "source_label": source_label(db, row, context),
        "status": row.status,
        "auto_generated": row.auto_generated,
        "note": row.note,
    }
