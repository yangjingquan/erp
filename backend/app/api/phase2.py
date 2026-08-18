from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.phase2 import (
    AlertResolve, AssetCreate, AssetUpdate, AssetWorkOrderCreate, AssetWorkOrderTransition, AssetWorkOrderUpdate, ChangeRequestCreate, ChangeTransition, MaintenancePlanCreate, MilestoneCreate,
    IntercompanyCreate, InvoiceCreate, LeaveRequestCreate, LowCodeCreate, MembershipCreate, MembershipUpdate, MetricCreate, ProductRevisionCreate,
    ProjectCreate, ProjectEntryCreate, RfqCreate, RfqQuoteUpdate, ServiceCaseCreate, ServiceCaseTransition, ServiceCaseUpdate,
    ServiceContractCreate, VisitCreate, VisitUpdate, WbsCreate, RevisionTransition, SupplierScoreCreate,
)
from app.services.auth_service import UserContext
from app.services import phase2_service as service

router = APIRouter(prefix="/api/phase2", tags=["p1-p2"])


@router.get("/plm/revisions")
def revisions(keyword: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_revisions(db, context, keyword))


@router.post("/plm/revisions")
def create_revision(payload: ProductRevisionCreate, context: UserContext = Depends(require_permission("production:view")), db: Session = Depends(get_db)):
    row = service.create_revision(db, payload, context); db.commit(); return ok(service._row(row, ["material_id", "revision", "status", "effective_from", "effective_to", "change_summary", "snapshot_json"]))


@router.post("/plm/revisions/{revision_id}/transition")
def transition_revision(revision_id: str, payload: RevisionTransition, context: UserContext = Depends(require_permission("production:view")), db: Session = Depends(get_db)):
    row = service.transition_revision(db, revision_id, payload.status, context); db.commit(); return ok(service._row(row, ["material_id", "revision", "status", "effective_from", "effective_to"]))


@router.get("/plm/changes")
def changes(status: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_change_requests(db, context, status))


@router.post("/plm/changes")
def create_change(payload: ChangeRequestCreate, context: UserContext = Depends(require_permission("production:view")), db: Session = Depends(get_db)):
    row = service.create_change_request(db, payload, context); db.commit(); return ok(service._row(row, ["change_no", "title", "change_type", "description", "status", "owner_id", "due_date", "impact_snapshot"]))


@router.post("/plm/changes/{change_id}/transition")
def transition_change(change_id: str, payload: ChangeTransition, context: UserContext = Depends(require_permission("production:view")), db: Session = Depends(get_db)):
    row = service.transition_change_request(db, change_id, payload.status, context); db.commit(); return ok(service._row(row, ["change_no", "title", "status", "owner_id", "due_date"]))


@router.get("/plm/changes/{change_id}/impacts")
def change_impacts(change_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_change_impacts(db, change_id, context))


@router.post("/plm/impacts/{impact_id}/resolve")
def resolve_change_impact(impact_id: str, payload: dict, context: UserContext = Depends(require_permission("production:view")), db: Session = Depends(get_db)):
    row = service.resolve_change_impact(db, impact_id, payload.get("status", "applied"), context); db.commit(); return ok(service._row(row, ["object_type", "object_id", "impact", "status"]))


@router.get("/srm/rfqs")
def rfqs(status: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_rfqs(db, context, status))


@router.get("/srm/compare")
def compare_rfqs(material_id: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.compare_rfqs(db, context, material_id))


