from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError
from app.core.time import local_now
from app.models.business_extensions import PurchaseRequest, PurchaseRequestItem
from app.models.inventory import InvStock
from app.models.master_data import MdMaterial, MdWarehouse
from app.models.production import (
    MfgBom,
    MfgDemandLine,
    MfgPlanException,
    MfgPlanRun,
    MfgPlannedOrder,
    MfgMps,
    MfgWorkOrder,
)
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.sales import SalesOrder
from app.services.auth_service import UserContext
from app.services.configuration_service import next_doc_no


Q = Decimal("0.000001")


def q(value) -> Decimal:
    return Decimal(value or 0).quantize(Q, rounding=ROUND_HALF_UP)


def text(value) -> str:
    return f"{q(value):.6f}"


def _next_planned_document_no(db: Session, rule_key: str, org_id: str, document_date: date, prefix: str) -> str:
    """Keep plan confirmation usable in a newly initialized tenant.

    Configured numbering rules remain authoritative. The fallback is only used
    when a tenant has not configured the optional rule yet; it is unique and
    still carries the document type/date for traceability.
    """
    try:
        return next_doc_no(db, rule_key, org_id, document_date)
    except AppError as exc:
        if exc.code != 400 or "编号规则" not in exc.msg:
            raise
        return f"{prefix}-{document_date:%Y%m%d}-{uuid4().hex[:10].upper()}"


def _require_material(db: Session, material_id: str, context: UserContext) -> MdMaterial:
    row = db.scalar(select(MdMaterial).where(MdMaterial.id == material_id, MdMaterial.org_id == context.org_id, MdMaterial.is_deleted.is_(False)))
    if row is None:
        raise AppError("物料不存在或不属于当前组织", code=404)
    return row


def _require_warehouse(db: Session, warehouse_id: str | None, context: UserContext) -> None:
    if warehouse_id is None:
        return
    row = db.scalar(select(MdWarehouse).where(MdWarehouse.id == warehouse_id, MdWarehouse.org_id == context.org_id, MdWarehouse.is_deleted.is_(False)))
    if row is None:
        raise AppError("仓库不存在或不属于当前组织", code=404)


def add_demand_line(db: Session, payload, context: UserContext) -> dict:
    _require_material(db, payload.material_id, context)
    _require_warehouse(db, payload.warehouse_id, context)
    existing = db.scalar(select(MfgDemandLine).where(
        MfgDemandLine.org_id == context.org_id,
        MfgDemandLine.source_type == payload.source_type,
        MfgDemandLine.source_id == payload.source_id,
        MfgDemandLine.material_id == payload.material_id,
        MfgDemandLine.demand_date == payload.demand_date,
        MfgDemandLine.is_deleted.is_(False),
    ))
    if existing:
        existing.quantity = q(payload.quantity)
        existing.warehouse_id = payload.warehouse_id
        row = existing
    else:
        row = MfgDemandLine(
            org_id=context.org_id,
            material_id=payload.material_id,
            warehouse_id=payload.warehouse_id,
            demand_date=payload.demand_date,
            quantity=q(payload.quantity),
            source_type=payload.source_type,
            source_id=payload.source_id,
            created_by=context.id,
        )
        db.add(row)
    db.flush()
    return serialize_demand_line(row)


def serialize_demand_line(row: MfgDemandLine) -> dict:
    return {
        "id": row.id,
        "material_id": row.material_id,
        "warehouse_id": row.warehouse_id,
        "demand_date": row.demand_date.isoformat(),
        "quantity": text(row.quantity),
        "source_type": row.source_type,
        "source_id": row.source_id,
        "status": row.status,
    }


