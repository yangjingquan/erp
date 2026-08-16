from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import jwt
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.config import get_settings
from app.core.time import local_now, local_today
from app.models.configuration import CfgGlobalParameter
from app.models.inventory import InvStock, InvStockTransaction
from app.models.inventory_advanced import (
    InvBatch,
    InvCostLayer,
    InvCostLayerConsumption,
    InvReservation,
    InvTraceEvent,
    InvLocation,
    InvPickWave,
    InvSlowMovingRule,
    InvScanRecord,
    InvWarehouseAccess,
    InvWarehouseTask,
    InvZone,
)
from app.models.master_data import MdMaterial, MdWarehouse
from app.models.purchase import PurchaseReceipt
from app.models.sales import SalesDelivery
from app.models.production import MfgMaterialIssue, MfgWorkOrder
from app.models.system import SysUser
from app.services.audit_service import write_operation_log
from app.services.auth_service import UserContext
from app.services.inventory_service import post_stock_transaction


DEFAULT_SLOW_MOVING_DAYS = 90
QUANTITY_SCALE = Decimal("0.000001")
DEFAULT_SCAN_TOKEN_TTL = 900


def _decimal(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(QUANTITY_SCALE)


def _number(value: Decimal) -> str:
    return format(_decimal(value).normalize(), "f") if value else "0"


def _scan_token_ttl(db: Session, context: UserContext) -> int:
    value = db.scalar(
        select(CfgGlobalParameter.parameter_value).where(
            CfgGlobalParameter.org_id == context.org_id,
            CfgGlobalParameter.parameter_key == "scan.token.ttl",
        )
    )
    try:
        return max(0, int(value)) if value is not None else DEFAULT_SCAN_TOKEN_TTL
    except (TypeError, ValueError):
        return DEFAULT_SCAN_TOKEN_TTL


def create_scan_token(db: Session, context: UserContext) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": context.id,
        "org_id": context.org_id,
        "type": "inventory_scan",
        "warehouse_ids": sorted(context.warehouse_ids),
        "permissions": sorted(context.permissions),
        "iat": now,
        "exp": now + timedelta(seconds=_scan_token_ttl(db, context)),
    }
    settings = get_settings()
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode_scan_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise AppError("扫描令牌无效或已过期", code=401) from exc
    if payload.get("type") != "inventory_scan":
        raise AppError("扫描令牌无效", code=401)
    return payload


def process_scan(
    db: Session,
    token: str,
    scan_id: str,
    action: str,
    document_id: str,
    payload: dict,
) -> dict:
    token_payload = _decode_scan_token(token)
    user = db.get(SysUser, token_payload.get("sub"))
    if user is None or user.org_id != token_payload.get("org_id"):
        raise AppError("扫描令牌无效", code=401)
    context = UserContext(
        user=user,
        permissions=set(token_payload.get("permissions", [])),
        warehouse_ids=set(token_payload.get("warehouse_ids", [])),
    )
    if action not in {"receive", "fill", "return", "count"}:
        raise AppError("不支持的扫描操作", code=400)

    if not scan_id or len(scan_id) > 128 or not document_id:
        raise AppError("扫描请求参数无效", code=422)

    warehouse_id = payload.get("warehouse_id")
    if warehouse_id not in set(token_payload.get("warehouse_ids", [])):
        raise AppError("无权访问该仓库", code=403)
    assert_warehouse_access(context, warehouse_id)

    existing_record = db.scalar(
        select(InvScanRecord).where(
            InvScanRecord.org_id == context.org_id,
            InvScanRecord.scan_id == scan_id,
        )
    )
    if existing_record is not None:
        if not existing_record.response_json or existing_record.response_json.get("status") == "processing":
            raise AppError("扫描请求正在处理中，请稍后重试", code=409)
        return existing_record.response_json

    # Claim the scan id before changing stock. The unique key makes a retry or
    # concurrent request recover the committed original response instead of
    # replaying the business operation.
    record = InvScanRecord(
        org_id=context.org_id,
        scan_id=scan_id,
        action=action,
        document_id=document_id,
        response_json={"status": "processing", "scan_id": scan_id},
    )
    try:
        with db.begin_nested():
            db.add(record)
            db.flush()
    except IntegrityError:
        existing_record = db.scalar(
            select(InvScanRecord).where(
                InvScanRecord.org_id == context.org_id,
                InvScanRecord.scan_id == scan_id,
            )
        )
        if existing_record is None or not existing_record.response_json or existing_record.response_json.get("status") == "processing":
            raise AppError("扫描请求正在处理中，请稍后重试", code=409)
        return existing_record.response_json
    if action == "receive":
        receipt = db.scalar(
            select(PurchaseReceipt).where(
                PurchaseReceipt.id == document_id,
                PurchaseReceipt.org_id == context.org_id,
            )
        )
        if receipt is None:
            raise AppError("采购入库单不存在", code=404)
        if receipt.status != "draft":
            raise AppError("采购入库单当前不可完成", code=400)
        if receipt.warehouse_id != warehouse_id:
            raise AppError("扫描仓库与单据仓库不一致", code=403)
        if len(receipt.items) != 1:
            raise AppError("扫描入库暂仅支持单行入库单", code=400)
        item = receipt.items[0]
        material_id = payload.get("material_id")
        quantity = _decimal(payload.get("quantity", "0"))
        if material_id != item.material_id or quantity != _decimal(item.quantity):
            raise AppError("扫描数量或物料与入库单不一致", code=400)
        # Cost is authoritative on the receipt; the handheld value is only a
        # display hint and must never change accounting valuation.
        layers = post_fifo_inbound(
            db,
            source_type="scan",
            source_id=scan_id,
            warehouse_id=warehouse_id,
            location_id=payload.get("location_id"),
            material_id=material_id,
            batch_id=payload.get("batch_id"),
            quantity=quantity,
            unit_cost=_decimal(item.unit_price),
            context=context,
        )
        receipt.status = "completed"
        db.flush()
        transaction = db.get(InvStockTransaction, layers[0].inbound_transaction_id)
        result = {
            "scan_id": scan_id,
            "action": action,
            "document_id": document_id,
            "document_status": receipt.status,
            "transaction_id": transaction.id,
            "quantity": _number(transaction.quantity),
            "unit_cost": _number(transaction.unit_cost),
        }
    elif action in {"fill", "return"}:
        from types import SimpleNamespace
        from app.services.production_service import issue_material, return_material

        lines = payload.get("items") or [{"material_id": payload.get("material_id"), "quantity": payload.get("quantity")}]
        items = [SimpleNamespace(material_id=line["material_id"], quantity=_decimal(line["quantity"])) for line in lines]
        row = issue_material(db, document_id, items, context) if action == "fill" else return_material(db, document_id, items, context)
        result = {"scan_id": scan_id, "action": action, "document_id": document_id, "result_id": row.id, "status": "completed"}
    else:
        from app.services.inventory_service import complete_count, create_count

        material_id = payload.get("material_id")
        actual_quantity = payload.get("actual_quantity", payload.get("quantity"))
        count = create_count(
            db,
            context,
            warehouse_id=warehouse_id,
            items=[{"material_id": material_id, "actual_quantity": _decimal(actual_quantity)}],
        )
        count = complete_count(db, count.id, context)
        result = {"scan_id": scan_id, "action": action, "document_id": document_id, "result_id": count.id, "status": count.status}

    record.response_json = result
    db.flush()
    return result


