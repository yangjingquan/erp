from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_now
from app.models.production import (
    MfgAlternateMaterial,
    MfgCapacityCalendar,
    MfgWorkCenter,
    MfgWorkOrder,
    MfgWorkOrderException,
    MfgWorkOrderSchedule,
)
from app.services.auth_service import UserContext
from app.services.production_service import _get_work_order


def _text(value: Decimal | int | None) -> str:
    return f"{Decimal(value or 0):.6f}"


def _schedule_payload(row: MfgWorkOrderSchedule) -> dict:
    return {
        "id": row.id,
        "work_order_id": row.work_order_id,
        "operation_id": row.operation_id,
        "work_center_id": row.work_center_id,
        "schedule_date": row.schedule_date.isoformat(),
        "scheduled_hours": _text(row.scheduled_hours),
        "actual_hours": _text(row.actual_hours),
        "status": row.status,
    }


def schedule_work_order(db: Session, work_order_id: str, payload, context: UserContext) -> MfgWorkOrderSchedule:
    order = _get_work_order(db, work_order_id, context)
    if order.status in {"cancelled", "completed"}:
        raise AppError("已取消或已完成的工单不能排程", code=409)
    center = db.scalar(select(MfgWorkCenter).where(MfgWorkCenter.id == payload.work_center_id, MfgWorkCenter.org_id == context.org_id, MfgWorkCenter.is_deleted.is_(False)))
    if center is None or center.status != "active":
        raise AppError("工作中心不存在或已停用", code=404)
    if payload.schedule_date < order.plan_date:
        raise AppError("排程日期不能早于工单计划日期", code=422)
    capacity = db.scalar(select(MfgCapacityCalendar.available_hours).where(MfgCapacityCalendar.org_id == context.org_id, MfgCapacityCalendar.work_center_id == center.id, MfgCapacityCalendar.capacity_date == payload.schedule_date, MfgCapacityCalendar.is_deleted.is_(False)))
    if capacity is None:
        capacity = center.daily_capacity_hours * center.efficiency_rate
    used = db.scalar(select(func.coalesce(func.sum(MfgWorkOrderSchedule.scheduled_hours), 0)).where(MfgWorkOrderSchedule.org_id == context.org_id, MfgWorkOrderSchedule.work_center_id == center.id, MfgWorkOrderSchedule.schedule_date == payload.schedule_date, MfgWorkOrderSchedule.status != "cancelled", MfgWorkOrderSchedule.is_deleted.is_(False))) or Decimal("0")
    existing = db.scalar(select(MfgWorkOrderSchedule).where(MfgWorkOrderSchedule.org_id == context.org_id, MfgWorkOrderSchedule.work_order_id == order.id, MfgWorkOrderSchedule.operation_id == payload.operation_id, MfgWorkOrderSchedule.is_deleted.is_(False)))
    if existing:
        used -= existing.scheduled_hours
    if used + payload.scheduled_hours > capacity and not payload.override_capacity:
        raise AppError(f"工作中心产能不足，剩余 {_text(capacity - used)} 小时", code=409)
    row = existing or MfgWorkOrderSchedule(org_id=context.org_id, work_order_id=order.id, operation_id=payload.operation_id, created_by=context.id)
    row.work_center_id = center.id
    row.schedule_date = payload.schedule_date
    row.scheduled_hours = payload.scheduled_hours
    row.status = "planned"
    db.add(row)
    db.flush()
    return row


def list_work_order_schedule(db: Session, context: UserContext, work_order_id: str | None = None) -> list[dict]:
    conditions = [MfgWorkOrderSchedule.org_id == context.org_id, MfgWorkOrderSchedule.is_deleted.is_(False)]
    if work_order_id:
        _get_work_order(db, work_order_id, context)
        conditions.append(MfgWorkOrderSchedule.work_order_id == work_order_id)
    return [_schedule_payload(row) for row in db.scalars(select(MfgWorkOrderSchedule).where(*conditions).order_by(MfgWorkOrderSchedule.schedule_date, MfgWorkOrderSchedule.created_at)).all()]