def _source_demands(db: Session, plan_from: date, plan_to: date, warehouse_id: str | None, sources: list[str], context: UserContext) -> list[dict]:
    result: list[dict] = []
    if "sales_order" in sources:
        orders = db.scalars(select(SalesOrder).options(selectinload(SalesOrder.items)).where(
            SalesOrder.org_id == context.org_id,
            SalesOrder.status.in_({"submitted", "approved"}),
            SalesOrder.expected_date.between(plan_from, plan_to),
            SalesOrder.is_deleted.is_(False),
        )).all()
        for order in orders:
            for item in order.items:
                remaining = q(item.quantity - item.delivered_quantity)
                if remaining <= 0 or (warehouse_id and item.warehouse_id != warehouse_id):
                    continue
                result.append({"material_id": item.material_id, "warehouse_id": item.warehouse_id or warehouse_id, "demand_date": order.expected_date, "quantity": remaining, "source_type": "sales_order", "source_id": order.id, "source_line_id": item.id})
    if "mps" in sources:
        rows = db.scalars(select(MfgMps).where(
            MfgMps.org_id == context.org_id,
            MfgMps.plan_date.between(plan_from, plan_to),
            MfgMps.status != "cancelled",
            MfgMps.is_deleted.is_(False),
        )).all()
        result.extend({"material_id": row.material_id, "warehouse_id": row.warehouse_id or warehouse_id, "demand_date": row.plan_date, "quantity": q(row.plan_quantity), "source_type": "mps", "source_id": row.id, "source_line_id": None} for row in rows if not warehouse_id or row.warehouse_id in {None, warehouse_id})
    manual = db.scalars(select(MfgDemandLine).where(
        MfgDemandLine.org_id == context.org_id,
        MfgDemandLine.demand_date.between(plan_from, plan_to),
        MfgDemandLine.status == "open",
        MfgDemandLine.is_deleted.is_(False),
        *([MfgDemandLine.warehouse_id == warehouse_id] if warehouse_id else []),
    )).all()
    result.extend({"material_id": row.material_id, "warehouse_id": row.warehouse_id or warehouse_id, "demand_date": row.demand_date, "quantity": q(row.quantity), "source_type": row.source_type, "source_id": row.source_id, "source_line_id": row.source_line_id} for row in manual if "manual" in sources or row.source_type in sources)
    return result


def _supply_snapshot(db: Session, material_id: str, warehouse_id: str | None, context: UserContext) -> dict:
    stock = select(func.coalesce(func.sum(InvStock.available_quantity), 0)).where(InvStock.org_id == context.org_id, InvStock.material_id == material_id)
    if warehouse_id:
        stock = stock.where(InvStock.warehouse_id == warehouse_id)
    available = q(db.scalar(stock))
    purchase = select(func.coalesce(func.sum(PurchaseOrderItem.quantity - PurchaseOrderItem.received_quantity), 0)).join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.order_id).where(PurchaseOrder.org_id == context.org_id, PurchaseOrderItem.material_id == material_id, PurchaseOrder.status.in_({"submitted", "approved"}), PurchaseOrder.is_deleted.is_(False))
    if warehouse_id:
        purchase = purchase.where(PurchaseOrderItem.warehouse_id == warehouse_id)
    in_transit = q(db.scalar(purchase))
    reserved = q(db.scalar(select(func.coalesce(func.sum(MfgWorkOrder.quantity - MfgWorkOrder.completed_quantity), 0)).where(MfgWorkOrder.org_id == context.org_id, MfgWorkOrder.material_id == material_id, MfgWorkOrder.status.in_({"released", "in_progress"}), MfgWorkOrder.is_deleted.is_(False))))
    material = db.scalar(select(MdMaterial).where(MdMaterial.id == material_id, MdMaterial.org_id == context.org_id, MdMaterial.is_deleted.is_(False)))
    safety = q(getattr(material, "min_stock", 0))
    return {"available_stock": text(available), "in_transit": text(in_transit), "reserved": text(reserved), "safety_stock": text(safety), "projected_available": text(available + in_transit - reserved), "net_requirement": text(max(safety - available - in_transit + reserved, Decimal("0")))}


def _approved_bom(db: Session, material_id: str, as_of: date, context: UserContext) -> MfgBom | None:
    return db.scalar(select(MfgBom).options(selectinload(MfgBom.items)).where(MfgBom.org_id == context.org_id, MfgBom.material_id == material_id, MfgBom.status == "approved", MfgBom.effective_from <= as_of, (MfgBom.effective_to.is_(None) | (MfgBom.effective_to >= as_of)), MfgBom.is_deleted.is_(False)).order_by(MfgBom.effective_from.desc()))


