from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.advanced_operations import (
    BenefitCreate, CandidateCreate, CandidateUpdate, CustomerClaimCreate, CustomerClaimUpdate,
    LifecycleCreate, OcrCreate, PerformanceCreate, QualityCostConfirm, QualityCostCreate, ShipmentCreate,
    ShipmentTransition, SpcActionComplete, SpcActionCreate, SpcCreate, SpcExceptionClose,
    SpcExceptionContainment, SpcExceptionInvestigation, SpcExceptionRootCause, SpcRetestCreate,
    SupplierQualityCreate, SupplierQualityReject, SupplierQualityReview,
)
from app.services import advanced_operations_service as service
from app.services.auth_service import UserContext

router = APIRouter(prefix="/api/advanced", tags=["advanced-operations"])


@router.get("/hr/candidates")
def candidates(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_candidates(db, context))


@router.post("/hr/candidates")
def create_candidate(payload: CandidateCreate, context: UserContext = Depends(require_permission("hr:employee:manage")), db: Session = Depends(get_db)):
    row = service.create_candidate(db, payload, context); db.commit(); return ok(service._row(row, ["candidate_no", "name", "phone", "position", "source", "status", "note"]))


@router.put("/hr/candidates/{candidate_id}")
def update_candidate(candidate_id: str, payload: CandidateUpdate, context: UserContext = Depends(require_permission("hr:employee:manage")), db: Session = Depends(get_db)):
    row = service.update_candidate(db, candidate_id, payload, context); db.commit(); return ok(service._row(row, ["candidate_no", "name", "phone", "position", "source", "status", "note"]))


@router.get("/hr/lifecycle")
def lifecycle(employee_id: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_lifecycle(db, context, employee_id))


@router.post("/hr/lifecycle")
def create_lifecycle(payload: LifecycleCreate, context: UserContext = Depends(require_permission("hr:employee:manage")), db: Session = Depends(get_db)):
    row = service.create_lifecycle(db, payload, context); db.commit(); return ok(service._row(row, ["employee_id", "event_type", "effective_date", "from_status", "to_status", "note"]))


@router.get("/hr/performance")
def performance(employee_id: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_performance(db, context, employee_id))


@router.post("/hr/performance")
def save_performance(payload: PerformanceCreate, context: UserContext = Depends(require_permission("hr:employee:manage")), db: Session = Depends(get_db)):
    row = service.upsert_performance(db, payload, context); db.commit(); return ok(service._row(row, ["employee_id", "period", "score", "rating", "goals_json", "comments", "status"]))


@router.get("/hr/benefits")
def benefits(employee_id: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_benefits(db, context, employee_id))


@router.post("/hr/benefits")
def create_benefit(payload: BenefitCreate, context: UserContext = Depends(require_permission("hr:employee:manage")), db: Session = Depends(get_db)):
    row = service.create_benefit(db, payload, context); db.commit(); return ok(service._row(row, ["employee_id", "benefit_type", "amount", "effective_date", "status", "note"]))


@router.get("/quality/spc")
def spc(material_id: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_spc(db, context, material_id))


