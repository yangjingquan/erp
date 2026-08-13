from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError
from app.models.inventory import InvStock
from app.models.production import (
    MfgBom,
    MfgCapacityCalendar,
    MfgRouting,
    MfgRoutingOperation,
    MfgWorkCenter,
    MfgWorkOrder,
)
from app.services.audit_service import write_operation_log
from app.services.auth_service import UserContext


def _decimal(value) -> Decimal:
    return Decimal(value or 0)


def _decimal_text(value) -> str:
    return f"{_decimal(value):.6f}"


def serialize_work_center(row: MfgWorkCenter) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "daily_capacity_hours": _decimal_text(row.daily_capacity_hours),
        "efficiency_rate": f"{_decimal(row.efficiency_rate):.4f}",
        "status": row.status,
    }


def serialize_capacity(row: MfgCapacityCalendar) -> dict:
    return {
        "id": row.id,
        "work_center_id": row.work_center_id,
        "capacity_date": row.capacity_date.isoformat(),
        "available_hours": _decimal_text(row.available_hours),
        "note": row.note,
    }


def serialize_routing(row: MfgRouting) -> dict:
    return {
        "id": row.id,
        "material_id": row.material_id,
        "bom_id": row.bom_id,
        "routing_version": row.routing_version,
        "effective_from": row.effective_from.isoformat() if row.effective_from else None,
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
        "status": row.status,
        "operations": [
            {
                "id": item.id,
                "work_center_id": item.work_center_id,
                "operation_name": item.operation_name,
                "line_no": item.line_no,
                "setup_hours": _decimal_text(item.setup_hours),
                "run_hours_per_unit": _decimal_text(item.run_hours_per_unit),
            }
            for item in row.operations
            if not item.is_deleted
        ],
    }