def serialize_planned_order(row: MfgPlannedOrder) -> dict:
    return {"id": row.id, "run_id": row.run_id, "order_type": row.order_type, "material_id": row.material_id, "warehouse_id": row.warehouse_id, "due_date": row.due_date.isoformat(), "quantity": text(row.quantity), "status": row.status, "source_snapshot": row.source_snapshot, "formal_document_type": row.formal_document_type, "formal_document_id": row.formal_document_id, "available_actions": ["confirm"] if row.status == "pending" else []}


def serialize_plan_exception(row: MfgPlanException) -> dict:
    return {"id": row.id, "run_id": row.run_id, "material_id": row.material_id, "exception_type": row.exception_type, "severity": row.severity, "due_date": row.due_date.isoformat() if row.due_date else None, "impact_quantity": text(row.impact_quantity), "details": row.details, "status": row.status, "owner_id": row.owner_id, "resolution": row.resolution}


def serialize_plan_run(row: MfgPlanRun, include_children: bool = True) -> dict:
    result = {"id": row.id, "run_no": row.run_no, "plan_from": row.plan_from.isoformat(), "plan_to": row.plan_to.isoformat(), "warehouse_id": row.warehouse_id, "status": row.status, "algorithm_version": row.algorithm_version, "input_snapshot": row.input_snapshot, "output_snapshot": row.output_snapshot, "created_by": row.created_by, "created_at": row.created_at.isoformat(timespec="seconds"), "available_actions": ["compare", "confirm"] if row.status == "completed" else []}
    if include_children:
        result["planned_orders"] = [serialize_planned_order(item) for item in row.planned_orders if not item.is_deleted]
        result["exceptions"] = [serialize_plan_exception(item) for item in row.exceptions if not item.is_deleted]
    return result


def run_plan(db: Session, payload, context: UserContext) -> MfgPlanRun:
    if payload.plan_to < payload.plan_from:
        raise AppError("计划结束日期不能早于开始日期", code=422)
    _require_warehouse(db, payload.warehouse_id, context)
    sources = payload.demand_sources or ["sales_order", "mps", "manual"]
    demands = _source_demands(db, payload.plan_from, payload.plan_to, payload.warehouse_id, sources, context)
    grouped: dict[tuple[str, str | None, date], Decimal] = defaultdict(lambda: Decimal("0"))
    source_map: dict[tuple[str, str | None, date], list[dict]] = defaultdict(list)
    for demand in demands:
        key = (demand["material_id"], demand["warehouse_id"], demand["demand_date"])
        grouped[key] += q(demand["quantity"])
        source_map[key].append({"source_type": demand["source_type"], "source_id": demand["source_id"], "source_line_id": demand["source_line_id"], "quantity": text(demand["quantity"])})
    run = MfgPlanRun(org_id=context.org_id, run_no=f"PLAN-{local_now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}", plan_from=payload.plan_from, plan_to=payload.plan_to, warehouse_id=payload.warehouse_id, algorithm_version="rules-v1", input_snapshot={"sources": sources, "demand_count": len(demands), "demand_lines": [{**item, "quantity": text(item["quantity"]), "demand_date": item["demand_date"].isoformat()} for item in demands]}, created_by=context.id)
    db.add(run)
    db.flush()
    total_gross = Decimal("0")
    total_net = Decimal("0")
    material_count = 0
    exception_count = 0
    for (material_id, wh_id, due_date), gross in grouped.items():
        total_gross += gross
        material_count += 1
        supply = _supply_snapshot(db, material_id, wh_id, context)
        net = q(max(gross + Decimal(supply["safety_stock"]) - Decimal(supply["available_stock"]) - Decimal(supply["in_transit"]) + Decimal(supply["reserved"]), Decimal("0")))
        total_net += net
        details = {"gross_requirement": text(gross), **supply, "demand_sources": source_map[(material_id, wh_id, due_date)]}
        if net <= 0:
            continue
        bom = _approved_bom(db, material_id, due_date, context)
        order_type = "work_order" if bom else "purchase"
        planned = MfgPlannedOrder(org_id=context.org_id, run_id=run.id, order_type=order_type, material_id=material_id, warehouse_id=wh_id, due_date=due_date, quantity=net, source_snapshot=details)
        run.planned_orders.append(planned)
        if bom and not bom.items:
            run.exceptions.append(MfgPlanException(org_id=context.org_id, run_id=run.id, material_id=material_id, exception_type="missing_bom_detail", severity="blocking", due_date=due_date, impact_quantity=net, details=details))
            exception_count += 1
    run.output_snapshot = {"material_count": material_count, "net_requirement": text(total_net), "gross_requirement": text(total_gross), "planned_order_count": len(run.planned_orders), "exception_count": exception_count, "calculated_at": local_now().isoformat(timespec="seconds")}
    db.flush()
    return run


