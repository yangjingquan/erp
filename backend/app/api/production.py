from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.production import (
    BomCreate,
    CapacityCalendarUpsert,
    MaterialIssueCreate,
    MaterialReturnCreate,
    MpsCreate,
    RoutingCreate,
    SubcontractOrderCreate,
    SubcontractReceiptCreate,
    WorkOrderCreate,
    WorkCenterCreate,
    WorkCenterUpdate,
    WorkReportCreate,
)
from app.services.auth_service import UserContext
from app.services.planning_service import (
    _get_bom,
    _get_mrp_run,
    approve_bom,
    confirm_mrp_result,
    create_bom,
    create_mps,
    disable_bom,
    list_boms,
    list_mps,
    run_mrp,
    serialize_bom,
    serialize_mps,
    serialize_mrp_run,
    submit_bom,
)
from app.services.production_service import (
    _get_work_order,
    cancel_work_order,
    cancel_subcontract_order,
    complete_work_order,
    create_work_order,
    create_subcontract_order,
    issue_material,
    issue_subcontract_material,
    release_work_order,
    release_subcontract_order,
    receive_subcontract_order,
    report_work,
    return_material,
    serialize_issue,
    serialize_report,
    serialize_subcontract_order,
    serialize_subcontract_receipt,
    serialize_return,
    serialize_work_order,
)
from app.services.production_resource_service import (
    approve_routing,
    create_routing,
    create_work_center,
    disable_routing,
    list_capacity_calendar,
    list_routings,
    list_work_centers,
    serialize_capacity,
    serialize_routing,
    serialize_work_center,
    submit_routing,
    update_work_center,
    upsert_capacity_calendar,
    capacity_load,
    work_order_readiness,
)
from app.services.production_cost_service import get_work_order_cost
from app.models.production import MfgWorkOrder

router = APIRouter(prefix="/api/production", tags=["production"])


@router.get("/work-centers")
def list_work_centers_api(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_work_centers(db, context))