@router.post("/quality/spc")
def create_spc(payload: SpcCreate, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.create_spc(db, payload, context); db.commit(); return ok(service.serialize_spc_record(db, row, context))


@router.get("/quality/spc/exceptions")
def spc_exceptions(status: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_spc_exceptions(db, context, status))


@router.get("/quality/spc/exceptions/{exception_id}")
def spc_exception(exception_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.get_spc_exception(db, exception_id, context))


@router.put("/quality/spc/exceptions/{exception_id}/confirm")
def confirm_spc_exception(exception_id: str, payload: SpcExceptionInvestigation, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.confirm_spc_exception(db, exception_id, payload.model_dump(), context); db.commit(); return ok(service.serialize_spc_exception(db, row, context))


@router.put("/quality/spc/exceptions/{exception_id}/containment")
def save_spc_containment(exception_id: str, payload: SpcExceptionContainment, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.save_spc_containment(db, exception_id, payload.model_dump(), context); db.commit(); return ok(service.serialize_spc_exception(db, row, context))


@router.put("/quality/spc/exceptions/{exception_id}/root-cause")
def save_spc_root_cause(exception_id: str, payload: SpcExceptionRootCause, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.save_spc_root_cause(db, exception_id, payload.model_dump(), context); db.commit(); return ok(service.serialize_spc_exception(db, row, context))


@router.post("/quality/spc/exceptions/{exception_id}/resume")
def resume_spc_exception(exception_id: str, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.resume_spc_exception(db, exception_id, context); db.commit(); return ok(service.serialize_spc_exception(db, row, context))


@router.post("/quality/spc/exceptions/{exception_id}/actions")
def create_spc_action(exception_id: str, payload: SpcActionCreate, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.create_spc_action(db, exception_id, payload.model_dump(), context); db.commit(); return ok(service._row(row, ["action_type", "description", "owner_id", "due_date", "status", "completion_evidence", "completed_at", "completed_by"]))


@router.post("/quality/spc/exceptions/{exception_id}/actions/{action_id}/complete")
def complete_spc_action(exception_id: str, action_id: str, payload: SpcActionComplete, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.complete_spc_action(db, exception_id, action_id, payload.completion_evidence, context); db.commit(); return ok(service._row(row, ["action_type", "description", "owner_id", "due_date", "status", "completion_evidence", "completed_at", "completed_by"]))


@router.post("/quality/spc/exceptions/{exception_id}/retest")
def retest_spc_exception(exception_id: str, payload: SpcRetestCreate, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.retest_spc_exception(db, exception_id, payload.model_dump(), context); db.commit(); return ok(service.serialize_spc_record(db, row, context))


@router.post("/quality/spc/exceptions/{exception_id}/close")
def close_spc_exception(exception_id: str, payload: SpcExceptionClose, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.close_spc_exception(db, exception_id, payload.closure_evidence, context); db.commit(); return ok(service.serialize_spc_exception(db, row, context))


@router.get("/quality/supplier")
def supplier_quality(supplier_id: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_supplier_quality(db, context, supplier_id))


@router.post("/quality/supplier")
def save_supplier_quality(payload: SupplierQualityCreate, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.upsert_supplier_quality(db, payload, context); db.commit(); return ok(next(item for item in service.list_supplier_quality(db, context, row.supplier_id) if item["id"] == row.id))


@router.get("/quality/supplier/{quality_id}/sources")
def supplier_quality_sources(quality_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_supplier_quality_sources(db, quality_id, context))


@router.post("/quality/supplier/{quality_id}/approve")
def approve_supplier_quality(quality_id: str, payload: SupplierQualityReview, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.review_supplier_quality(db, quality_id, "approve", payload.comment, context); db.commit(); return ok(next(item for item in service.list_supplier_quality(db, context, row.supplier_id) if item["id"] == row.id))


@router.post("/quality/supplier/{quality_id}/reject")
def reject_supplier_quality(quality_id: str, payload: SupplierQualityReject, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.review_supplier_quality(db, quality_id, "reject", payload.comment, context); db.commit(); return ok(next(item for item in service.list_supplier_quality(db, context, row.supplier_id) if item["id"] == row.id))


@router.get("/quality/cost")
def quality_cost(period: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_quality_costs(db, context, period))


@router.post("/quality/cost")
def create_quality_cost(payload: QualityCostCreate, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.create_quality_cost(db, payload, context); db.commit(); return ok(service.serialize_quality_cost(db, row, context))


@router.post("/quality/cost/{cost_id}/confirm")
def confirm_quality_cost(cost_id: str, payload: QualityCostConfirm, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.confirm_quality_cost_record(db, cost_id, payload, context); db.commit(); return ok(service.serialize_quality_cost(db, row, context))


@router.get("/quality/claims")
def claims(status: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_claims(db, context, status))


@router.get("/quality/claims/sources")
def claim_sources(source_type: str | None = None, customer_id: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_claim_sources(db, context, source_type, customer_id))


@router.post("/quality/claims")
def create_claim(payload: CustomerClaimCreate, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.create_claim(db, payload, context); db.commit(); return ok(service._serialize_claim(db, row, context))


@router.put("/quality/claims/{claim_id}")
def update_claim(claim_id: str, payload: CustomerClaimUpdate, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.update_claim(db, claim_id, payload, context); db.commit(); return ok(service._serialize_claim(db, row, context))


@router.get("/transport/shipments")
def shipments(status: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_shipments(db, context, status))


@router.post("/transport/shipments")
def create_shipment(payload: ShipmentCreate, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    row = service.create_shipment(db, payload, context); db.commit(); return ok(service._row(row, ["shipment_no", "carrier_name", "origin", "destination", "planned_date", "freight_amount", "status"]))


@router.post("/transport/shipments/{shipment_id}/transition")
def transition_shipment(shipment_id: str, payload: ShipmentTransition, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    row = service.transition_shipment(db, shipment_id, payload, context); db.commit(); return ok(service._row(row, ["shipment_no", "status", "actual_date"]))


@router.get("/ocr/documents")
def ocr_documents(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_ocr(db, context))


@router.post("/ocr/documents/process")
def process_ocr(payload: OcrCreate, context: UserContext = Depends(require_permission("config:manage")), db: Session = Depends(get_db)):
    row = service.process_ocr(db, payload, context); db.commit(); return ok(service._row(row, ["document_type", "source_file", "extracted_json", "confidence", "status", "error_message"]))
