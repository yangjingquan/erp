from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_now, local_today
from app.models.advanced_operations import QaSupplierQuality
from app.models.phase2_extensions import SrmSupplierScore
from app.models.purchase import PurchaseOrder, PurchaseReceipt
from app.models.quality import QaInspection, QaNonconformity
from app.services.auth_service import UserContext


QUALITY_CAPA_SCORE_THRESHOLD = Decimal("80")
QUALITY_CAPA_DEFECT_RATE_THRESHOLD = Decimal("0.05")
PURCHASE_INSPECTION_SOURCE_TYPES = {"purchase_receipt", "purchase_order"}


def _period(value: date | None) -> str:
    return value.strftime("%Y-%m") if value else local_today().strftime("%Y-%m")


def _quantize(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _source_documents(db: Session, context: UserContext, source_ids: set[str]) -> dict[tuple[str, str], dict]:
    if not source_ids:
        return {}
    documents: dict[tuple[str, str], dict] = {}
    receipts = db.scalars(
        select(PurchaseReceipt).where(
            PurchaseReceipt.org_id == context.org_id,
            PurchaseReceipt.id.in_(source_ids),
            PurchaseReceipt.is_deleted.is_(False),
        )
    ).all()
    for row in receipts:
        documents[("purchase_receipt", row.id)] = {
            "supplier_id": row.supplier_id,
            "period": _period(row.receipt_date),
            "doc_no": row.doc_no,
            "source_type": "purchase_receipt",
            "source_id": row.id,
        }
    orders = db.scalars(
        select(PurchaseOrder).where(
            PurchaseOrder.org_id == context.org_id,
            PurchaseOrder.id.in_(source_ids),
            PurchaseOrder.is_deleted.is_(False),
        )
    ).all()
    for row in orders:
        documents[("purchase_order", row.id)] = {
            "supplier_id": row.supplier_id,
            "period": _period(row.order_date),
            "doc_no": row.doc_no,
            "source_type": "purchase_order",
            "source_id": row.id,
        }
    return documents


def _metrics(db: Session, context: UserContext, supplier_id: str, period: str) -> dict:
    inspections = db.scalars(
        select(QaInspection).where(
            QaInspection.org_id == context.org_id,
            QaInspection.inspection_type == "incoming",
            QaInspection.source_type.in_(PURCHASE_INSPECTION_SOURCE_TYPES),
            QaInspection.status.in_(("submitted", "closed")),
            QaInspection.is_deleted.is_(False),
        )
    ).all()
    documents = _source_documents(db, context, {row.source_id for row in inspections})
    scoped: list[tuple[QaInspection, dict]] = []
    for inspection in inspections:
        source = documents.get((inspection.source_type, inspection.source_id))
        if source and source["supplier_id"] == supplier_id and source["period"] == period:
            scoped.append((inspection, source))

    inspection_ids = [inspection.id for inspection, _ in scoped]
    nonconformances = db.scalars(
        select(QaNonconformity).where(
            QaNonconformity.org_id == context.org_id,
            QaNonconformity.inspection_id.in_(inspection_ids) if inspection_ids else QaNonconformity.id == "__none__",
            QaNonconformity.is_deleted.is_(False),
        )
    ).all()
    ncr_by_inspection = {row.inspection_id: row for row in nonconformances}
    severity_counts = defaultdict(int)
    for row in nonconformances:
        severity_counts[row.severity or "major"] += 1

    inspection_count = len(scoped)
    defect_count = len(nonconformances)
    defect_rate = (Decimal(defect_count) / Decimal(inspection_count)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if inspection_count else Decimal("0")
    base_score = (Decimal(inspection_count - defect_count) / Decimal(inspection_count) * Decimal("100")) if inspection_count else Decimal("0")
    severity_penalty = Decimal(severity_counts["critical"] * 10 + severity_counts["major"] * 3 + severity_counts["minor"])
    score = max(Decimal("0"), min(Decimal("100"), _quantize(base_score - severity_penalty))) if inspection_count else Decimal("0")
    open_nonconformance_count = sum(1 for row in nonconformances if row.status != "closed")
    return {
        "inspection_count": inspection_count,
        "defect_count": defect_count,
        "defect_rate": defect_rate,
        "score": score,
        "critical_count": severity_counts["critical"],
        "major_count": severity_counts["major"],
        "minor_count": severity_counts["minor"],
        "open_nonconformance_count": open_nonconformance_count,
        "sources": [
            {
                **source,
                "inspection_id": inspection.id,
                "inspection_status": inspection.status,
                "inspection_result": inspection.result,
                "nonconformance": {
                    "id": ncr_by_inspection[inspection.id].id,
                    "status": ncr_by_inspection[inspection.id].status,
                    "severity": ncr_by_inspection[inspection.id].severity,
                } if inspection.id in ncr_by_inspection else None,
            }
            for inspection, source in scoped
        ],
    }


def _capa_trigger(metrics: dict) -> tuple[bool, str | None]:
    reasons: list[str] = []
    if metrics["score"] < QUALITY_CAPA_SCORE_THRESHOLD:
        reasons.append(f"质量得分 {metrics['score']} 低于 {QUALITY_CAPA_SCORE_THRESHOLD}")
    if metrics["defect_rate"] >= QUALITY_CAPA_DEFECT_RATE_THRESHOLD:
        reasons.append(f"缺陷率 {metrics['defect_rate']:.2%} 达到 {QUALITY_CAPA_DEFECT_RATE_THRESHOLD:.0%}")
    if metrics["critical_count"]:
        reasons.append(f"存在 {metrics['critical_count']} 条严重不合格")
    return bool(reasons), "；".join(reasons) if reasons else None


def refresh_supplier_quality(db: Session, payload: dict, context: UserContext) -> tuple[QaSupplierQuality, dict]:
    supplier_id = str(payload["supplier_id"])
    period = str(payload["period"])
    metrics = _metrics(db, context, supplier_id, period)
    automatic = metrics["inspection_count"] > 0
    has_manual_counts = payload.get("inspection_count") is not None or payload.get("defect_count") is not None
    if not automatic and not has_manual_counts:
        raise AppError("本期间没有可汇总的采购检验，请先提交来料检验", code=422)
    if not automatic and has_manual_counts and (payload.get("inspection_count") is None or payload.get("defect_count") is None):
        raise AppError("手工兼容数据必须同时填写检验数和缺陷数", code=422)
    if not automatic and payload.get("inspection_count") is not None and payload.get("defect_count") is not None:
        inspection_count = int(payload["inspection_count"])
        defect_count = int(payload["defect_count"])
        defect_rate = (Decimal(defect_count) / Decimal(inspection_count)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if inspection_count else Decimal("0")
        compatibility_score = payload.get("score") if payload.get("score") is not None else (Decimal(inspection_count - defect_count) / Decimal(inspection_count) * Decimal("100") if inspection_count else Decimal("0"))
        metrics.update({
            "inspection_count": inspection_count,
            "defect_count": defect_count,
            "defect_rate": defect_rate,
            "score": max(Decimal("0"), min(Decimal("100"), _quantize(Decimal(compatibility_score)))),
        })
        metrics["sources"] = []

    row = db.scalar(
        select(QaSupplierQuality).where(
            QaSupplierQuality.org_id == context.org_id,
            QaSupplierQuality.supplier_id == supplier_id,
            QaSupplierQuality.period == period,
            QaSupplierQuality.is_deleted.is_(False),
        )
    )
    if row is None:
        row = QaSupplierQuality(org_id=context.org_id, supplier_id=supplier_id, period=period)
        db.add(row)
    row.inspection_count = metrics["inspection_count"]
    row.defect_count = metrics["defect_count"]
    row.defect_rate = metrics["defect_rate"]
    row.score = metrics["score"]
    if payload.get("note") is not None:
        row.note = payload["note"]
    row.aggregation_source = "purchase_inspection" if automatic else "manual_compatibility"
    row.source_snapshot_json = list(metrics["sources"]) if automatic else []
    row.status = "submitted"
    row.review_comment = None
    row.reviewed_by = None
    row.reviewed_at = None
    row.capa_required, row.capa_trigger_reason = _capa_trigger(metrics)
    row.capa_status = "pending" if row.capa_required else "not_required"
    db.flush()
    return row, metrics


def sync_supplier_quality_for_inspection(db: Session, inspection: QaInspection, context: UserContext) -> None:
    if inspection.inspection_type != "incoming" or inspection.source_type not in PURCHASE_INSPECTION_SOURCE_TYPES:
        return
    documents = _source_documents(db, context, {inspection.source_id})
    source = documents.get((inspection.source_type, inspection.source_id))
    if source:
        refresh_supplier_quality(db, {"supplier_id": source["supplier_id"], "period": source["period"]}, context)


def sync_supplier_quality_for_nonconformance(db: Session, nonconformance: QaNonconformity, context: UserContext) -> None:
    if not nonconformance.inspection_id:
        return
    inspection = db.get(QaInspection, nonconformance.inspection_id)
    if inspection is not None and inspection.org_id == context.org_id:
        sync_supplier_quality_for_inspection(db, inspection, context)


def ensure_supplier_quality_capa(db: Session, row: QaSupplierQuality, metrics: dict, context: UserContext) -> QaNonconformity | None:
    required, reason = _capa_trigger(metrics)
    row.capa_required = required
    row.capa_trigger_reason = reason
    if not required:
        row.capa_status = "not_required"
        db.flush()
        return None
    capa = db.scalar(
        select(QaNonconformity).where(
            QaNonconformity.org_id == context.org_id,
            QaNonconformity.supplier_quality_id == row.id,
            QaNonconformity.is_deleted.is_(False),
        ).order_by(QaNonconformity.created_at.desc())
    )
    if capa is None:
        severity = "critical" if metrics["critical_count"] else "major"
        capa = QaNonconformity(
            org_id=context.org_id,
            inspection_id=None,
            supplier_quality_id=row.id,
            supplier_id=row.supplier_id,
            supplier_period=row.period,
            description=f"供应商质量自动触发 CAPA：{reason}",
            status="open",
            severity=severity,
        )
        db.add(capa)
        db.flush()
    row.capa_nonconformance_id = capa.id
    row.capa_status = "closed" if capa.status == "closed" else capa.status
    db.flush()
    return capa


def approve_supplier_quality(db: Session, row: QaSupplierQuality, metrics: dict, context: UserContext, comment: str = "") -> QaSupplierQuality:
    if row.status != "submitted":
        raise AppError("只有待审核的供应商质量记录可以审核", code=409)
    row.status = "approved"
    row.review_comment = comment.strip() or None
    row.reviewed_by = context.id
    row.reviewed_at = local_now()
    capa = ensure_supplier_quality_capa(db, row, metrics, context)
    quality_score = Decimal(row.score or 0)
    score_row = db.scalar(select(SrmSupplierScore).where(
        SrmSupplierScore.org_id == context.org_id,
        SrmSupplierScore.supplier_id == row.supplier_id,
        SrmSupplierScore.period == row.period,
        SrmSupplierScore.is_deleted.is_(False),
    ))
    if score_row is None:
        score_row = SrmSupplierScore(org_id=context.org_id, supplier_id=row.supplier_id, period=row.period)
        db.add(score_row)
    score_row.quality_score = quality_score
    score_row.total_score = _quantize((Decimal(score_row.delivery_score or 0) + quality_score + Decimal(score_row.service_score or 0)) / Decimal("3"))
    evidence = dict(score_row.evidence_json or {})
    evidence["quality"] = {
        "supplier_quality_id": row.id,
        "inspection_count": row.inspection_count,
        "defect_count": row.defect_count,
        "defect_rate": str(row.defect_rate),
        "score": str(quality_score),
        "rule": "100 - defect_rate*100 - critical*10 - major*3 - minor*1",
    }
    score_row.evidence_json = evidence
    if capa is not None:
        row.capa_nonconformance_id = capa.id
    from app.services.quality_cost_service import record_supplier_prevention_cost
    record_supplier_prevention_cost(db, row, context)
    db.flush()
    return row


def reject_supplier_quality(row: QaSupplierQuality, context: UserContext, comment: str) -> QaSupplierQuality:
    if row.status != "submitted":
        raise AppError("只有待审核的供应商质量记录可以驳回", code=409)
    row.status = "rejected"
    row.review_comment = comment.strip()
    row.reviewed_by = context.id
    row.reviewed_at = local_now()
    return row