@router.post("/work-centers")
def create_work_center_api(payload: WorkCenterCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = create_work_center(db, payload, context)
    db.commit()
    return ok(serialize_work_center(row))


@router.put("/work-centers/{work_center_id}")
def update_work_center_api(work_center_id: str, payload: WorkCenterUpdate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = update_work_center(db, work_center_id, payload, context)
    db.commit()
    return ok(serialize_work_center(row))


@router.get("/capacity-calendar")
def list_capacity_calendar_api(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(list_capacity_calendar(db, context, date_from, date_to))


@router.post("/capacity-calendar")
def upsert_capacity_calendar_api(payload: CapacityCalendarUpsert, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = upsert_capacity_calendar(db, payload, context)
    db.commit()
    return ok(serialize_capacity(row))


@router.get("/capacity-load")
def capacity_load_api(date_from: date | None = Query(default=None), date_to: date | None = Query(default=None), context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(capacity_load(db, context, date_from, date_to))


@router.get("/routings")
def list_routings_api(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_routings(db, context))


@router.post("/routings")
def create_routing_api(payload: RoutingCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = create_routing(db, payload, context)
    db.commit()
    return ok(serialize_routing(row))


@router.post("/routings/{routing_id}/submit")
def submit_routing_api(routing_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = submit_routing(db, routing_id, context)
    db.commit()
    return ok(serialize_routing(row))


@router.post("/routings/{routing_id}/approve")
def approve_routing_api(routing_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = approve_routing(db, routing_id, context)
    db.commit()
    return ok(serialize_routing(row))


@router.post("/routings/{routing_id}/disable")
def disable_routing_api(routing_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = disable_routing(db, routing_id, context)
    db.commit()
    return ok(serialize_routing(row))

@router.get("/work-orders")
def list_work_orders_api(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(MfgWorkOrder).where(MfgWorkOrder.org_id == context.org_id, MfgWorkOrder.is_deleted.is_(False)).order_by(MfgWorkOrder.created_at.desc())).all()
    return ok([serialize_work_order(row) for row in rows])


@router.get("/boms")
def list_boms_api(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_boms(db, context))


@router.post("/boms")
def create_bom_api(payload: BomCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    bom = create_bom(db, payload, context)
    db.commit()
    return ok(serialize_bom(bom))


@router.get("/boms/{bom_id}")
def bom_detail(bom_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(serialize_bom(_get_bom(db, bom_id, context)))


@router.post("/boms/{bom_id}/submit")
def submit_bom_api(bom_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    bom = submit_bom(db, bom_id, context)
    db.commit()
    return ok(serialize_bom(bom))


@router.post("/boms/{bom_id}/approve")
def approve_bom_api(bom_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    bom = approve_bom(db, bom_id, context)
    db.commit()
    return ok(serialize_bom(bom))


@router.post("/boms/{bom_id}/disable")
def disable_bom_api(bom_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    bom = disable_bom(db, bom_id, context)
    db.commit()
    return ok(serialize_bom(bom))


@router.get("/mps")
def list_mps_api(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_mps(db, context))


@router.post("/mps")
def create_mps_api(payload: MpsCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    mps = create_mps(db, payload, context)
    db.commit()
    return ok(serialize_mps(mps))


@router.get("/mps/{mps_id}")
def mps_detail(mps_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = [row for row in list_mps(db, context) if row["id"] == mps_id]
    if not rows:
        from app.core.exceptions import AppError

        raise AppError("MPS 不存在", code=404)
    return ok(rows[0])


@router.post("/mps/{mps_id}/run-mrp")
def run_mrp_api(mps_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    run = run_mrp(db, mps_id, context)
    db.commit()
    return ok(serialize_mrp_run(run))


@router.get("/mrp-runs/{run_id}")
def mrp_run_detail(run_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(serialize_mrp_run(_get_mrp_run(db, run_id, context)))


@router.post("/mrp-results/{result_id}/confirm")
def confirm_mrp_result_api(result_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    confirmation = confirm_mrp_result(db, result_id, context)
    db.commit()
    return ok(confirmation)


@router.post("/work-orders")
def create_work_order_api(payload: WorkOrderCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = create_work_order(db, payload, context)
    db.commit()
    return ok(serialize_work_order(row))


@router.post("/subcontract-orders")
def create_subcontract_order_api(payload: SubcontractOrderCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = create_subcontract_order(db, payload, context)
    db.commit()
    return ok(serialize_subcontract_order(row))


@router.post("/subcontract-orders/{order_id}/release")
def release_subcontract_order_api(order_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = release_subcontract_order(db, order_id, context)
    db.commit()
    return ok(serialize_subcontract_order(row))


@router.post("/subcontract-orders/{order_id}/cancel")
def cancel_subcontract_order_api(order_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = cancel_subcontract_order(db, order_id, context)
    db.commit()
    return ok(serialize_subcontract_order(row))


@router.post("/subcontract-orders/{order_id}/issue")
def issue_subcontract_material_api(order_id: str, payload: MaterialIssueCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = issue_subcontract_material(db, order_id, payload.items, context)
    db.commit()
    return ok(serialize_issue(row))


@router.post("/subcontract-orders/{order_id}/receipts")
def receive_subcontract_order_api(order_id: str, payload: SubcontractReceiptCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = receive_subcontract_order(db, order_id, payload, context)
    db.commit()
    return ok(serialize_subcontract_receipt(row))


@router.post("/work-orders/{work_order_id}/release")
def release_work_order_api(work_order_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = release_work_order(db, work_order_id, context)
    db.commit()
    return ok(serialize_work_order(row))


@router.get("/work-orders/{work_order_id}/readiness")
def work_order_readiness_api(work_order_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(work_order_readiness(db, _get_work_order(db, work_order_id, context), context))


@router.get("/work-orders/{work_order_id}/cost")
def work_order_cost_api(work_order_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_work_order(db, work_order_id, context)
    return ok(get_work_order_cost(db, work_order_id, context))


@router.post("/work-orders/{work_order_id}/issue")
def issue_material_api(work_order_id: str, payload: MaterialIssueCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = issue_material(db, work_order_id, payload.items, context)
    db.commit()
    return ok(serialize_issue(row))


@router.post("/material-issues/{issue_id}/return")
def return_material_api(issue_id: str, payload: MaterialReturnCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = return_material(db, issue_id, payload.items, context)
    db.commit()
    return ok(serialize_return(row))


@router.post("/work-orders/{work_order_id}/reports")
def report_work_api(work_order_id: str, payload: WorkReportCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = report_work(db, work_order_id, payload, context)
    db.commit()
    return ok(serialize_report(row))


@router.post("/work-orders/{work_order_id}/complete")
def complete_work_order_api(work_order_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = complete_work_order(db, work_order_id, context)
    db.commit()
    return ok(serialize_work_order(row))


@router.post("/work-orders/{work_order_id}/cancel")
def cancel_work_order_api(work_order_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = cancel_work_order(db, work_order_id, context)
    db.commit()
    return ok(serialize_work_order(row))