def add_alternate_material(db: Session, work_order_id: str, payload, context: UserContext) -> MfgAlternateMaterial:
    order = _get_work_order(db, work_order_id, context)
    if payload.material_id == payload.alternate_material_id:
        raise AppError("替代料不能与主料相同", code=422)
    required = {item.material_id for item in order.materials}
    if payload.material_id not in required:
        raise AppError("主料不是当前工单需求物料", code=422)
    row = db.scalar(select(MfgAlternateMaterial).where(MfgAlternateMaterial.org_id == context.org_id, MfgAlternateMaterial.work_order_id == order.id, MfgAlternateMaterial.material_id == payload.material_id, MfgAlternateMaterial.alternate_material_id == payload.alternate_material_id, MfgAlternateMaterial.is_deleted.is_(False)))
    if row:
        row.conversion_rate = payload.conversion_rate
        row.reason = payload.reason
    else:
        row = MfgAlternateMaterial(org_id=context.org_id, work_order_id=order.id, material_id=payload.material_id, alternate_material_id=payload.alternate_material_id, conversion_rate=payload.conversion_rate, reason=payload.reason, approved_by=context.id)
        db.add(row)
    db.flush()
    return row


def list_alternate_materials(db: Session, work_order_id: str, context: UserContext) -> list[dict]:
    _get_work_order(db, work_order_id, context)
    rows = db.scalars(select(MfgAlternateMaterial).where(MfgAlternateMaterial.org_id == context.org_id, MfgAlternateMaterial.work_order_id == work_order_id, MfgAlternateMaterial.is_deleted.is_(False)).order_by(MfgAlternateMaterial.created_at)).all()
    return [{"id": row.id, "material_id": row.material_id, "alternate_material_id": row.alternate_material_id, "conversion_rate": _text(row.conversion_rate), "status": row.status, "reason": row.reason} for row in rows]


def create_work_order_exception(db: Session, work_order_id: str, payload, context: UserContext) -> MfgWorkOrderException:
    order = _get_work_order(db, work_order_id, context)
    row = MfgWorkOrderException(org_id=context.org_id, work_order_id=order.id, exception_type=payload.exception_type, description=payload.description, reported_by=context.id)
    db.add(row)
    if order.status == "in_progress":
        order.status = "exception"
    db.flush()
    return row


def list_work_order_exceptions(db: Session, work_order_id: str, context: UserContext) -> list[dict]:
    _get_work_order(db, work_order_id, context)
    rows = db.scalars(select(MfgWorkOrderException).where(MfgWorkOrderException.org_id == context.org_id, MfgWorkOrderException.work_order_id == work_order_id, MfgWorkOrderException.is_deleted.is_(False)).order_by(MfgWorkOrderException.occurred_at.desc())).all()
    return [{"id": row.id, "exception_type": row.exception_type, "description": row.description, "status": row.status, "occurred_at": row.occurred_at.isoformat(), "resolution": row.resolution, "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None} for row in rows]


def resolve_work_order_exception(db: Session, exception_id: str, payload, context: UserContext) -> MfgWorkOrderException:
    row = db.scalar(select(MfgWorkOrderException).where(MfgWorkOrderException.id == exception_id, MfgWorkOrderException.org_id == context.org_id, MfgWorkOrderException.is_deleted.is_(False)))
    if row is None:
        raise AppError("生产异常不存在", code=404)
    if row.status != "open":
        raise AppError("生产异常已处理", code=409)
    row.status = "resolved"
    row.resolution = payload.resolution
    row.resolved_at = local_now()
    row.resolved_by = context.id
    order = _get_work_order(db, row.work_order_id, context)
    open_count = db.scalar(select(func.count(MfgWorkOrderException.id)).where(MfgWorkOrderException.work_order_id == order.id, MfgWorkOrderException.status == "open", MfgWorkOrderException.is_deleted.is_(False))) or 0
    if order.status == "exception" and open_count == 0:
        order.status = "in_progress"
    db.flush()
    return row