def list_scan_tasks(db: Session, context: UserContext) -> list[dict]:
    statement = select(PurchaseReceipt).where(
        PurchaseReceipt.org_id == context.org_id,
        PurchaseReceipt.status == "draft",
    )
    allowed = allowed_warehouse_ids(context)
    if allowed is not None:
        statement = statement.where(PurchaseReceipt.warehouse_id.in_(allowed))
    receipts = db.scalars(statement.order_by(PurchaseReceipt.id)).all()
    tasks = [
        {
            "action": "receive",
            "document_id": receipt.id,
            "document_no": receipt.doc_no,
            "warehouse_id": receipt.warehouse_id,
            "status": receipt.status,
        }
        for receipt in receipts
    ]
    work_orders = db.scalars(
        select(MfgWorkOrder).where(
            MfgWorkOrder.org_id == context.org_id,
            MfgWorkOrder.status.in_({"released", "in_progress"}),
            *([MfgWorkOrder.warehouse_id.in_(allowed)] if allowed is not None else []),
        ).order_by(MfgWorkOrder.id)
    ).all()
    tasks.extend({
        "action": "fill", "document_id": row.id, "document_no": row.doc_no,
        "warehouse_id": row.warehouse_id, "status": row.status,
    } for row in work_orders)
    issues = db.scalars(
        select(MfgMaterialIssue).where(
            MfgMaterialIssue.org_id == context.org_id,
            *([MfgMaterialIssue.warehouse_id.in_(allowed)] if allowed is not None else []),
        ).order_by(MfgMaterialIssue.id)
    ).all()
    tasks.extend({
        "action": "return", "document_id": row.id, "document_no": f"ISSUE-{row.id[:8]}",
        "warehouse_id": row.warehouse_id, "status": "open",
    } for row in issues)
    if allowed is None:
        warehouse_ids = db.scalars(select(MdWarehouse.id).where(MdWarehouse.org_id == context.org_id, MdWarehouse.is_deleted.is_(False))).all()
    else:
        warehouse_ids = sorted(allowed)
    tasks.extend({
        "action": "count", "document_id": warehouse_id, "document_no": f"COUNT-{warehouse_id[:8]}",
        "warehouse_id": warehouse_id, "status": "open",
    } for warehouse_id in warehouse_ids)
    return tasks


