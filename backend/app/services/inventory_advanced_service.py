from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import jwt
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.config import get_settings
from app.models.configuration import CfgGlobalParameter
from app.models.inventory import InvStock, InvStockTransaction
from app.models.inventory_advanced import (
    InvBatch,
    InvCostLayer,
    InvCostLayerConsumption,
    InvLocation,
    InvSlowMovingRule,
    InvScanRecord,
    InvWarehouseAccess,
    InvZone,
)
from app.models.master_data import MdMaterial, MdWarehouse
from app.models.purchase import PurchaseReceipt
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
        "action": "count", "document_id": f"count:{warehouse_id}", "document_no": f"COUNT-{warehouse_id[:8]}",
        "warehouse_id": warehouse_id, "status": "open",
    } for warehouse_id in warehouse_ids)
    return tasks


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
    if batch.expiry_date is not None and batch.expiry_date < date.today():
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
    assert_period_open(db, context.org_id, date.today())
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
    db.flush()
    write_operation_log(db, user=context.user, action="fifo_inbound", resource="inv_cost_layer", target_id=layer.id)
    return [layer]


def post_fifo_outbound(
    db: Session, source_type: str, source_id: str, warehouse_id: str, location_id: str,
    material_id: str, batch_id: str | None, quantity: Decimal, context: UserContext,
) -> list[dict]:
    from app.services.cost_service import assert_period_open

    quantity = _decimal(quantity)
    assert_period_open(db, context.org_id, date.today())
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


def list_locations(db: Session, warehouse_id: str, context: UserContext) -> list[InvLocation]:
    _require_warehouse(db, warehouse_id, context)
    return list(
        db.scalars(
            select(InvLocation).where(
                InvLocation.org_id == context.org_id,
                InvLocation.warehouse_id == warehouse_id,
                InvLocation.is_deleted.is_(False),
            ).order_by(InvLocation.code)
        ).all()
    )


def list_batches(db: Session, material_id: str | None, context: UserContext) -> list[InvBatch]:
    statement = select(InvBatch).where(InvBatch.org_id == context.org_id, InvBatch.is_deleted.is_(False))
    if material_id:
        _require_material(db, material_id, context)
        statement = statement.where(InvBatch.material_id == material_id)
    return list(db.scalars(statement.order_by(InvBatch.created_at.desc())).all())
