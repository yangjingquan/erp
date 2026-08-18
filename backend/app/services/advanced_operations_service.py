import re
import math
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
    QaSpcException,
    QaSupplierQuality,
    TmsShipment,
    TmsShipmentEvent,
)
from app.models.quality import QaCapaAction, QaInspection, QaNonconformity
from app.services.audit_service import write_operation_log
from app.services.quality_service import complete_capa_action, create_capa_action, close_nonconformance, _serialize_action
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
    if payload.status == "hired" and row.status != "hired":
        # 录用即入职：自动生成员工档案，避免招聘与人事重复录入。
        existing = db.scalar(select(HrEmployee).where(HrEmployee.org_id == context.org_id, HrEmployee.name == row.name, HrEmployee.is_deleted.is_(False)))
        if existing is None:
            employee_no = f"EMP-{local_now().strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"
            db.add(HrEmployee(org_id=context.org_id, employee_no=employee_no, name=row.name, department_id=context.department_id, status="active", base_salary=Decimal("0"), allowance=Decimal("0")))
            db.flush()
            row.note = row.note or f"已录用并创建员工档案 {employee_no}"
    row.status = payload.status
    if payload.note is not None:
        row.note = payload.note
    db.flush()
    return row


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


SPC_WORKFLOW_LABELS = {
    "normal": "正常监控",
    "pending_review": "待确认",
    "containment": "临时遏制",
    "root_cause": "原因分析",
    "corrective_action": "整改中",
    "retest": "待复验",
    "reopened": "复验未通过",
    "closed": "已关闭",
}


def _spc_control_status(sample_value: Decimal, lsl: Decimal | None, usl: Decimal | None) -> str:
    if lsl is not None and usl is not None and lsl >= usl:
        raise AppError("LSL 必须小于 USL", code=422)
    if lsl is not None and sample_value < lsl:
        return "out_of_control"
    if usl is not None and sample_value > usl:
        return "out_of_control"
    return "in_control"


def _calculate_cpk(db, context, material_id: str, metric: str, lsl: Decimal | None, usl: Decimal | None) -> Decimal | None:
    if lsl is None or usl is None:
        return None
    values = db.scalars(select(QaSpcRecord.sample_value).where(
        QaSpcRecord.org_id == context.org_id,
        QaSpcRecord.material_id == material_id,
        QaSpcRecord.metric == metric,
        QaSpcRecord.is_deleted.is_(False),
    )).all()
    if len(values) < 2:
        return None
    mean = sum((float(value) for value in values), 0.0) / len(values)
    sigma = math.sqrt(sum((float(value) - mean) ** 2 for value in values) / (len(values) - 1))
    if sigma <= 0:
        return None
    cpk = min((float(usl) - mean) / (3 * sigma), (mean - float(lsl)) / (3 * sigma))
    return Decimal(str(max(cpk, 0))).quantize(Decimal("0.0001"))


def _get_spc_exception(db, exception_id: str, context) -> QaSpcException:
    row = db.scalar(select(QaSpcException).where(
        QaSpcException.id == exception_id,
        QaSpcException.org_id == context.org_id,
        QaSpcException.is_deleted.is_(False),
    ))
    if row is None:
        raise AppError("SPC 异常不存在", code=404)
    return row


def _spc_actions(db, exception: QaSpcException, context) -> list[QaCapaAction]:
    if not exception.nonconformance_id:
        return []
    return db.scalars(select(QaCapaAction).where(
        QaCapaAction.org_id == context.org_id,
        QaCapaAction.nonconformance_id == exception.nonconformance_id,
        QaCapaAction.is_deleted.is_(False),
    ).order_by(QaCapaAction.created_at)).all()


def serialize_spc_record(db, row: QaSpcRecord, context) -> dict:
    exception = _get_spc_exception(db, row.exception_id, context) if row.exception_id else None
    workflow_status = exception.status if exception else ("normal" if row.status in {"in_control", "active"} else "pending_review")
    data = _row(row, ["inspection_id", "material_id", "metric", "sample_value", "lsl", "usl", "cpk", "status", "parent_record_id", "exception_id"])
    data.update({
        "control_status": row.status if row.status in {"in_control", "out_of_control"} else "in_control",
        "workflow_status": workflow_status,
        "workflow_status_label": SPC_WORKFLOW_LABELS.get(workflow_status, workflow_status),
        "exception": serialize_spc_exception(db, exception, context) if exception else None,
    })
    return data