def list_plan_runs(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(MfgPlanRun).options(selectinload(MfgPlanRun.planned_orders), selectinload(MfgPlanRun.exceptions)).where(MfgPlanRun.org_id == context.org_id, MfgPlanRun.is_deleted.is_(False)).order_by(MfgPlanRun.created_at.desc())).all()
    return [serialize_plan_run(row, include_children=False) | {"planned_order_count": len([item for item in row.planned_orders if not item.is_deleted]), "exception_count": len([item for item in row.exceptions if not item.is_deleted])} for row in rows]


def get_plan_run(db: Session, run_id: str, context: UserContext) -> MfgPlanRun:
    row = db.scalar(select(MfgPlanRun).options(selectinload(MfgPlanRun.planned_orders), selectinload(MfgPlanRun.exceptions)).where(MfgPlanRun.id == run_id, MfgPlanRun.org_id == context.org_id, MfgPlanRun.is_deleted.is_(False)))
    if row is None:
        raise AppError("计划运行批次不存在", code=404)
    return row


def confirm_planned_order(db: Session, planned_order_id: str, context: UserContext) -> dict:
    row = db.scalar(select(MfgPlannedOrder).where(MfgPlannedOrder.id == planned_order_id, MfgPlannedOrder.org_id == context.org_id, MfgPlannedOrder.is_deleted.is_(False)).with_for_update())
    if row is None:
        raise AppError("计划建议不存在", code=404)
    if row.status == "confirmed":
        return serialize_planned_order(row)
    if row.status != "pending":
        raise AppError("该计划建议当前不可确认", code=409)
    if row.order_type == "purchase":
        request = PurchaseRequest(org_id=context.org_id, doc_no=_next_planned_document_no(db, "purchase_request", context.org_id, row.due_date, "PR"), department_id=context.department_id, requester_id=context.id, status="draft", request_date=local_now().date(), remark=f"计划建议 {row.id}", created_by=context.id, created_at=local_now(), updated_at=local_now())
        request.items = [PurchaseRequestItem(material_id=row.material_id, quantity=row.quantity, line_no=1)]
        db.add(request)
        db.flush()
        row.formal_document_type = "purchase_request"
        row.formal_document_id = request.id
    else:
        from app.schemas.production import WorkOrderCreate
        from app.services.production_service import create_work_order
        if not row.warehouse_id:
            raise AppError("生产建议缺少仓库，不能转工单", code=422)
        order = create_work_order(db, WorkOrderCreate(material_id=row.material_id, warehouse_id=row.warehouse_id, quantity=row.quantity, plan_date=row.due_date, source_type="mfg_planned_order", source_id=row.id), context)
        row.formal_document_type = "work_order"
        row.formal_document_id = order.id
    row.status = "confirmed"
    row.confirmed_by = context.id
    db.flush()
    return serialize_planned_order(row)


def confirm_planned_orders(db: Session, ids: list[str], context: UserContext) -> list[dict]:
    if len(ids) != len(set(ids)):
        raise AppError("计划建议不能重复提交", code=422)
    return [confirm_planned_order(db, item, context) for item in ids]


def ignore_planned_order(db: Session, planned_order_id: str, context: UserContext) -> dict:
    row = db.scalar(select(MfgPlannedOrder).where(MfgPlannedOrder.id == planned_order_id, MfgPlannedOrder.org_id == context.org_id, MfgPlannedOrder.is_deleted.is_(False)))
    if row is None:
        raise AppError("计划建议不存在", code=404)
    if row.status == "confirmed":
        raise AppError("已转正式单据的建议不能忽略", code=409)
    row.status = "ignored"
    db.flush()
    return serialize_planned_order(row)
