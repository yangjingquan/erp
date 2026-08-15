from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.advanced_operations import (
    BenefitCreate, CandidateCreate, CandidateUpdate, CustomerClaimCreate, CustomerClaimUpdate,
    LifecycleCreate, OcrCreate, PerformanceCreate, QualityCostCreate, ShipmentCreate,
    ShipmentTransition, SpcCreate, SupplierQualityCreate,
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
    row = service.create_spc(db, payload, context); db.commit(); return ok(service._row(row, ["inspection_id", "material_id", "metric", "sample_value", "lsl", "usl", "cpk", "status"]))


@router.get("/quality/supplier")
def supplier_quality(supplier_id: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_supplier_quality(db, context, supplier_id))


@router.post("/quality/supplier")
def save_supplier_quality(payload: SupplierQualityCreate, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.upsert_supplier_quality(db, payload, context); db.commit(); return ok(service._row(row, ["supplier_id", "period", "inspection_count", "defect_count", "defect_rate", "score", "status", "note"]))


@router.get("/quality/cost")
def quality_cost(period: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_quality_costs(db, context, period))


@router.post("/quality/cost")
def create_quality_cost(payload: QualityCostCreate, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.create_quality_cost(db, payload, context); db.commit(); return ok(service._row(row, ["period", "cost_type", "amount", "source_id", "note"]))


@router.get("/quality/claims")
def claims(status: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_claims(db, context, status))


@router.post("/quality/claims")
def create_claim(payload: CustomerClaimCreate, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.create_claim(db, payload, context); db.commit(); return ok(service._row(row, ["claim_no", "customer_id", "source_type", "source_id", "title", "amount", "status"]))


@router.put("/quality/claims/{claim_id}")
def update_claim(claim_id: str, payload: CustomerClaimUpdate, context: UserContext = Depends(require_permission("quality:manage")), db: Session = Depends(get_db)):
    row = service.update_claim(db, claim_id, payload, context); db.commit(); return ok(service._row(row, ["claim_no", "customer_id", "title", "amount", "status", "root_cause", "resolution", "closed_at"]))


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