def serialize_spc_exception(db, exception: QaSpcException, context) -> dict:
    actions = _spc_actions(db, exception, context)
    ncr = db.get(QaNonconformity, exception.nonconformance_id) if exception.nonconformance_id else None
    return {
        **_row(exception, ["spc_record_id", "nonconformance_id", "material_id", "metric", "control_status", "status", "owner_id", "due_date", "containment_action", "root_cause", "closure_evidence", "retest_record_id", "closed_at", "closed_by"]),
        "status_label": SPC_WORKFLOW_LABELS.get(exception.status, exception.status),
        "severity": ncr.severity if ncr else "major",
        "disposition": ncr.disposition if ncr else "rework",
        "actions": [_serialize_action(action) for action in actions],
    }


def list_spc(db, context, material_id=None):
    rows = _list(db, QaSpcRecord, context)
    if material_id:
        rows = [row for row in rows if row.material_id == material_id]
    return [serialize_spc_record(db, row, context) for row in rows]


def _create_spc_record(db, payload: dict, context, *, parent_record_id: str | None = None, exception: QaSpcException | None = None):
    control_status = _spc_control_status(payload["sample_value"], payload.get("lsl"), payload.get("usl"))
    cpk = payload.get("cpk") or _calculate_cpk(db, context, payload["material_id"], payload["metric"], payload.get("lsl"), payload.get("usl"))
    row = QaSpcRecord(
        org_id=context.org_id,
        status=control_status,
        cpk=cpk,
        parent_record_id=parent_record_id,
        exception_id=exception.id if exception else None,
        **{key: value for key, value in payload.items() if key in {"inspection_id", "material_id", "metric", "sample_value", "lsl", "usl"}},
    )
    db.add(row)
    db.flush()
    if control_status == "out_of_control" and exception is None:
        inspection = QaInspection(
            org_id=context.org_id,
            inspection_type="spc",
            source_type="spc_record",
            source_id=row.id,
            status="submitted",
            result="failed",
            results_json=[{"item": payload["metric"], "value": str(payload["sample_value"]), "passed": False}],
        )
        db.add(inspection)
        db.flush()
        ncr = QaNonconformity(
            org_id=context.org_id,
            inspection_id=inspection.id,
            description=f"SPC 指标“{payload['metric']}”样本超出控制界限",
            severity="major",
        )
        db.add(ncr)
        db.flush()
        exception = QaSpcException(
            org_id=context.org_id,
            spc_record_id=row.id,
            nonconformance_id=ncr.id,
            material_id=row.material_id,
            metric=row.metric,
            control_status=control_status,
            status="pending_review",
        )
        db.add(exception)
        db.flush()
        row.exception_id = exception.id
    return row


def create_spc(db, payload, context):
    return _create_spc_record(db, payload.model_dump(), context)


def list_spc_exceptions(db, context, status=None):
    rows = db.scalars(select(QaSpcException).where(
        QaSpcException.org_id == context.org_id,
        QaSpcException.is_deleted.is_(False),
    ).order_by(QaSpcException.created_at.desc())).all()
    if status:
        rows = [row for row in rows if row.status == status]
    return [serialize_spc_exception(db, row, context) for row in rows]


def get_spc_exception(db, exception_id, context):
    return serialize_spc_exception(db, _get_spc_exception(db, exception_id, context), context)


def confirm_spc_exception(db, exception_id, payload, context):
    row = _get_spc_exception(db, exception_id, context)
    if row.status not in {"pending_review"}:
        raise AppError("当前异常不在待确认阶段", code=409)
    if payload.get("severity") not in {"minor", "major", "critical"}:
        raise AppError("异常严重程度不合法", code=422)
    if payload.get("disposition") not in {"rework", "accept", "scrap", "return_to_supplier"}:
        raise AppError("异常处置结论不合法", code=422)
    from app.services.quality_service import _require_active_user
    _require_active_user(db, payload["owner_id"], context)
    if payload["due_date"] < local_today():
        raise AppError("整改期限不能早于今天", code=400)
    row.owner_id = payload["owner_id"]
    row.due_date = payload["due_date"]
    ncr = db.get(QaNonconformity, row.nonconformance_id) if row.nonconformance_id else None
    if ncr:
        ncr.severity = payload.get("severity", "major")
        ncr.disposition = payload.get("disposition", "rework")
        ncr.owner_id = row.owner_id
        ncr.due_date = row.due_date
    row.status = "containment"
    write_operation_log(db, user=context.user, action="spc_confirm", resource="qa_spc_exception", target_id=row.id, detail={"owner_id": row.owner_id})
    db.flush()
    return row