@router.post("/srm/rfqs")
def create_rfq(payload: RfqCreate, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    row = service.create_rfq(db, payload, context); db.commit(); return ok(service._row(row, ["rfq_no", "supplier_id", "material_id", "quantity", "due_date", "status"]))


@router.post("/srm/rfqs/{rfq_id}/quote")
def quote_rfq(rfq_id: str, payload: RfqQuoteUpdate, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    row = service.update_rfq_quote(db, rfq_id, payload, context); db.commit(); return ok(service._row(row, ["rfq_no", "quote_amount", "promised_date", "status", "supplier_note"]))


@router.post("/srm/rfqs/{rfq_id}/accept")
def accept_rfq(rfq_id: str, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    row = service.accept_rfq(db, rfq_id, context); db.commit(); return ok(service._row(row, ["rfq_no", "quote_amount", "status"]))


@router.get("/srm/scores")
def supplier_scores(supplier_id: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_supplier_scores(db, context, supplier_id))


@router.post("/srm/scores")
def create_supplier_score(payload: SupplierScoreCreate, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    row = service.upsert_supplier_score(db, payload, context); db.commit(); return ok(service._row(row, ["supplier_id", "period", "delivery_score", "quality_score", "service_score", "total_score", "evidence_json"]))


@router.get("/projects")
def projects(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_projects(db, context))


@router.post("/projects")
def create_project(payload: ProjectCreate, context: UserContext = Depends(require_permission("cost:manage")), db: Session = Depends(get_db)):
    row = service.create_project(db, payload, context); db.commit(); return ok(service._row(row, ["project_code", "name", "customer_id", "manager_id", "status", "budget_amount", "start_date", "end_date"]))


@router.post("/projects/wbs")
def create_wbs(payload: WbsCreate, context: UserContext = Depends(require_permission("cost:manage")), db: Session = Depends(get_db)):
    row = service.create_wbs(db, payload, context); db.commit(); return ok(service._row(row, ["project_id", "parent_id", "code", "name", "planned_amount", "actual_amount", "status"]))


@router.get("/projects/{project_id}/wbs")
def project_wbs(project_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_project_wbs(db, project_id, context))


@router.post("/projects/milestones")
def project_milestone(payload: MilestoneCreate, context: UserContext = Depends(require_permission("cost:manage")), db: Session = Depends(get_db)):
    row = service.create_milestone(db, payload, context); db.commit(); return ok(service._row(row, ["project_id", "wbs_id", "name", "due_date", "status"]))


@router.get("/projects/{project_id}/milestones")
def project_milestones(project_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_milestones(db, project_id, context))


@router.get("/projects/{project_id}/dashboard")
def project_dashboard(project_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.project_dashboard(db, project_id, context))


@router.post("/projects/entries")
def create_entry(payload: ProjectEntryCreate, context: UserContext = Depends(require_permission("cost:manage")), db: Session = Depends(get_db)):
    row = service.create_project_entry(db, payload, context); db.commit(); return ok(service._row(row, ["project_id", "wbs_id", "entry_date", "category", "source_type", "source_id", "amount"]))


@router.get("/projects/{project_id}/entries")
def project_entries(project_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_project_entries(db, project_id, context))


@router.get("/eam/assets")
def assets(status: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_assets(db, context, status))


@router.get("/eam/assignees")
def eam_assignees(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_assignees(db, context))


@router.post("/eam/assets")
def create_asset(payload: AssetCreate, context: UserContext = Depends(require_permission("production:view")), db: Session = Depends(get_db)):
    row = service.create_asset(db, payload, context); db.commit(); return ok(service._row(row, ["asset_code", "asset_name", "serial_no", "location", "status", "next_maintenance_date"]))


@router.put("/eam/assets/{asset_id}")
def update_asset(asset_id: str, payload: AssetUpdate, context: UserContext = Depends(require_permission("production:view")), db: Session = Depends(get_db)):
    row = service.update_asset(db, asset_id, payload, context); db.commit(); return ok(service._row(row, ["asset_code", "asset_name", "serial_no", "location", "status", "next_maintenance_date", "retired_at", "retirement_reason"]))


@router.get("/eam/work-orders")
def asset_work_orders(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_asset_work_orders(db, context))


@router.post("/eam/work-orders")
def create_asset_work_order(payload: AssetWorkOrderCreate, context: UserContext = Depends(require_permission("production:view")), db: Session = Depends(get_db)):
    row = service.create_asset_work_order(db, payload, context); db.commit(); return ok(service._row(row, ["work_order_no", "asset_id", "service_type", "description", "status", "owner_id", "due_date", "maintenance_plan_id"]))


@router.put("/eam/work-orders/{work_order_id}")
def update_asset_work_order(work_order_id: str, payload: AssetWorkOrderUpdate, context: UserContext = Depends(require_permission("production:view")), db: Session = Depends(get_db)):
    row = service.update_asset_work_order(db, work_order_id, payload, context); db.commit(); return ok(service._row(row, ["work_order_no", "status", "owner_id", "due_date", "resolution", "actual_hours", "parts_cost", "labor_cost"]))


@router.get("/eam/maintenance-plans")
def maintenance_plans(asset_id: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_maintenance_plans(db, context, asset_id))


@router.post("/eam/maintenance-plans")
def create_maintenance_plan(payload: MaintenancePlanCreate, context: UserContext = Depends(require_permission("production:view")), db: Session = Depends(get_db)):
    row = service.create_maintenance_plan(db, payload, context); db.commit(); return ok(service._row(row, ["asset_id", "name", "interval_days", "next_due", "status"]))


@router.post("/eam/maintenance-plans/{plan_id}/generate-work-order")
def generate_maintenance_work_order(plan_id: str, context: UserContext = Depends(require_permission("production:view")), db: Session = Depends(get_db)):
    row = service.generate_maintenance_work_order(db, plan_id, context); db.commit(); return ok(service._row(row, ["work_order_no", "asset_id", "service_type", "description", "status", "due_date", "maintenance_plan_id"]))


@router.post("/eam/work-orders/{work_order_id}/transition/{status}")
def transition_asset_work_order(work_order_id: str, status: str, payload: AssetWorkOrderTransition | None = None, context: UserContext = Depends(require_permission("production:view")), db: Session = Depends(get_db)):
    row = service.transition_asset_work_order(db, work_order_id, status, context, payload); db.commit(); return ok(service._row(row, ["work_order_no", "status", "resolution", "actual_hours", "parts_cost", "labor_cost", "closed_at"]))


@router.get("/service/cases")
def service_cases(status: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_service_cases(db, context, status))


@router.get("/service/contracts")
def service_contracts(customer_id: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_service_contracts(db, context, customer_id))


@router.post("/service/contracts")
def create_contract(payload: ServiceContractCreate, context: UserContext = Depends(require_permission("crm:manage")), db: Session = Depends(get_db)):
    row = service.create_service_contract(db, payload, context); db.commit(); return ok(service._row(row, ["contract_no", "customer_id", "start_date", "end_date", "value", "status"]))


@router.post("/service/cases")
def create_case(payload: ServiceCaseCreate, context: UserContext = Depends(require_permission("crm:manage")), db: Session = Depends(get_db)):
    row = service.create_service_case(db, payload, context); db.commit(); return ok(service._row(row, ["case_no", "customer_id", "contract_id", "title", "priority", "status", "owner_id", "due_date", "sla_hours"]))


@router.put("/service/cases/{case_id}")
def update_case(case_id: str, payload: ServiceCaseUpdate, context: UserContext = Depends(require_permission("crm:manage")), db: Session = Depends(get_db)):
    row = service.update_service_case(db, case_id, payload, context); db.commit(); return ok(service._row(row, ["case_no", "title", "priority", "status", "owner_id", "due_date", "resolution", "customer_feedback", "satisfaction_score"]))


@router.post("/service/cases/{case_id}/transition/{status}")
def transition_case(case_id: str, status: str, payload: ServiceCaseTransition | None = None, context: UserContext = Depends(require_permission("crm:manage")), db: Session = Depends(get_db)):
    row = service.transition_service_case(db, case_id, status, context, payload); db.commit(); return ok(service._row(row, ["case_no", "title", "priority", "status", "owner_id", "due_date", "resolution", "customer_feedback", "satisfaction_score", "closed_at"]))


@router.post("/service/visits")
def create_visit(payload: VisitCreate, context: UserContext = Depends(require_permission("crm:manage")), db: Session = Depends(get_db)):
    row = service.create_visit(db, payload, context); db.commit(); return ok(service._row(row, ["case_id", "scheduled_at", "technician_id", "status", "notes"]))


@router.get("/service/visits")
def visits(case_id: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_visits(db, context, case_id))


@router.put("/service/visits/{visit_id}")
def update_visit(visit_id: str, payload: VisitUpdate, context: UserContext = Depends(require_permission("crm:manage")), db: Session = Depends(get_db)):
    row = service.update_visit(db, visit_id, payload, context); db.commit(); return ok(service._row(row, ["case_id", "scheduled_at", "technician_id", "status", "notes", "outcome", "completed_at", "feedback_score"]))


@router.get("/crm/customers/{customer_id}/360")
def customer_360(customer_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.customer_360(db, customer_id, context))


@router.get("/compliance/tax-codes")
def tax_codes(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_tax_codes(db, context))


@router.get("/compliance/invoices")
def tax_invoices(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_tax_invoices(db, context))


@router.post("/compliance/tax-codes")
def create_tax_code(payload: dict, context: UserContext = Depends(require_permission("config:manage")), db: Session = Depends(get_db)):
    required = {"code", "name", "rate"}
    if not required.issubset(payload):
        from app.core.exceptions import AppError
        raise AppError("税码必须包含 code、name、rate", code=422)
    row = service.create_tax_code(db, payload, context); db.commit(); return ok(service._row(row, ["code", "name", "rate", "status"]))


@router.post("/compliance/invoices")
def create_invoice(payload: InvoiceCreate, context: UserContext = Depends(require_permission("finance:view")), db: Session = Depends(get_db)):
    row = service.create_invoice(db, payload, context); db.commit(); return ok(service._row(row, ["invoice_no", "invoice_type", "source_type", "source_id", "party_id", "amount", "tax_amount", "tax_code", "status"]))


@router.post("/compliance/invoices/{invoice_id}/transition/{status}")
def transition_invoice(invoice_id: str, status: str, context: UserContext = Depends(require_permission("finance:view")), db: Session = Depends(get_db)):
    row = service.transition_invoice(db, invoice_id, status, context); db.commit(); return ok(service._row(row, ["invoice_no", "status", "source_type", "source_id"]))


@router.get("/group/intercompany")
def intercompany(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_intercompany(db, context))


@router.post("/group/intercompany")
def create_intercompany(payload: IntercompanyCreate, context: UserContext = Depends(require_permission("config:manage")), db: Session = Depends(get_db)):
    row = service.create_intercompany(db, payload, context); db.commit(); return ok(service._row(row, ["transaction_no", "from_org_id", "to_org_id", "source_type", "source_id", "amount", "currency", "status"]))


@router.get("/group/members")
def group_members(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_memberships(db, context))


@router.post("/group/members")
def create_group_member(payload: MembershipCreate, context: UserContext = Depends(require_permission("config:manage")), db: Session = Depends(get_db)):
    row = service.create_membership(db, payload, context); db.commit(); return ok({"id": row.id, "user_id": row.user_id, "org_id": row.org_id, "membership_type": row.membership_type, "status": row.status})


@router.put("/group/members/{membership_id}")
def update_group_member(membership_id: str, payload: MembershipUpdate, context: UserContext = Depends(require_permission("config:manage")), db: Session = Depends(get_db)):
    row = service.update_membership(db, membership_id, payload, context); db.commit(); return ok(service.membership_row(db, row))


@router.delete("/group/members/{membership_id}")
def delete_group_member(membership_id: str, context: UserContext = Depends(require_permission("config:manage")), db: Session = Depends(get_db)):
    service.delete_membership(db, membership_id, context); db.commit(); return ok({"id": membership_id})


@router.get("/low-code/definitions")
def low_code(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_low_code(db, context))


@router.post("/low-code/definitions")
def create_low_code(payload: LowCodeCreate, context: UserContext = Depends(require_permission("config:manage")), db: Session = Depends(get_db)):
    row = service.create_low_code(db, payload, context); db.commit(); return ok(service._row(row, ["object_key", "name", "schema_json", "workflow_json", "status", "version"]))


@router.post("/low-code/definitions/{object_id}/publish")
def publish_low_code(object_id: str, context: UserContext = Depends(require_permission("config:manage")), db: Session = Depends(get_db)):
    row = service.publish_low_code(db, object_id, context); db.commit(); return ok(service._row(row, ["object_key", "name", "status", "version"]))


@router.get("/metrics")
def metrics(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_metrics(db, context))


@router.post("/metrics")
def create_metric(payload: MetricCreate, context: UserContext = Depends(require_permission("config:manage")), db: Session = Depends(get_db)):
    row = service.create_metric(db, payload, context); db.commit(); return ok(service._row(row, ["metric_key", "name", "formula", "target", "owner_id", "status"]))


@router.get("/metrics/{metric_key}/explain")
def explain_metric(metric_key: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.explain_metric(db, metric_key, context))


@router.get("/ai/alerts")
def ai_alerts(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_ai_alerts(db, context))


@router.get("/hr/leave-requests")
def leave_requests(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_leave_requests(db, context))


@router.get("/hr/attendance")
def attendance(attendance_date: date | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(service.list_attendance(db, context, attendance_date))


@router.post("/hr/leave-requests")
def create_leave(payload: LeaveRequestCreate, context: UserContext = Depends(require_permission("hr:employee:manage")), db: Session = Depends(get_db)):
    row = service.create_leave_request(db, payload, context); db.commit(); return ok(service._row(row, ["employee_id", "leave_type", "start_date", "end_date", "reason", "status"]))


@router.post("/hr/leave-requests/{leave_id}/transition/{status}")
def transition_leave(leave_id: str, status: str, context: UserContext = Depends(require_permission("hr:employee:manage")), db: Session = Depends(get_db)):
    row = service.transition_leave_request(db, leave_id, status, context); db.commit(); return ok(service._row(row, ["employee_id", "leave_type", "start_date", "end_date", "status", "approved_by"]))


@router.post("/ai/scan")
def scan_ai(context: UserContext = Depends(require_permission("config:manage")), db: Session = Depends(get_db)):
    result = service.scan_ai_alerts(db, context); db.commit(); return ok(result)


@router.post("/ai/alerts/{alert_id}/resolve")
def resolve_ai(alert_id: str, payload: AlertResolve, context: UserContext = Depends(require_permission("config:manage")), db: Session = Depends(get_db)):
    row = service.resolve_ai_alert(db, alert_id, payload.resolution, context); db.commit(); return ok(service._row(row, ["alert_key", "title", "severity", "status", "recommended_action"]))