def list_work_centers(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(
        select(MfgWorkCenter)
        .where(MfgWorkCenter.org_id == context.org_id, MfgWorkCenter.is_deleted.is_(False))
        .order_by(MfgWorkCenter.code)
    ).all()
    return [serialize_work_center(row) for row in rows]


def _get_work_center(db: Session, work_center_id: str, context: UserContext) -> MfgWorkCenter:
    row = db.scalar(
        select(MfgWorkCenter).where(
            MfgWorkCenter.id == work_center_id,
            MfgWorkCenter.org_id == context.org_id,
            MfgWorkCenter.is_deleted.is_(False),
        )
    )
    if row is None:
        raise AppError("工作中心不存在", code=404)
    return row


def create_work_center(db: Session, payload, context: UserContext) -> MfgWorkCenter:
    row = MfgWorkCenter(
        org_id=context.org_id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        daily_capacity_hours=payload.daily_capacity_hours,
        efficiency_rate=payload.efficiency_rate,
        status="active",
        created_by=context.id,
        updated_by=context.id,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError as exc:
        raise AppError("工作中心编码已存在", code=409) from exc
    write_operation_log(db, user=context.user, action="create", resource="mfg_work_center", target_id=row.id)
    return row


def update_work_center(db: Session, work_center_id: str, payload, context: UserContext) -> MfgWorkCenter:
    row = _get_work_center(db, work_center_id, context)
    if payload.status == "inactive":
        used = db.scalar(
            select(MfgRoutingOperation.id)
            .join(MfgRouting, MfgRouting.id == MfgRoutingOperation.routing_id)
            .where(
                MfgRoutingOperation.work_center_id == row.id,
                MfgRoutingOperation.is_deleted.is_(False),
                MfgRouting.org_id == context.org_id,
                MfgRouting.status == "approved",
                MfgRouting.is_deleted.is_(False),
            )
            .limit(1)
        )
        if used is not None:
            raise AppError("工作中心仍被已审核工艺路线使用，不能停用", code=400)
    row.name = payload.name.strip()
    row.daily_capacity_hours = payload.daily_capacity_hours
    row.efficiency_rate = payload.efficiency_rate
    row.status = payload.status
    row.updated_by = context.id
    write_operation_log(db, user=context.user, action="update", resource="mfg_work_center", target_id=row.id)
    db.flush()
    return row


def list_capacity_calendar(
    db: Session, context: UserContext, date_from: date | None = None, date_to: date | None = None
) -> list[dict]:
    conditions = [MfgCapacityCalendar.org_id == context.org_id, MfgCapacityCalendar.is_deleted.is_(False)]
    if date_from:
        conditions.append(MfgCapacityCalendar.capacity_date >= date_from)
    if date_to:
        conditions.append(MfgCapacityCalendar.capacity_date <= date_to)
    rows = db.scalars(
        select(MfgCapacityCalendar).where(*conditions).order_by(MfgCapacityCalendar.capacity_date.desc())
    ).all()
    return [serialize_capacity(row) for row in rows]


def upsert_capacity_calendar(db: Session, payload, context: UserContext) -> MfgCapacityCalendar:
    center = _get_work_center(db, payload.work_center_id, context)
    if center.status != "active":
        raise AppError("停用的工作中心不能维护产能", code=400)
    row = db.scalar(
        select(MfgCapacityCalendar).where(
            MfgCapacityCalendar.org_id == context.org_id,
            MfgCapacityCalendar.work_center_id == center.id,
            MfgCapacityCalendar.capacity_date == payload.capacity_date,
            MfgCapacityCalendar.is_deleted.is_(False),
        )
    )
    action = "update"
    if row is None:
        action = "create"
        row = MfgCapacityCalendar(
            org_id=context.org_id,
            work_center_id=center.id,
            capacity_date=payload.capacity_date,
            created_by=context.id,
        )
        db.add(row)
    row.available_hours = payload.available_hours
    row.note = payload.note.strip() if payload.note else None
    row.updated_by = context.id
    db.flush()
    write_operation_log(db, user=context.user, action=action, resource="mfg_capacity_calendar", target_id=row.id)
    return row


def list_routings(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(
        select(MfgRouting)
        .options(selectinload(MfgRouting.operations))
        .where(MfgRouting.org_id == context.org_id, MfgRouting.is_deleted.is_(False))
        .order_by(MfgRouting.created_at.desc())
    ).all()
    return [serialize_routing(row) for row in rows]


def _get_routing(db: Session, routing_id: str, context: UserContext, *, lock: bool = False) -> MfgRouting:
    statement = (
        select(MfgRouting)
        .options(selectinload(MfgRouting.operations))
        .where(
            MfgRouting.id == routing_id,
            MfgRouting.org_id == context.org_id,
            MfgRouting.is_deleted.is_(False),
        )
    )
    if lock:
        statement = statement.with_for_update()
    row = db.scalar(statement)
    if row is None:
        raise AppError("工艺路线不存在", code=404)
    return row


def create_routing(db: Session, payload, context: UserContext) -> MfgRouting:
    if payload.effective_to and payload.effective_to < payload.effective_from:
        raise AppError("工艺路线失效日期不能早于生效日期", code=400)
    bom = db.scalar(
        select(MfgBom).where(
            MfgBom.id == payload.bom_id,
            MfgBom.org_id == context.org_id,
            MfgBom.material_id == payload.material_id,
            MfgBom.status == "approved",
            MfgBom.is_deleted.is_(False),
        )
    )
    if bom is None:
        raise AppError("工艺路线必须关联同一成品的已审核 BOM", code=400)
    center_ids = [item.work_center_id for item in payload.operations]
    if len(center_ids) != len(payload.operations):
        raise AppError("每道工序都必须指定工作中心", code=400)
    centers = db.scalars(
        select(MfgWorkCenter).where(
            MfgWorkCenter.org_id == context.org_id,
            MfgWorkCenter.id.in_(set(center_ids)),
            MfgWorkCenter.status == "active",
            MfgWorkCenter.is_deleted.is_(False),
        )
    ).all()
    if len({row.id for row in centers}) != len(set(center_ids)):
        raise AppError("工序包含不存在或已停用的工作中心", code=400)
    row = MfgRouting(
        org_id=context.org_id,
        material_id=payload.material_id,
        bom_id=bom.id,
        routing_version=payload.routing_version.strip(),
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        status="draft",
        created_by=context.id,
        updated_by=context.id,
    )
    row.operations = [
        MfgRoutingOperation(
            work_center_id=item.work_center_id,
            operation_name=item.operation_name.strip(),
            line_no=index,
            setup_hours=item.setup_hours,
            run_hours_per_unit=item.run_hours_per_unit,
        )
        for index, item in enumerate(payload.operations, start=1)
    ]
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError as exc:
        raise AppError("该 BOM 的工艺路线版本已存在", code=409) from exc
    write_operation_log(db, user=context.user, action="create", resource="mfg_routing", target_id=row.id)
    return row


def submit_routing(db: Session, routing_id: str, context: UserContext) -> MfgRouting:
    row = _get_routing(db, routing_id, context, lock=True)
    if row.status != "draft":
        raise AppError(f"工艺路线状态 {row.status} 不允许提交", code=400)
    if not [item for item in row.operations if not item.is_deleted]:
        raise AppError("工艺路线至少需要一道工序", code=400)
    row.status = "submitted"
    row.updated_by = context.id
    write_operation_log(db, user=context.user, action="submit", resource="mfg_routing", target_id=row.id)
    db.flush()
    return row


def approve_routing(db: Session, routing_id: str, context: UserContext) -> MfgRouting:
    row = _get_routing(db, routing_id, context, lock=True)
    if row.status != "submitted":
        raise AppError(f"工艺路线状态 {row.status} 不允许审核", code=400)
    if row.bom_id is None or row.effective_from is None:
        raise AppError("历史工艺路线缺少 BOM 或生效日期，不能审核", code=400)
    overlap = db.scalar(
        select(MfgRouting.id).where(
            MfgRouting.org_id == context.org_id,
            MfgRouting.bom_id == row.bom_id,
            MfgRouting.id != row.id,
            MfgRouting.status == "approved",
            MfgRouting.is_deleted.is_(False),
            or_(MfgRouting.effective_to.is_(None), MfgRouting.effective_to >= row.effective_from),
            *([] if row.effective_to is None else [MfgRouting.effective_from <= row.effective_to]),
        )
    )
    if overlap is not None:
        raise AppError("同一 BOM 已存在生效期重叠的已审核工艺路线", code=409)
    row.status = "approved"
    row.updated_by = context.id
    write_operation_log(db, user=context.user, action="approve", resource="mfg_routing", target_id=row.id)
    db.flush()
    return row


def disable_routing(db: Session, routing_id: str, context: UserContext) -> MfgRouting:
    row = _get_routing(db, routing_id, context, lock=True)
    if row.status != "approved":
        raise AppError(f"工艺路线状态 {row.status} 不允许停用", code=400)
    row.status = "disabled"
    row.updated_by = context.id
    write_operation_log(db, user=context.user, action="disable", resource="mfg_routing", target_id=row.id)
    db.flush()
    return row


def approved_routing_for_work_order(
    db: Session, context: UserContext, *, bom_id: str, material_id: str, plan_date: date, routing_id: str | None
) -> MfgRouting | None:
    if not routing_id:
        return None
    conditions = [
        MfgRouting.org_id == context.org_id,
        MfgRouting.bom_id == bom_id,
        MfgRouting.material_id == material_id,
        MfgRouting.status == "approved",
        MfgRouting.effective_from <= plan_date,
        or_(MfgRouting.effective_to.is_(None), MfgRouting.effective_to >= plan_date),
        MfgRouting.is_deleted.is_(False),
    ]
    conditions.append(MfgRouting.id == routing_id)
    row = db.scalar(select(MfgRouting).options(selectinload(MfgRouting.operations)).where(*conditions))
    if routing_id and row is None:
        raise AppError("所选工艺路线未审核、已失效或与 BOM 不匹配", code=400)
    return row


def routing_snapshot(row: MfgRouting | None) -> dict:
    if row is None:
        return {}
    return {
        "routing_id": row.id,
        "routing_version": row.routing_version,
        "operations": [
            {
                "id": item.id,
                "work_center_id": item.work_center_id,
                "operation_name": item.operation_name,
                "line_no": item.line_no,
                "setup_hours": _decimal_text(item.setup_hours),
                "run_hours_per_unit": _decimal_text(item.run_hours_per_unit),
            }
            for item in row.operations
            if not item.is_deleted
        ],
    }


def work_order_readiness(db: Session, work_order: MfgWorkOrder, context: UserContext) -> dict:
    active_orders = db.scalars(
        select(MfgWorkOrder)
        .options(selectinload(MfgWorkOrder.materials))
        .where(
            MfgWorkOrder.org_id == context.org_id,
            MfgWorkOrder.id != work_order.id,
            MfgWorkOrder.warehouse_id == work_order.warehouse_id,
            MfgWorkOrder.status.in_({"released", "in_progress"}),
            MfgWorkOrder.is_deleted.is_(False),
        )
    ).all()
    reserved_materials: dict[str, Decimal] = {}
    for other in active_orders:
        for item in other.materials:
            if item.is_deleted:
                continue
            outstanding = max(_decimal(item.required_quantity) - _decimal(item.issued_quantity) + _decimal(item.returned_quantity), Decimal(0))
            reserved_materials[item.material_id] = reserved_materials.get(item.material_id, Decimal(0)) + outstanding
    material_ids = [item.material_id for item in work_order.materials if not item.is_deleted]
    stocks = db.scalars(
        select(InvStock).where(
            InvStock.org_id == context.org_id,
            InvStock.warehouse_id == work_order.warehouse_id,
            InvStock.material_id.in_(material_ids),
        )
    ).all() if material_ids else []
    stock_map = {row.material_id: _decimal(row.available_quantity) for row in stocks}
    material_rows = []
    for item in work_order.materials:
        if item.is_deleted:
            continue
        required = max(_decimal(item.required_quantity) - _decimal(item.issued_quantity) + _decimal(item.returned_quantity), Decimal(0))
        stock = stock_map.get(item.material_id, Decimal(0))
        reserved = reserved_materials.get(item.material_id, Decimal(0))
        available = max(stock - reserved, Decimal(0))
        shortage = max(required - available, Decimal(0))
        material_rows.append({
            "material_id": item.material_id,
            "required_quantity": _decimal_text(required),
            "stock_available_quantity": _decimal_text(stock),
            "reserved_quantity": _decimal_text(reserved),
            "available_quantity": _decimal_text(available),
            "shortage_quantity": _decimal_text(shortage),
            "ready": shortage == 0,
        })

    operations = (work_order.routing_snapshot or {}).get("operations", [])
    centers = db.scalars(
        select(MfgWorkCenter).where(
            MfgWorkCenter.org_id == context.org_id,
            MfgWorkCenter.id.in_({item.get("work_center_id") for item in operations if item.get("work_center_id")}),
            MfgWorkCenter.is_deleted.is_(False),
        )
    ).all() if operations else []
    center_map = {row.id: row for row in centers}
    calendars = db.scalars(
        select(MfgCapacityCalendar).where(
            MfgCapacityCalendar.org_id == context.org_id,
            MfgCapacityCalendar.capacity_date == work_order.plan_date,
            MfgCapacityCalendar.work_center_id.in_(center_map),
            MfgCapacityCalendar.is_deleted.is_(False),
        )
    ).all() if center_map else []
    calendar_map = {row.work_center_id: _decimal(row.available_hours) for row in calendars}
    reserved_capacity: dict[str, Decimal] = {}
    other_capacity_orders = db.scalars(
        select(MfgWorkOrder).where(
            MfgWorkOrder.org_id == context.org_id,
            MfgWorkOrder.id != work_order.id,
            MfgWorkOrder.plan_date == work_order.plan_date,
            MfgWorkOrder.status.in_({"released", "in_progress"}),
            MfgWorkOrder.is_deleted.is_(False),
        )
    ).all()
    for other in other_capacity_orders:
        for operation in (other.routing_snapshot or {}).get("operations", []):
            center_id = operation.get("work_center_id")
            if not center_id:
                continue
            hours = _decimal(operation.get("setup_hours")) + _decimal(operation.get("run_hours_per_unit")) * _decimal(other.quantity)
            reserved_capacity[center_id] = reserved_capacity.get(center_id, Decimal(0)) + hours
    required_capacity: dict[str, Decimal] = {}
    for operation in operations:
        center_id = operation.get("work_center_id")
        if not center_id:
            continue
        hours = _decimal(operation.get("setup_hours")) + _decimal(operation.get("run_hours_per_unit")) * _decimal(work_order.quantity)
        required_capacity[center_id] = required_capacity.get(center_id, Decimal(0)) + hours
    capacity_rows = []
    for center_id, required in required_capacity.items():
        center = center_map.get(center_id)
        default_hours = _decimal(center.daily_capacity_hours) * _decimal(center.efficiency_rate) if center else Decimal(0)
        available_total = calendar_map.get(center_id, default_hours)
        reserved = reserved_capacity.get(center_id, Decimal(0))
        available = max(available_total - reserved, Decimal(0))
        shortage = max(required - available, Decimal(0))
        capacity_rows.append({
            "work_center_id": center_id,
            "work_center_code": center.code if center else None,
            "work_center_name": center.name if center else None,
            "required_hours": _decimal_text(required),
            "total_available_hours": _decimal_text(available_total),
            "reserved_hours": _decimal_text(reserved),
            "available_hours": _decimal_text(available),
            "shortage_hours": _decimal_text(shortage),
            "ready": shortage == 0,
        })
    material_ready = all(item["ready"] for item in material_rows)
    capacity_ready = all(item["ready"] for item in capacity_rows)
    return {
        "work_order_id": work_order.id,
        "routing_required": bool(work_order.routing_id),
        "material_ready": material_ready,
        "capacity_ready": capacity_ready,
        "ready": material_ready and capacity_ready,
        "materials": material_rows,
        "capacity": capacity_rows,
    }