def save_spc_containment(db, exception_id, payload, context):
    row = _get_spc_exception(db, exception_id, context)
    if row.status != "containment":
        raise AppError("请先确认 SPC 异常", code=409)
    row.containment_action = payload["containment_action"]
    row.status = "root_cause"
    db.flush()
    return row


def save_spc_root_cause(db, exception_id, payload, context):
    row = _get_spc_exception(db, exception_id, context)
    if row.status != "root_cause":
        raise AppError("请先完成临时遏制", code=409)
    row.root_cause = payload["root_cause"]
    ncr = db.get(QaNonconformity, row.nonconformance_id) if row.nonconformance_id else None
    if ncr:
        ncr.root_cause = row.root_cause
        ncr.status = "investigating"
    row.status = "corrective_action"
    db.flush()
    return row


def resume_spc_exception(db, exception_id, context):
    row = _get_spc_exception(db, exception_id, context)
    if row.status != "reopened":
        raise AppError("当前异常无需重新整改", code=409)
    row.status = "corrective_action"
    db.flush()
    return row


def create_spc_action(db, exception_id, payload, context):
    row = _get_spc_exception(db, exception_id, context)
    if row.status not in {"corrective_action", "reopened"} or not row.nonconformance_id:
        raise AppError("请先完成原因分析", code=409)
    if payload.get("action_type") not in {"corrective", "preventive"}:
        raise AppError("CAPA 措施类型不合法", code=422)
    action = create_capa_action(db, row.nonconformance_id, payload, context)
    row.status = "corrective_action"
    db.flush()
    return action


def complete_spc_action(db, exception_id, action_id, evidence, context):
    row = _get_spc_exception(db, exception_id, context)
    action = complete_capa_action(db, action_id, evidence, context)
    if action.nonconformance_id != row.nonconformance_id:
        raise AppError("措施不属于当前 SPC 异常", code=409)
    db.flush()
    return action


def retest_spc_exception(db, exception_id, payload, context):
    exception = _get_spc_exception(db, exception_id, context)
    if exception.status != "corrective_action":
        raise AppError("请先完成纠正/预防措施，再进行复验", code=409)
    actions = _spc_actions(db, exception, context)
    if not {action.action_type for action in actions}.issuperset({"corrective", "preventive"}):
        raise AppError("复验前必须同时制定纠正措施和预防措施", code=409)
    if any(action.status != "completed" or not action.completion_evidence for action in actions):
        raise AppError("复验前必须完成全部 CAPA 措施并提交证据", code=409)
    source = db.get(QaSpcRecord, exception.spc_record_id)
    if source is None:
        raise AppError("SPC 原始样本不存在", code=404)
    retest = _create_spc_record(db, {
        "material_id": source.material_id,
        "metric": source.metric,
        "sample_value": payload["sample_value"],
        "lsl": source.lsl,
        "usl": source.usl,
        "inspection_id": None,
    }, context, parent_record_id=source.id, exception=exception)
    exception.retest_record_id = retest.id
    exception.status = "retest" if retest.status == "in_control" else "reopened"
    db.flush()
    return retest


def close_spc_exception(db, exception_id, closure_evidence, context):
    exception = _get_spc_exception(db, exception_id, context)
    if exception.status != "retest" or not exception.retest_record_id:
        raise AppError("只有复验通过的异常才可以关闭", code=409)
    retest = db.get(QaSpcRecord, exception.retest_record_id)
    if retest is None or retest.status != "in_control":
        raise AppError("复验样本未通过控制界限", code=409)
    if not exception.nonconformance_id:
        raise AppError("SPC 异常缺少 NCR 关联", code=409)
    close_nonconformance(db, exception.nonconformance_id, closure_evidence, context)
    exception.closure_evidence = closure_evidence
    exception.status = "closed"
    exception.closed_at = local_now()
    exception.closed_by = context.id
    db.flush()
    return exception


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