def _serialize_warehouse_task(row: InvWarehouseTask) -> dict:
    return {
        "id": row.id,
        "task_no": row.task_no,
        "task_type": row.task_type,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "warehouse_id": row.warehouse_id,
        "location_id": row.location_id,
        "material_id": row.material_id,
        "batch_id": row.batch_id,
        "planned_quantity": _number(row.planned_quantity),
        "completed_quantity": _number(row.completed_quantity),
        "assigned_to": row.assigned_to,
        "wave_id": row.wave_id,
        "status": row.status,
        "priority": row.priority,
        "exception_reason": row.exception_reason,
        "serial_numbers": row.serial_numbers_json or [],
        "serial_tracking": row.serial_tracking,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


def _serialize_pick_wave(row: InvPickWave, task_count: int = 0) -> dict:
    return {
        "id": row.id,
        "wave_no": row.wave_no,
        "warehouse_id": row.warehouse_id,
        "status": row.status,
        "priority": row.priority,
        "assigned_to": row.assigned_to,
        "task_count": task_count,
        "released_at": row.released_at.isoformat() if row.released_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


def create_warehouse_task(db: Session, payload, context: UserContext) -> InvWarehouseTask:
    _require_warehouse(db, payload.warehouse_id, context)
    if payload.location_id:
        _require_location(db, payload.location_id, payload.warehouse_id, context)
    if payload.material_id:
        _require_material(db, payload.material_id, context)
        _require_batch(db, payload.batch_id, payload.material_id, context)
    row = InvWarehouseTask(
        org_id=context.org_id,
        task_no=f"WT-{local_now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8].upper()}",
        task_type=payload.task_type,
        source_type=payload.source_type,
        source_id=payload.source_id,
        warehouse_id=payload.warehouse_id,
        location_id=payload.location_id,
        material_id=payload.material_id,
        batch_id=payload.batch_id,
        planned_quantity=payload.planned_quantity,
        priority=payload.priority,
        status="ready",
        serial_tracking=payload.serial_tracking,
    )
    db.add(row)
    db.flush()
    write_operation_log(db, user=context.user, action="create", resource="inv_warehouse_task", target_id=row.id)
    return row


def _find_source_document(db: Session, model, source_id: str, org_id: str, *, exclude_deleted: bool = False):
    """Find a source document by internal ID first, then by business document number."""
    lookup = source_id.strip()
    filters = [model.org_id == org_id]
    if exclude_deleted:
        filters.append(model.is_deleted.is_(False))

    document = db.scalar(select(model).where(model.id == lookup, *filters))
    if document is None and hasattr(model, "doc_no"):
        document = db.scalar(select(model).where(model.doc_no == lookup, *filters))
    return document


def generate_warehouse_tasks(db: Session, source_type: str, source_id: str, context: UserContext, serial_tracking: bool = False) -> list[dict]:
    """Generate idempotent warehouse tasks from a business document."""
    candidates: list[dict] = []
    if source_type == "purchase_receipt":
        document = _find_source_document(db, PurchaseReceipt, source_id, context.org_id)
        if document is None:
            raise AppError("采购入库单不存在", code=404)
        source_document_id = document.id
        for item in document.items:
            candidates.append({"task_type": "putaway", "warehouse_id": document.warehouse_id, "material_id": item.material_id, "planned_quantity": item.quantity, "source_type": source_type, "source_id": source_document_id, "serial_tracking": serial_tracking})
    elif source_type == "sales_delivery":
        document = _find_source_document(db, SalesDelivery, source_id, context.org_id)
        if document is None:
            raise AppError("销售出库单不存在", code=404)
        source_document_id = document.id
        for item in document.items:
            candidates.append({"task_type": "pick", "warehouse_id": document.warehouse_id, "material_id": item.material_id, "planned_quantity": item.quantity, "source_type": source_type, "source_id": source_document_id, "serial_tracking": serial_tracking})
    elif source_type == "work_order":
        document = _find_source_document(db, MfgWorkOrder, source_id, context.org_id, exclude_deleted=True)
        if document is None:
            raise AppError("生产工单不存在", code=404)
        source_document_id = document.id
        for item in document.materials:
            candidates.append({"task_type": "pick", "warehouse_id": document.warehouse_id, "material_id": item.material_id, "planned_quantity": item.required_quantity, "source_type": source_type, "source_id": source_document_id, "serial_tracking": serial_tracking})
    elif source_type == "material_issue":
        document = db.scalar(select(MfgMaterialIssue).where(MfgMaterialIssue.id == source_id, MfgMaterialIssue.org_id == context.org_id, MfgMaterialIssue.is_deleted.is_(False)))
        if document is None:
            raise AppError("生产领料单不存在", code=404)
        source_document_id = document.id
        for item in document.items:
            candidates.append({"task_type": "pick", "warehouse_id": document.warehouse_id, "material_id": item.material_id, "planned_quantity": item.quantity, "source_type": source_type, "source_id": source_document_id, "serial_tracking": serial_tracking})
    else:
        raise AppError("不支持自动生成任务的来源单据", code=422)
    result = []
    for candidate in candidates:
        existing = db.scalar(select(InvWarehouseTask).where(InvWarehouseTask.org_id == context.org_id, InvWarehouseTask.source_type == source_type, InvWarehouseTask.source_id == source_id, InvWarehouseTask.task_type == candidate["task_type"], InvWarehouseTask.material_id == candidate["material_id"], InvWarehouseTask.is_deleted.is_(False)))
        if existing is not None:
            result.append(_serialize_warehouse_task(existing))
            continue
        row = InvWarehouseTask(org_id=context.org_id, task_no=f"WT-{local_now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8].upper()}", status="ready", priority=50, **candidate)
        db.add(row)
        db.flush()
        result.append(_serialize_warehouse_task(row))
    return result


def list_warehouse_tasks(
    db: Session,
    context: UserContext,
    *,
    status: str | None = None,
    task_type: str | None = None,
    warehouse_id: str | None = None,
    source_type: str | None = None,
) -> list[dict]:
    conditions = [InvWarehouseTask.org_id == context.org_id, InvWarehouseTask.is_deleted.is_(False)]
    allowed = allowed_warehouse_ids(context)
    if allowed is not None:
        conditions.append(InvWarehouseTask.warehouse_id.in_(allowed))
    if warehouse_id:
        _require_warehouse(db, warehouse_id, context)
        conditions.append(InvWarehouseTask.warehouse_id == warehouse_id)
    if status:
        conditions.append(InvWarehouseTask.status == status)
    if task_type:
        conditions.append(InvWarehouseTask.task_type == task_type)
    if source_type:
        conditions.append(InvWarehouseTask.source_type == source_type)
    rows = db.scalars(
        select(InvWarehouseTask).where(*conditions).order_by(InvWarehouseTask.created_at.desc())
    ).all()
    return [_serialize_warehouse_task(row) for row in rows]


def transition_warehouse_task(db: Session, task_id: str, payload, context: UserContext) -> InvWarehouseTask:
    row = db.scalar(
        select(InvWarehouseTask).where(
            InvWarehouseTask.id == task_id,
            InvWarehouseTask.org_id == context.org_id,
            InvWarehouseTask.is_deleted.is_(False),
        )
    )
    if row is None:
        raise AppError("仓库作业任务不存在", code=404)
    assert_warehouse_access(context, row.warehouse_id)
    allowed_transitions = {
        "ready": {"assigned", "in_progress", "cancelled"},
        "assigned": {"in_progress", "exception", "cancelled"},
        "in_progress": {"completed", "exception", "cancelled"},
        "exception": {"in_progress", "cancelled"},
    }
    if payload.status not in allowed_transitions.get(row.status, set()):
        raise AppError(f"任务不能从 {row.status} 变更为 {payload.status}", code=409)
    if payload.status == "assigned" and not (payload.assigned_to or row.assigned_to):
        raise AppError("分配任务必须指定执行人", code=422)
    if payload.status == "exception" and not payload.exception_reason:
        raise AppError("异常任务必须填写异常原因", code=422)
    if payload.completed_quantity is not None:
        if payload.completed_quantity > row.planned_quantity and row.planned_quantity > 0:
            raise AppError("完成数量不能超过计划数量", code=422)
        row.completed_quantity = payload.completed_quantity
    if row.serial_tracking and payload.status == "completed" and row.planned_quantity > 0 and len(payload.serial_numbers) < int(row.planned_quantity):
        raise AppError("序列号数量不能少于计划数量", code=422)
    if payload.serial_numbers:
        if len(payload.serial_numbers) != len(set(payload.serial_numbers)):
            raise AppError("序列号不能重复", code=422)
        if row.planned_quantity > 0 and len(payload.serial_numbers) < int(row.planned_quantity):
            raise AppError("序列号数量不能少于计划数量", code=422)
        row.serial_numbers_json = payload.serial_numbers
    if payload.assigned_to:
        row.assigned_to = payload.assigned_to
    row.status = payload.status
    row.exception_reason = payload.exception_reason if payload.status == "exception" else None
    if payload.status == "completed":
        row.completed_at = local_now()
        row.completed_by = context.id
        if row.planned_quantity > 0 and row.completed_quantity == 0:
            row.completed_quantity = row.planned_quantity
    row.version += 1
    db.flush()
    if row.wave_id and row.status == "completed":
        _refresh_pick_wave_status(db, row.wave_id, context.org_id)
    if row.status == "completed" and row.task_type in {"pick", "pack"}:
        next_type = "pack" if row.task_type == "pick" else "check"
        existing = db.scalar(select(InvWarehouseTask).where(InvWarehouseTask.org_id == row.org_id, InvWarehouseTask.source_type == row.source_type, InvWarehouseTask.source_id == row.source_id, InvWarehouseTask.task_type == next_type, InvWarehouseTask.material_id == row.material_id, InvWarehouseTask.is_deleted.is_(False)))
        if existing is None:
            db.add(InvWarehouseTask(org_id=row.org_id, task_no=f"WT-{local_now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8].upper()}", task_type=next_type, source_type=row.source_type, source_id=row.source_id, warehouse_id=row.warehouse_id, location_id=row.location_id, material_id=row.material_id, batch_id=row.batch_id, planned_quantity=row.completed_quantity or row.planned_quantity, priority=row.priority, status="ready", serial_numbers_json=row.serial_numbers_json or [], serial_tracking=row.serial_tracking))
    if row.status == "completed" and row.task_type == "check" and row.source_type == "sales_delivery" and row.source_id:
        delivery = db.scalar(select(SalesDelivery).where(SalesDelivery.id == row.source_id, SalesDelivery.org_id == row.org_id))
        if delivery is not None:
            check_statuses = db.scalars(select(InvWarehouseTask.status).where(InvWarehouseTask.source_type == row.source_type, InvWarehouseTask.source_id == row.source_id, InvWarehouseTask.task_type == "check", InvWarehouseTask.is_deleted.is_(False))).all()
            if check_statuses and all(status == "completed" for status in check_statuses):
                # Unify WMS completion semantics with the document workbench:
                # completing the check task must also post the stock-out and
                # create the receivable (and its accounting voucher).
                from app.services.inventory_service import complete_sales_delivery
                from app.services.finance_service import create_receivable_from_sales_delivery
                if delivery.status == "draft":
                    complete_sales_delivery(db, delivery.id, context)
                    create_receivable_from_sales_delivery(db, delivery.id, context)
    db.flush()
    write_operation_log(db, user=context.user, action="transition", resource="inv_warehouse_task", target_id=row.id)
    return row


def create_pick_wave(db: Session, payload, context: UserContext) -> InvPickWave:
    _require_warehouse(db, payload.warehouse_id, context)
    tasks = db.scalars(
        select(InvWarehouseTask).where(
            InvWarehouseTask.org_id == context.org_id,
            InvWarehouseTask.id.in_(payload.task_ids),
            InvWarehouseTask.warehouse_id == payload.warehouse_id,
            InvWarehouseTask.task_type == "pick",
            InvWarehouseTask.status.in_({"ready", "assigned"}),
            InvWarehouseTask.is_deleted.is_(False),
        )
    ).all()
    if len(tasks) != len(set(payload.task_ids)):
        raise AppError("波次只能包含当前仓库中可拣货的任务", code=409)
    row = InvPickWave(
        org_id=context.org_id,
        wave_no=f"PW-{local_now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8].upper()}",
        warehouse_id=payload.warehouse_id,
        priority=payload.priority,
        status="draft",
    )
    db.add(row)
    db.flush()
    for task in tasks:
        task.wave_id = row.id
        task.status = "assigned"
    db.flush()
    return row


def list_pick_waves(db: Session, context: UserContext, status: str | None = None) -> list[dict]:
    conditions = [InvPickWave.org_id == context.org_id, InvPickWave.is_deleted.is_(False)]
    allowed = allowed_warehouse_ids(context)
    if allowed is not None:
        conditions.append(InvPickWave.warehouse_id.in_(allowed))
    if status:
        conditions.append(InvPickWave.status == status)
    rows = db.scalars(select(InvPickWave).where(*conditions).order_by(InvPickWave.created_at.desc())).all()
    return [_serialize_pick_wave(row, db.scalar(select(func.count(InvWarehouseTask.id)).where(InvWarehouseTask.wave_id == row.id, InvWarehouseTask.is_deleted.is_(False))) or 0) for row in rows]


def release_pick_wave(db: Session, wave_id: str, context: UserContext) -> InvPickWave:
    row = db.scalar(select(InvPickWave).where(InvPickWave.id == wave_id, InvPickWave.org_id == context.org_id, InvPickWave.is_deleted.is_(False)))
    if row is None:
        raise AppError("拣货波次不存在", code=404)
    assert_warehouse_access(context, row.warehouse_id)
    if row.status != "draft":
        raise AppError("只有草稿波次可以发布", code=409)
    row.status = "released"
    row.released_at = local_now()
    db.flush()
    return row


def _refresh_pick_wave_status(db: Session, wave_id: str, org_id: str) -> None:
    wave = db.scalar(select(InvPickWave).where(InvPickWave.id == wave_id, InvPickWave.org_id == org_id))
    if wave is None:
        return
    statuses = db.scalars(select(InvWarehouseTask.status).where(InvWarehouseTask.wave_id == wave.id, InvWarehouseTask.is_deleted.is_(False))).all()
    if statuses and all(status == "completed" for status in statuses):
        wave.status = "completed"
        wave.completed_at = local_now()
    elif any(status == "in_progress" for status in statuses):
        wave.status = "in_progress"


def assert_warehouse_access(context: UserContext, warehouse_id: str) -> None:
    if (
        "*" in context.permissions
        or "warehouse:all" in context.permissions
        or getattr(context.user, "is_superuser", False)
    ):
        return
    if warehouse_id not in context.warehouse_ids:
        raise AppError("无权访问该仓库", code=403)


def allowed_warehouse_ids(context: UserContext) -> set[str] | None:
    if (
        "*" in context.permissions
        or "warehouse:all" in context.permissions
        or getattr(context.user, "is_superuser", False)
    ):
        return None
    return context.warehouse_ids


def _require_warehouse(db: Session, warehouse_id: str, context: UserContext) -> MdWarehouse:
    warehouse = db.scalar(
        select(MdWarehouse).where(
            MdWarehouse.id == warehouse_id,
            MdWarehouse.org_id == context.org_id,
            MdWarehouse.is_deleted.is_(False),
        )
    )
    if warehouse is None:
        raise AppError("仓库不存在或不属于当前组织", code=404)
    assert_warehouse_access(context, warehouse_id)
    return warehouse


def _require_material(db: Session, material_id: str, context: UserContext) -> MdMaterial:
    material = db.scalar(
        select(MdMaterial).where(
            MdMaterial.id == material_id,
            MdMaterial.org_id == context.org_id,
            MdMaterial.is_deleted.is_(False),
        )
    )
    if material is None:
        raise AppError("物料不存在或不属于当前组织", code=404)
    return material


def _require_location(
    db: Session, location_id: str, warehouse_id: str, context: UserContext
) -> InvLocation:
    location = db.scalar(
        select(InvLocation).where(
            InvLocation.id == location_id,
            InvLocation.org_id == context.org_id,
            InvLocation.warehouse_id == warehouse_id,
            InvLocation.is_deleted.is_(False),
            InvLocation.status == "active",
        )
    )
    if location is None:
        raise AppError("库位不存在、不属于当前仓库或已停用", code=404)
    return location


def _require_batch(
    db: Session, batch_id: str | None, material_id: str, context: UserContext
) -> InvBatch | None:
    if batch_id is None:
        return None
    batch = db.scalar(
        select(InvBatch).where(
            InvBatch.id == batch_id,
            InvBatch.org_id == context.org_id,
            InvBatch.material_id == material_id,
            InvBatch.is_deleted.is_(False),
            InvBatch.status == "active",
        )
    )
    if batch is None:
        raise AppError("批次不存在、不属于当前物料或已停用", code=404)
    if batch.expiry_date is not None and batch.expiry_date < local_today():
        raise AppError("批次已过期", code=400)
    return batch


def create_location(db: Session, warehouse_id: str, zone_id: str | None, payload, context: UserContext) -> InvLocation:
    _require_warehouse(db, warehouse_id, context)
    if zone_id is not None:
        zone = db.scalar(
            select(InvZone).where(
                InvZone.id == zone_id,
                InvZone.org_id == context.org_id,
                InvZone.warehouse_id == warehouse_id,
                InvZone.is_deleted.is_(False),
            )
        )
        if zone is None:
            raise AppError("库区不存在或不属于当前仓库", code=404)
    duplicate = db.scalar(
        select(InvLocation).where(
            InvLocation.warehouse_id == warehouse_id,
            InvLocation.code == payload.code,
        )
    )
    if duplicate is not None:
        raise AppError("同一仓库内库位编码已存在", code=409)
    row = InvLocation(
        org_id=context.org_id,
        warehouse_id=warehouse_id,
        zone_id=zone_id,
        code=payload.code,
        name=payload.name,
        status=payload.status,
    )
    db.add(row)
    db.flush()
    write_operation_log(db, user=context.user, action="create", resource="inv_location", target_id=row.id)
    return row


def update_location(db: Session, location_id: str, payload, context: UserContext) -> InvLocation:
    row = db.scalar(
        select(InvLocation).where(
            InvLocation.id == location_id,
            InvLocation.org_id == context.org_id,
            InvLocation.is_deleted.is_(False),
        )
    )
    if row is None:
        raise AppError("库位不存在", code=404)
    assert_warehouse_access(context, row.warehouse_id)
    duplicate = db.scalar(
        select(InvLocation).where(
            InvLocation.org_id == context.org_id,
            InvLocation.warehouse_id == row.warehouse_id,
            InvLocation.code == payload.code,
            InvLocation.id != location_id,
            InvLocation.is_deleted.is_(False),
        )
    )
    if duplicate is not None:
        raise AppError("同一仓库内库位编码已存在", code=409)
    row.code = payload.code
    row.name = payload.name
    row.status = payload.status
    row.version += 1
    write_operation_log(db, user=context.user, action="update", resource="inv_location", target_id=row.id)
    return row


def delete_location(db: Session, location_id: str, context: UserContext) -> None:
    row = db.scalar(
        select(InvLocation).where(
            InvLocation.id == location_id,
            InvLocation.org_id == context.org_id,
            InvLocation.is_deleted.is_(False),
        )
    )
    if row is None:
        raise AppError("库位不存在", code=404)
    assert_warehouse_access(context, row.warehouse_id)
    occupied = db.scalar(
        select(InvCostLayer.id).where(
            InvCostLayer.location_id == location_id,
            InvCostLayer.remaining_quantity > 0,
            InvCostLayer.is_deleted.is_(False),
        )
    )
    if occupied is not None:
        raise AppError("库位仍有可用库存，暂不能删除", code=400)
    row.is_deleted = True
    row.version += 1
    write_operation_log(db, user=context.user, action="delete", resource="inv_location", target_id=row.id)


def create_batch(db: Session, material_id: str, payload, context: UserContext) -> InvBatch:
    _require_material(db, material_id, context)
    if payload.production_date and payload.expiry_date and payload.expiry_date < payload.production_date:
        raise AppError("批次失效日期不能早于生产日期", code=400)
    duplicate = db.scalar(
        select(InvBatch).where(
            InvBatch.org_id == context.org_id,
            InvBatch.material_id == material_id,
            InvBatch.batch_no == payload.batch_no,
        )
    )
    if duplicate is not None:
        raise AppError("物料批次号已存在", code=409)
    row = InvBatch(
        org_id=context.org_id,
        material_id=material_id,
        batch_no=payload.batch_no,
        production_date=payload.production_date,
        expiry_date=payload.expiry_date,
        status=payload.status,
    )
    db.add(row)
    db.flush()
    write_operation_log(db, user=context.user, action="create", resource="inv_batch", target_id=row.id)
    return row


def update_batch(db: Session, batch_id: str, payload, context: UserContext) -> InvBatch:
    row = db.scalar(
        select(InvBatch).where(
            InvBatch.id == batch_id,
            InvBatch.org_id == context.org_id,
            InvBatch.is_deleted.is_(False),
        )
    )
    if row is None:
        raise AppError("批次不存在", code=404)
    duplicate = db.scalar(
        select(InvBatch).where(
            InvBatch.org_id == context.org_id,
            InvBatch.material_id == row.material_id,
            InvBatch.batch_no == payload.batch_no,
            InvBatch.id != batch_id,
            InvBatch.is_deleted.is_(False),
        )
    )
    if duplicate is not None:
        raise AppError("物料批次号已存在", code=409)
    row.batch_no = payload.batch_no
    row.production_date = payload.production_date
    row.expiry_date = payload.expiry_date
    row.status = payload.status
    row.version += 1
    write_operation_log(db, user=context.user, action="update", resource="inv_batch", target_id=row.id)
    return row


def delete_batch(db: Session, batch_id: str, context: UserContext) -> None:
    row = db.scalar(
        select(InvBatch).where(
            InvBatch.id == batch_id,
            InvBatch.org_id == context.org_id,
            InvBatch.is_deleted.is_(False),
        )
    )
    if row is None:
        raise AppError("批次不存在", code=404)
    occupied = db.scalar(
        select(InvCostLayer.id).where(
            InvCostLayer.batch_id == batch_id,
            InvCostLayer.remaining_quantity > 0,
            InvCostLayer.is_deleted.is_(False),
        )
    )
    if occupied is not None:
        raise AppError("批次仍有可用库存，暂不能删除", code=400)
    row.is_deleted = True
    row.version += 1
    write_operation_log(db, user=context.user, action="delete", resource="inv_batch", target_id=row.id)


def _assert_new_source(
    db: Session, context: UserContext, source_type: str, source_id: str, warehouse_id: str, material_id: str, direction: str
) -> None:
    duplicate = db.scalar(
        select(InvStockTransaction.id).where(
            InvStockTransaction.org_id == context.org_id,
            InvStockTransaction.source_type == source_type,
            InvStockTransaction.source_id == source_id,
            InvStockTransaction.warehouse_id == warehouse_id,
            InvStockTransaction.material_id == material_id,
            InvStockTransaction.direction == direction,
        )
    )
    if duplicate is not None:
        raise AppError("库存来源单据已入账，禁止重复记账", code=409)


def post_fifo_inbound(
    db: Session, source_type: str, source_id: str, warehouse_id: str, location_id: str,
    material_id: str, batch_id: str | None, quantity: Decimal, unit_cost: Decimal, context: UserContext,
) -> list[InvCostLayer]:
    from app.services.cost_service import assert_period_open

    quantity = _decimal(quantity)
    assert_period_open(db, context.org_id, local_today())
    unit_cost = _decimal(unit_cost)
    if quantity <= 0 or unit_cost < 0:
        raise AppError("入库数量或单位成本无效", code=400)
    _require_warehouse(db, warehouse_id, context)
    _require_material(db, material_id, context)
    _require_location(db, location_id, warehouse_id, context)
    _require_batch(db, batch_id, material_id, context)
    _assert_new_source(db, context, source_type, source_id, warehouse_id, material_id, "in")
    transaction = post_stock_transaction(
        db, context, source_type=source_type, source_id=source_id, warehouse_id=warehouse_id,
        material_id=material_id, quantity=quantity, direction="in", unit_cost=unit_cost,
        location_id=location_id, batch_id=batch_id, consumed_layer_ids=[],
    )
    layer = InvCostLayer(
        org_id=context.org_id,
        material_id=material_id,
        warehouse_id=warehouse_id,
        location_id=location_id,
        batch_id=batch_id,
        inbound_transaction_id=transaction.id,
        source_type=source_type,
        source_id=source_id,
        original_quantity=quantity,
        remaining_quantity=quantity,
        unit_cost=unit_cost,
    )
    db.add(layer)
    db.add(InvTraceEvent(
        org_id=context.org_id, material_id=material_id, batch_id=batch_id,
        transaction_id=transaction.id, source_type=source_type, source_id=source_id,
        direction="in", quantity=quantity, warehouse_id=warehouse_id,
        location_id=location_id, event_time=local_today(),
    ))
    db.flush()
    write_operation_log(db, user=context.user, action="fifo_inbound", resource="inv_cost_layer", target_id=layer.id)
    return [layer]


def post_fifo_outbound(
    db: Session, source_type: str, source_id: str, warehouse_id: str, location_id: str,
    material_id: str, batch_id: str | None, quantity: Decimal, context: UserContext,
) -> list[dict]:
    from app.services.cost_service import assert_period_open

    quantity = _decimal(quantity)
    assert_period_open(db, context.org_id, local_today())
    if quantity <= 0:
        raise AppError("出库数量无效", code=400)
    _require_warehouse(db, warehouse_id, context)
    _require_material(db, material_id, context)
    _require_location(db, location_id, warehouse_id, context)
    _require_batch(db, batch_id, material_id, context)
    _assert_new_source(db, context, source_type, source_id, warehouse_id, material_id, "out")
    statement = (
        select(InvCostLayer)
        .where(
            InvCostLayer.org_id == context.org_id,
            InvCostLayer.warehouse_id == warehouse_id,
            InvCostLayer.location_id == location_id,
            InvCostLayer.material_id == material_id,
            InvCostLayer.remaining_quantity > 0,
            InvCostLayer.is_deleted.is_(False),
        )
        .order_by(InvCostLayer.created_at.asc(), InvCostLayer.id.asc())
        .with_for_update()
    )
    if batch_id is not None:
        statement = statement.where(InvCostLayer.batch_id == batch_id)
    layers = list(db.scalars(statement).all())
    if sum((_decimal(layer.remaining_quantity) for layer in layers), Decimal("0")) < quantity:
        raise AppError("可用 FIFO 成本层库存不足", code=400)

    remaining = quantity
    allocations: list[tuple[InvCostLayer, Decimal]] = []
    for layer in layers:
        consumed_quantity = min(_decimal(layer.remaining_quantity), remaining)
        if consumed_quantity > 0:
            allocations.append((layer, consumed_quantity))
            remaining -= consumed_quantity
        if remaining == 0:
            break
    total_amount = sum((amount * _decimal(layer.unit_cost) for layer, amount in allocations), Decimal("0"))
    transaction = post_stock_transaction(
        db, context, source_type=source_type, source_id=source_id, warehouse_id=warehouse_id,
        material_id=material_id, quantity=quantity, direction="out",
        unit_cost=(total_amount / quantity).quantize(QUANTITY_SCALE), location_id=location_id,
        batch_id=batch_id, consumed_layer_ids=[layer.id for layer, _ in allocations],
    )
    consumed: list[dict] = []
    for layer, consumed_quantity in allocations:
        layer.remaining_quantity = _decimal(layer.remaining_quantity) - consumed_quantity
        consumption = InvCostLayerConsumption(
            org_id=context.org_id,
            outbound_transaction_id=transaction.id,
            cost_layer_id=layer.id,
            source_type=source_type,
            source_id=source_id,
            quantity=consumed_quantity,
            unit_cost=_decimal(layer.unit_cost),
        )
        db.add(consumption)
        db.add(InvTraceEvent(
            org_id=context.org_id, material_id=material_id, batch_id=layer.batch_id,
            transaction_id=transaction.id, source_type=source_type, source_id=source_id,
            direction="out", quantity=consumed_quantity, warehouse_id=warehouse_id,
            location_id=location_id, event_time=local_today(),
        ))
        consumed.append(
            {"cost_layer_id": layer.id, "quantity": _number(consumed_quantity), "unit_cost": _number(layer.unit_cost)}
        )
    db.flush()
    write_operation_log(
        db, user=context.user, action="fifo_outbound", resource="inv_stock_transaction", target_id=transaction.id,
        detail={"consumed_layer_ids": transaction.consumed_layer_ids},
    )
    return consumed


def _slow_moving_threshold(db: Session, stock: InvStock) -> int:
    rules = db.scalars(
        select(InvSlowMovingRule).where(
            InvSlowMovingRule.org_id == stock.org_id,
            InvSlowMovingRule.status == "active",
            InvSlowMovingRule.is_deleted.is_(False),
            (InvSlowMovingRule.warehouse_id.is_(None)) | (InvSlowMovingRule.warehouse_id == stock.warehouse_id),
            (InvSlowMovingRule.material_id.is_(None)) | (InvSlowMovingRule.material_id == stock.material_id),
        )
    ).all()
    if not rules:
        return DEFAULT_SLOW_MOVING_DAYS
    selected = sorted(
        rules,
        key=lambda rule: (
            -(int(rule.warehouse_id is not None) + int(rule.material_id is not None)),
            -rule.updated_at.timestamp(),
            rule.id,
        ),
    )[0]
    return selected.threshold_days


def list_slow_moving(db: Session, context: UserContext, as_of: date | datetime) -> list[dict]:
    snapshot_date = as_of.date() if isinstance(as_of, datetime) else as_of
    statement = select(InvStock).where(InvStock.org_id == context.org_id, InvStock.quantity > 0)
    warehouse_ids = allowed_warehouse_ids(context)
    if warehouse_ids is not None:
        if not warehouse_ids:
            return []
        statement = statement.where(InvStock.warehouse_id.in_(warehouse_ids))
    rows: list[dict] = []
    for stock in db.scalars(statement).all():
        last_movement = db.scalar(
            select(func.max(InvStockTransaction.transaction_date)).where(
                InvStockTransaction.org_id == context.org_id,
                InvStockTransaction.warehouse_id == stock.warehouse_id,
                InvStockTransaction.material_id == stock.material_id,
            )
        )
        reference_date = (last_movement or stock.updated_at).date()
        days_since_movement = (snapshot_date - reference_date).days
        threshold_days = _slow_moving_threshold(db, stock)
        if days_since_movement >= threshold_days:
            rows.append(
                {
                    "warehouse_id": stock.warehouse_id,
                    "material_id": stock.material_id,
                    "quantity": _number(stock.quantity),
                    "days_since_movement": days_since_movement,
                    "threshold_days": threshold_days,
                }
            )
    return rows


def list_locations(db: Session, warehouse_id: str | None, context: UserContext) -> list[InvLocation]:
    statement = select(InvLocation).where(
        InvLocation.org_id == context.org_id,
        InvLocation.is_deleted.is_(False),
    )
    if warehouse_id:
        _require_warehouse(db, warehouse_id, context)
        statement = statement.where(InvLocation.warehouse_id == warehouse_id)
    else:
        allowed = allowed_warehouse_ids(context)
        if allowed is not None:
            statement = statement.where(InvLocation.warehouse_id.in_(allowed))
    return list(db.scalars(statement.order_by(InvLocation.warehouse_id, InvLocation.code)).all())


def list_batches(db: Session, material_id: str | None, context: UserContext) -> list[InvBatch]:
    statement = select(InvBatch).where(InvBatch.org_id == context.org_id, InvBatch.is_deleted.is_(False))
    if material_id:
        _require_material(db, material_id, context)
        statement = statement.where(InvBatch.material_id == material_id)
    return list(db.scalars(statement.order_by(InvBatch.created_at.desc())).all())


def _serialize_reservation(row: InvReservation) -> dict:
    return {
        "id": row.id, "source_type": row.source_type, "source_id": row.source_id,
        "material_id": row.material_id, "warehouse_id": row.warehouse_id,
        "quantity": _number(row.quantity), "released_quantity": _number(row.released_quantity),
        "reserved_quantity": _number(_decimal(row.quantity) - _decimal(row.released_quantity)),
        "status": row.status, "note": row.note,
    }


def create_reservation(db: Session, payload, context: UserContext) -> InvReservation:
    from app.services.inventory_service import _get_or_create_stock

    _require_warehouse(db, payload.warehouse_id, context)
    _require_material(db, payload.material_id, context)
    quantity = _decimal(payload.quantity)
    duplicate = db.scalar(select(InvReservation).where(
        InvReservation.org_id == context.org_id,
        InvReservation.source_type == payload.source_type,
        InvReservation.source_id == payload.source_id,
        InvReservation.material_id == payload.material_id,
        InvReservation.warehouse_id == payload.warehouse_id,
        InvReservation.is_deleted.is_(False),
    ).with_for_update())
    if duplicate is not None:
        if duplicate.status == "released":
            raise AppError("原来源单据的库存预留已释放，不能重复预留", code=409)
        if _decimal(duplicate.quantity) != quantity:
            raise AppError("同一来源单据的预留数量不可变更，请先释放后重新预留", code=409)
        return duplicate
    stock = _get_or_create_stock(db, context, payload.warehouse_id, payload.material_id)
    if _decimal(stock.available_quantity) < quantity:
        raise AppError("可用库存不足，无法预留", code=400)
    stock.locked_quantity = _decimal(stock.locked_quantity) + quantity
    stock.available_quantity = _decimal(stock.quantity) - _decimal(stock.locked_quantity)
    row = InvReservation(
        org_id=context.org_id, source_type=payload.source_type, source_id=payload.source_id,
        material_id=payload.material_id, warehouse_id=payload.warehouse_id,
        quantity=quantity, note=payload.note,
    )
    db.add(row)
    db.flush()
    write_operation_log(db, user=context.user, action="reserve", resource="inv_reservation", target_id=row.id)
    return row


def release_reservation(db: Session, reservation_id: str, context: UserContext) -> InvReservation:
    from app.services.inventory_service import _get_or_create_stock

    row = db.scalar(select(InvReservation).where(
        InvReservation.id == reservation_id, InvReservation.org_id == context.org_id,
        InvReservation.is_deleted.is_(False),
    ).with_for_update())
    if row is None:
        raise AppError("库存预留不存在", code=404)
    remaining = _decimal(row.quantity) - _decimal(row.released_quantity)
    if remaining <= 0 or row.status == "released":
        return row
    stock = _get_or_create_stock(db, context, row.warehouse_id, row.material_id)
    stock.locked_quantity = max(Decimal("0"), _decimal(stock.locked_quantity) - remaining)
    stock.available_quantity = _decimal(stock.quantity) - _decimal(stock.locked_quantity)
    row.released_quantity = _decimal(row.quantity)
    row.status = "released"
    row.version += 1
    write_operation_log(db, user=context.user, action="release", resource="inv_reservation", target_id=row.id)
    db.flush()
    return row


def list_reservations(db: Session, context: UserContext, status: str | None = None) -> list[dict]:
    statement = select(InvReservation).where(
        InvReservation.org_id == context.org_id, InvReservation.is_deleted.is_(False)
    )
    if status:
        statement = statement.where(InvReservation.status == status)
    allowed = allowed_warehouse_ids(context)
    if allowed is not None:
        statement = statement.where(InvReservation.warehouse_id.in_(allowed))
    return [_serialize_reservation(row) for row in db.scalars(statement.order_by(InvReservation.created_at.desc())).all()]


def list_trace_events(db: Session, context: UserContext, *, material_id: str | None = None, batch_id: str | None = None) -> list[dict]:
    statement = select(InvTraceEvent).where(
        InvTraceEvent.org_id == context.org_id, InvTraceEvent.is_deleted.is_(False)
    )
    if material_id:
        _require_material(db, material_id, context)
        statement = statement.where(InvTraceEvent.material_id == material_id)
    if batch_id:
        statement = statement.where(InvTraceEvent.batch_id == batch_id)
    allowed = allowed_warehouse_ids(context)
    if allowed is not None:
        statement = statement.where(InvTraceEvent.warehouse_id.in_(allowed))
    return [{
        "id": row.id, "material_id": row.material_id, "batch_id": row.batch_id,
        "transaction_id": row.transaction_id, "source_type": row.source_type,
        "source_id": row.source_id, "direction": row.direction,
        "quantity": _number(row.quantity), "warehouse_id": row.warehouse_id,
        "location_id": row.location_id, "event_time": row.event_time.isoformat() if row.event_time else None,
    } for row in db.scalars(statement.order_by(InvTraceEvent.event_time.desc(), InvTraceEvent.created_at.desc())).all()]
