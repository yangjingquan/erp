import re
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_now, local_today
from app.models.advanced_operations import (
    HrBenefitRecord,
    HrEmployeeLifecycle,
    HrPerformanceReview,
    HrRecruitmentCandidate,
    OcrDocument,
    QaCustomerClaim,
    QaQualityCost,
    QaSpcRecord,
    QaSupplierQuality,
    TmsShipment,
    TmsShipmentEvent,
)
from app.models.hr import HrEmployee
from app.services.auth_service import UserContext


def _serialize(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _row(row, fields):
    return {field: _serialize(getattr(row, field, None)) for field in fields} | {"id": row.id}


def _list(db, model, context):
    return db.scalars(select(model).where(model.org_id == context.org_id, model.is_deleted.is_(False)).order_by(model.created_at.desc())).all()


def _employee(db, employee_id, context):
    row = db.scalar(select(HrEmployee).where(HrEmployee.id == employee_id, HrEmployee.org_id == context.org_id, HrEmployee.is_deleted.is_(False)))
    if row is None:
        raise AppError("员工不存在", code=404)
    return row


def list_candidates(db, context):
    fields = ["candidate_no", "name", "phone", "position", "source", "status", "note"]
    return [_row(row, fields) for row in _list(db, HrRecruitmentCandidate, context)]


def create_candidate(db, payload, context):
    row = HrRecruitmentCandidate(org_id=context.org_id, candidate_no=f"CAND-{local_today():%Y%m%d}-{uuid4().hex[:8].upper()}", **payload.model_dump(), status="new")
    db.add(row); db.flush(); return row


def update_candidate(db, candidate_id, payload, context):
    row = db.scalar(select(HrRecruitmentCandidate).where(HrRecruitmentCandidate.id == candidate_id, HrRecruitmentCandidate.org_id == context.org_id, HrRecruitmentCandidate.is_deleted.is_(False)))
    if row is None: raise AppError("候选人不存在", code=404)
    row.status = payload.status; row.note = payload.note; db.flush(); return row


def list_lifecycle(db, context, employee_id=None):
    rows = _list(db, HrEmployeeLifecycle, context)
    if employee_id: rows = [row for row in rows if row.employee_id == employee_id]
    return [_row(row, ["employee_id", "event_type", "effective_date", "from_status", "to_status", "note"]) for row in rows]


def create_lifecycle(db, payload, context):
    employee = _employee(db, payload.employee_id, context)
    previous = employee.status
    row = HrEmployeeLifecycle(org_id=context.org_id, from_status=previous, **payload.model_dump())
    db.add(row)
    if payload.to_status:
        employee.status = payload.to_status
    db.flush(); return row


def list_performance(db, context, employee_id=None):
    rows = _list(db, HrPerformanceReview, context)
    if employee_id: rows = [row for row in rows if row.employee_id == employee_id]
    return [_row(row, ["employee_id", "period", "score", "rating", "goals_json", "comments", "status"]) for row in rows]


def upsert_performance(db, payload, context):
    _employee(db, payload.employee_id, context)
    row = db.scalar(select(HrPerformanceReview).where(HrPerformanceReview.org_id == context.org_id, HrPerformanceReview.employee_id == payload.employee_id, HrPerformanceReview.period == payload.period, HrPerformanceReview.is_deleted.is_(False)))
    values = {"score": payload.score, "rating": payload.rating, "goals_json": payload.goals, "comments": payload.comments, "status": "submitted"}
    if row is None:
        row = HrPerformanceReview(org_id=context.org_id, employee_id=payload.employee_id, period=payload.period, **values); db.add(row)
    else:
        for key, value in values.items(): setattr(row, key, value)
    db.flush(); return row


def list_benefits(db, context, employee_id=None):
    rows = _list(db, HrBenefitRecord, context)
    if employee_id: rows = [row for row in rows if row.employee_id == employee_id]
    return [_row(row, ["employee_id", "benefit_type", "amount", "effective_date", "status", "note"]) for row in rows]


def create_benefit(db, payload, context):
    _employee(db, payload.employee_id, context)
    row = HrBenefitRecord(org_id=context.org_id, status="active", **payload.model_dump()); db.add(row); db.flush(); return row


def list_spc(db, context, material_id=None):
    rows = _list(db, QaSpcRecord, context)
    if material_id: rows = [row for row in rows if row.material_id == material_id]
    return [_row(row, ["inspection_id", "material_id", "metric", "sample_value", "lsl", "usl", "cpk", "status"]) for row in rows]


def create_spc(db, payload, context):
    status = "in_control"
    if payload.lsl is not None and payload.sample_value < payload.lsl: status = "out_of_control"
    if payload.usl is not None and payload.sample_value > payload.usl: status = "out_of_control"
    row = QaSpcRecord(org_id=context.org_id, status=status, **payload.model_dump()); db.add(row); db.flush(); return row


def list_supplier_quality(db, context, supplier_id=None):
    rows = _list(db, QaSupplierQuality, context)
    if supplier_id: rows = [row for row in rows if row.supplier_id == supplier_id]
    return [_row(row, ["supplier_id", "period", "inspection_count", "defect_count", "defect_rate", "score", "status", "note"]) for row in rows]


def upsert_supplier_quality(db, payload, context):
    rate = (Decimal(payload.defect_count) / Decimal(payload.inspection_count)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if payload.inspection_count else Decimal("0")
    row = db.scalar(select(QaSupplierQuality).where(QaSupplierQuality.org_id == context.org_id, QaSupplierQuality.supplier_id == payload.supplier_id, QaSupplierQuality.period == payload.period, QaSupplierQuality.is_deleted.is_(False)))
    values = {"inspection_count": payload.inspection_count, "defect_count": payload.defect_count, "defect_rate": rate, "score": payload.score, "note": payload.note, "status": "submitted"}
    if row is None:
        row = QaSupplierQuality(org_id=context.org_id, supplier_id=payload.supplier_id, period=payload.period, **values); db.add(row)
    else:
        for key, value in values.items(): setattr(row, key, value)
    db.flush(); return row


def list_quality_costs(db, context, period=None):
    rows = _list(db, QaQualityCost, context)
    if period: rows = [row for row in rows if row.period == period]
    return [_row(row, ["period", "cost_type", "amount", "source_id", "note"]) for row in rows]


def create_quality_cost(db, payload, context):
    row = QaQualityCost(org_id=context.org_id, **payload.model_dump()); db.add(row); db.flush(); return row


def list_claims(db, context, status=None):
    rows = _list(db, QaCustomerClaim, context)
    if status: rows = [row for row in rows if row.status == status]
    return [_row(row, ["claim_no", "customer_id", "source_type", "source_id", "title", "amount", "status", "root_cause", "resolution", "closed_at"]) for row in rows]


def create_claim(db, payload, context):
    row = QaCustomerClaim(org_id=context.org_id, claim_no=f"CLAIM-{local_today():%Y%m%d}-{uuid4().hex[:8].upper()}", status="open", **payload.model_dump()); db.add(row); db.flush(); return row


def update_claim(db, claim_id, payload, context):
    row = db.scalar(select(QaCustomerClaim).where(QaCustomerClaim.id == claim_id, QaCustomerClaim.org_id == context.org_id, QaCustomerClaim.is_deleted.is_(False)))
    if row is None: raise AppError("客户质量索赔不存在", code=404)
    if payload.status not in {"open", "investigating", "approved", "rejected", "closed"}: raise AppError("索赔状态不合法", code=422)
    row.status = payload.status; row.root_cause = payload.root_cause; row.resolution = payload.resolution
    if payload.status == "closed": row.closed_at = local_now()
    db.flush(); return row


def list_shipments(db, context, status=None):
    rows = _list(db, TmsShipment, context)
    if status: rows = [row for row in rows if row.status == status]
    return [_row(row, ["shipment_no", "source_type", "source_id", "carrier_name", "origin", "destination", "planned_date", "actual_date", "freight_amount", "status", "note"]) | {"events": list_shipment_events(db, row.id, context)} for row in rows]


def create_shipment(db, payload, context):
    row = TmsShipment(org_id=context.org_id, shipment_no=f"SHP-{local_today():%Y%m%d}-{uuid4().hex[:8].upper()}", status="draft", **payload.model_dump()); db.add(row); db.flush(); return row


def list_shipment_events(db, shipment_id, context):
    rows = db.scalars(select(TmsShipmentEvent).where(TmsShipmentEvent.org_id == context.org_id, TmsShipmentEvent.shipment_id == shipment_id, TmsShipmentEvent.is_deleted.is_(False)).order_by(TmsShipmentEvent.event_date)).all()
    return [_row(row, ["status", "event_date", "note"]) for row in rows]


def transition_shipment(db, shipment_id, payload, context):
    row = db.scalar(select(TmsShipment).where(TmsShipment.id == shipment_id, TmsShipment.org_id == context.org_id, TmsShipment.is_deleted.is_(False)))
    if row is None: raise AppError("运输单不存在", code=404)
    allowed = {"draft": {"planned", "cancelled"}, "planned": {"dispatched", "cancelled"}, "dispatched": {"in_transit", "delivered", "exception"}, "in_transit": {"delivered", "exception"}, "exception": {"in_transit", "cancelled"}, "delivered": set(), "cancelled": set()}
    if payload.status not in allowed.get(row.status, set()): raise AppError("运输状态流转不合法", code=409)
    row.status = payload.status
    if payload.status == "delivered": row.actual_date = local_today()
    db.add(TmsShipmentEvent(org_id=context.org_id, shipment_id=row.id, status=payload.status, event_date=local_now(), note=payload.note)); db.flush(); return row


def list_ocr(db, context):
    return [_row(row, ["document_type", "source_file", "extracted_json", "confidence", "status", "error_message"]) for row in _list(db, OcrDocument, context)]


def process_ocr(db, payload, context):
    text = payload.raw_text
    extracted = {}
    patterns = {"doc_no": r"(?:单号|编号|No\.?)[：:\s]*([A-Za-z0-9-]+)", "amount": r"(?:金额|合计|总额)[：:\s]*([0-9]+(?:\.[0-9]+)?)", "date": r"(?:日期|开票日期)[：:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match: extracted[key] = match.group(1).replace("/", "-")
    confidence = Decimal("0.95") if extracted else Decimal("0.20")
    row = OcrDocument(org_id=context.org_id, extracted_json=extracted, confidence=confidence, status="completed" if extracted else "needs_review", **payload.model_dump()); db.add(row); db.flush(); return row
