# Task 6 review package (Git unavailable)
## Report
# Appendix — frontend scan implementation

- Added `frontend/src/api/inventory-advanced.ts` with scan-token creation, scoped task listing, and scan processing helpers.
- Added `frontend/src/views/inventory-advanced/Scan.vue`, a responsive Element Plus scan form that includes `scan_id`, action, document, warehouse, location, batch, material, quantity, loading, and `ElMessage.error` handling.
- Verification: `npm test -- phase2-scan-page.test.ts` passed (1 test). `npm run typecheck` ran but is blocked by pre-existing missing Node type declarations in `frontend/tests/phase2-scan-page.test.ts` (`node:fs`, `node:path`, and `process`); it reported no scan-file errors.

# Backend and final verification

- Added scan token creation, expiration/scope validation, `scan_id` idempotency, receive-document checks, scoped open-task listing, and advanced-inventory API routes.
- Backend focused scan tests: 4 passed.
- Backend full suite: 101 passed; `python -m compileall -q app` passed.
- Frontend full suite: 35 passed; `npm run typecheck` passed after applying the repository's existing `@types/node` test-file annotation convention; `npm run build` passed. Vite emitted existing dependency annotation/chunk-size warnings only.
- Git commits were unavailable because the workspace has no writable Git metadata. Docker/MySQL execution remains unavailable in this environment.

## backend/app/services/inventory_advanced_service.py
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import jwt
from sqlalchemy import func, select
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
    InvWarehouseAccess,
    InvZone,
)
from app.models.master_data import MdMaterial, MdWarehouse
from app.models.purchase import PurchaseReceipt
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
    if action != "receive":
        raise AppError("不支持的扫描操作", code=400)

    warehouse_id = payload.get("warehouse_id")
    if warehouse_id not in set(token_payload.get("warehouse_ids", [])):
        raise AppError("无权访问该仓库", code=403)
    assert_warehouse_access(context, warehouse_id)

    existing = db.scalar(
        select(InvStockTransaction).where(
            InvStockTransaction.org_id == context.org_id,
            InvStockTransaction.source_type == "scan",
            InvStockTransaction.source_id == scan_id,
        )
    )
    if existing is not None:
        return {
            "scan_id": scan_id,
            "action": action,
            "document_id": document_id,
            "document_status": "completed",
            "transaction_id": existing.id,
            "quantity": _number(existing.quantity),
        }

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

    layers = post_fifo_inbound(
        db,
        source_type="scan",
        source_id=scan_id,
        warehouse_id=warehouse_id,
        location_id=payload.get("location_id"),
        material_id=material_id,
        batch_id=payload.get("batch_id"),
        quantity=quantity,
        unit_cost=_decimal(payload.get("unit_cost", item.unit_price)),
        context=context,
    )
    receipt.status = "completed"
    db.flush()
    transaction = db.get(InvStockTransaction, layers[0].inbound_transaction_id)
    return {
        "scan_id": scan_id,
        "action": action,
        "document_id": document_id,
        "document_status": receipt.status,
        "transaction_id": transaction.id,
        "quantity": _number(transaction.quantity),
    }


def list_scan_tasks(db: Session, context: UserContext) -> list[dict]:
    statement = select(PurchaseReceipt).where(
        PurchaseReceipt.org_id == context.org_id,
        PurchaseReceipt.status == "draft",
    )
    allowed = allowed_warehouse_ids(context)
    if allowed is not None:
        statement = statement.where(PurchaseReceipt.warehouse_id.in_(allowed))
    receipts = db.scalars(statement.order_by(PurchaseReceipt.id)).all()
    return [
        {
            "action": "receive",
            "document_id": receipt.id,
            "document_no": receipt.doc_no,
            "warehouse_id": receipt.warehouse_id,
            "status": receipt.status,
        }
        for receipt in receipts
    ]


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
    quantity = _decimal(quantity)
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
    quantity = _decimal(quantity)
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

## backend/app/api/inventory_advanced.py
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.inventory_advanced import BatchCreate, FifoInboundCreate, FifoOutboundCreate, LocationCreate
from app.services.auth_service import UserContext
from app.services.inventory_advanced_service import (
    create_batch,
    create_location,
    create_scan_token,
    list_scan_tasks,
    list_locations,
    list_slow_moving,
    post_fifo_inbound,
    post_fifo_outbound,
    process_scan,
)


router = APIRouter(prefix="/api/inventory/advanced", tags=["inventory-advanced"])


def _serialize_location(row) -> dict:
    return {
        "id": row.id,
        "warehouse_id": row.warehouse_id,
        "zone_id": row.zone_id,
        "code": row.code,
        "name": row.name,
        "status": row.status,
    }


def _serialize_batch(row) -> dict:
    return {
        "id": row.id,
        "material_id": row.material_id,
        "batch_no": row.batch_no,
        "production_date": row.production_date.isoformat() if row.production_date else None,
        "expiry_date": row.expiry_date.isoformat() if row.expiry_date else None,
        "status": row.status,
    }


def _serialize_layer(row) -> dict:
    return {
        "id": row.id,
        "warehouse_id": row.warehouse_id,
        "location_id": row.location_id,
        "batch_id": row.batch_id,
        "material_id": row.material_id,
        "remaining_quantity": str(row.remaining_quantity),
        "unit_cost": str(row.unit_cost),
    }


@router.get("/locations")
def locations(
    warehouse_id: str = Query(min_length=1),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok([_serialize_location(row) for row in list_locations(db, warehouse_id, context)])


@router.post("/locations")
def create_location_api(
    warehouse_id: str = Query(min_length=1),
    zone_id: str | None = Query(default=None),
    payload: LocationCreate = None,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    row = create_location(db, warehouse_id, zone_id, payload, context)
    db.commit()
    return ok(_serialize_location(row))


@router.post("/batches")
def create_batch_api(
    material_id: str = Query(min_length=1),
    payload: BatchCreate = None,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    row = create_batch(db, material_id, payload, context)
    db.commit()
    return ok(_serialize_batch(row))


@router.post("/fifo/inbound")
def fifo_inbound(
    payload: FifoInboundCreate,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    layers = post_fifo_inbound(db, context=context, **payload.model_dump())
    db.commit()
    return ok([_serialize_layer(row) for row in layers])


@router.post("/fifo/outbound")
def fifo_outbound(
    payload: FifoOutboundCreate,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    consumed = post_fifo_outbound(db, context=context, **payload.model_dump())
    db.commit()
    return ok(consumed)


@router.get("/slow-moving")
def slow_moving(
    as_of: date = Query(default_factory=date.today),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(list_slow_moving(db, context, as_of))


@router.post("/scan/token")
def scan_token(
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    return ok({"token": create_scan_token(db, context)})


@router.get("/scan/tasks")
def scan_tasks(
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(list_scan_tasks(db, context))


@router.post("/scan/process")
def scan_process(payload: dict, db: Session = Depends(get_db)):
    token = str(payload.get("token", ""))
    result = process_scan(
        db,
        token,
        str(payload.get("scan_id", "")),
        str(payload.get("action", "")),
        str(payload.get("document_id", "")),
        payload,
    )
    db.commit()
    return ok(result)

## backend/tests/test_scan_phase2.py
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.exceptions import AppError
from app.models.configuration import CfgGlobalParameter
from app.models.inventory import InvStockTransaction
from app.models.inventory_advanced import InvWarehouseAccess
from app.models.master_data import MdMaterial, MdWarehouse
from app.models.purchase import PurchaseReceipt, PurchaseReceiptItem
from app.models.system import SysUser
from app.schemas.inventory_advanced import BatchCreate, LocationCreate
from app.services import inventory_advanced_service as scan_service
from app.services.auth_service import UserContext


def _context(session) -> UserContext:
    return UserContext(
        user=session.get(SysUser, "user-1"),
        permissions={"inventory:manage"},
        warehouse_ids={"warehouse-1"},
    )


def _seed_receipt(session) -> None:
    session.add_all(
        [
            MdWarehouse(id="warehouse-1", org_id="org-1", code="WH-1", name="Main"),
            MdWarehouse(id="warehouse-2", org_id="org-1", code="WH-2", name="Other"),
            MdMaterial(id="material-1", org_id="org-1", code="MAT-1", name="Material one"),
            InvWarehouseAccess(
                org_id="org-1", warehouse_id="warehouse-1", user_id="user-1", access_level="manage"
            ),
            PurchaseReceipt(
                id="receipt-1", org_id="org-1", doc_no="PR-1", order_id="order-1", supplier_id="supplier-1",
                warehouse_id="warehouse-1", status="draft", receipt_date=date.today(),
            ),
        ]
    )
    session.flush()
    session.add(PurchaseReceiptItem(receipt_id="receipt-1", material_id="material-1", quantity=Decimal("2"), unit_price=Decimal("10")))
    session.commit()


def _scan_payload(session, context) -> dict:
    location = scan_service.create_location(
        session, "warehouse-1", None, LocationCreate(code="A-01", name="A-01"), context
    )
    batch = scan_service.create_batch(
        session, "material-1", BatchCreate(batch_no="LOT-1", expiry_date=date.today() + timedelta(days=30)), context
    )
    session.commit()
    return {
        "warehouse_id": "warehouse-1",
        "location_id": location.id,
        "batch_id": batch.id,
        "material_id": "material-1",
        "quantity": "2",
        "unit_cost": "10",
    }


def test_same_scan_id_returns_original_result_without_duplicate_stock_transaction(client_and_session):
    """Removing persisted scan-id lookup would create a second FIFO/ledger transaction."""
    _, session = client_and_session
    _seed_receipt(session)
    context = _context(session)
    payload = _scan_payload(session, context)

    token = scan_service.create_scan_token(session, context)
    first = scan_service.process_scan(session, token, "scan-1", "receive", "receipt-1", payload)
    second = scan_service.process_scan(session, token, "scan-1", "receive", "receipt-1", payload)

    assert first == second
    assert session.scalars(
        select(InvStockTransaction).where(
            InvStockTransaction.source_type == "scan", InvStockTransaction.source_id == "scan-1"
        )
    ).all().__len__() == 1


def test_scan_rejects_expired_token_wrong_warehouse_and_unknown_action(client_and_session):
    """Removing token binding or action validation would admit an unauthorized stock movement."""
    _, session = client_and_session
    _seed_receipt(session)
    context = _context(session)
    payload = _scan_payload(session, context)

    token = scan_service.create_scan_token(session, context)
    wrong_warehouse_payload = {**payload, "warehouse_id": "warehouse-2"}
    with pytest.raises(AppError) as warehouse_error:
        scan_service.process_scan(session, token, "scan-wrong-warehouse", "receive", "receipt-1", wrong_warehouse_payload)
    with pytest.raises(AppError) as action_error:
        scan_service.process_scan(session, token, "scan-unknown", "adjust", "receipt-1", payload)

    session.add(CfgGlobalParameter(org_id="org-1", parameter_key="scan.token.ttl", parameter_value="0"))
    session.commit()
    expired_token = scan_service.create_scan_token(session, context)
    with pytest.raises(AppError) as expired_error:
        scan_service.process_scan(session, expired_token, "scan-expired", "receive", "receipt-1", payload)

    assert warehouse_error.value.code == 403
    assert action_error.value.code == 400
    assert expired_error.value.code == 401


def test_receive_scan_validates_document_and_marks_completed_document_unavailable(client_and_session):
    """Removing document status and line-quantity checks would allow duplicate receipt completion."""
    _, session = client_and_session
    _seed_receipt(session)
    context = _context(session)
    payload = _scan_payload(session, context)
    token = scan_service.create_scan_token(session, context)

    result = scan_service.process_scan(session, token, "scan-complete", "receive", "receipt-1", payload)
    session.commit()

    assert result["document_status"] == "completed"
    assert session.get(PurchaseReceipt, "receipt-1").status == "completed"
    with pytest.raises(AppError) as error:
        scan_service.process_scan(session, token, "scan-later", "receive", "receipt-1", payload)
    assert error.value.code == 400


def test_list_scan_tasks_returns_scoped_open_receipts(client_and_session):
    """Dropping warehouse/document filtering would expose closed or unauthorized scanner work."""
    _, session = client_and_session
    _seed_receipt(session)

    tasks = scan_service.list_scan_tasks(session, _context(session))

    assert tasks == [{
        "action": "receive", "document_id": "receipt-1", "document_no": "PR-1", "warehouse_id": "warehouse-1", "status": "draft"
    }]

## frontend/src/api/inventory-advanced.ts
import { http } from "./http";

export type ScanTask = {
  action: "receive";
  document_id: string;
  document_no: string;
  warehouse_id: string;
  status: string;
};

export type ScanProcessPayload = {
  scan_id: string;
  action: "receive";
  document_id: string;
  warehouse_id: string;
  location_id: string;
  batch_id: string;
  material_id: string;
  quantity: number;
  unit_cost?: number;
};

export function createScanToken() {
  return http.post("/inventory/advanced/scan/token");
}

export function listScanTasks() {
  return http.get("/inventory/advanced/scan/tasks");
}

export function processScan(token: string, payload: ScanProcessPayload) {
  return http.post("/inventory/advanced/scan/process", { token, ...payload });
}

## frontend/src/views/inventory-advanced/Scan.vue
<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  createScanToken,
  listScanTasks,
  processScan,
  type ScanProcessPayload,
  type ScanTask,
} from "../../api/inventory-advanced";

const scanToken = ref("");
const tasks = ref<ScanTask[]>([]);
const loading = ref(false);
const processing = ref(false);
const resultMessage = ref("");
const form = reactive<ScanProcessPayload>({
  scan_id: createScanId(),
  action: "receive",
  document_id: "",
  warehouse_id: "",
  location_id: "",
  batch_id: "",
  material_id: "",
  quantity: 1,
  unit_cost: undefined,
});

function createScanId() {
  return globalThis.crypto?.randomUUID?.() ?? `scan-${Date.now()}`;
}

function tasksFrom(response: any): ScanTask[] {
  const data = response?.data?.data;
  return Array.isArray(data) ? data : [];
}

function messageFrom(error: any, fallback: string) {
  return error?.response?.data?.message || error?.response?.data?.detail || fallback;
}

function applyTask(documentId: string) {
  const task = tasks.value.find((item) => item.document_id === documentId);
  if (!task) return;
  form.action = task.action;
  form.warehouse_id = task.warehouse_id;
}

async function load() {
  loading.value = true;
  try {
    const [tokenResponse, tasksResponse] = await Promise.all([createScanToken(), listScanTasks()]);
    scanToken.value = tokenResponse?.data?.data?.token ?? tokenResponse?.data?.data ?? "";
    tasks.value = tasksFrom(tasksResponse);
  } catch (error) {
    ElMessage.error(messageFrom(error, "扫码任务加载失败，请检查接口服务后重试"));
  } finally {
    loading.value = false;
  }
}

async function submit() {
  if (!form.scan_id || !form.document_id || !form.warehouse_id || !form.location_id || !form.batch_id || !form.material_id || form.quantity <= 0) {
    ElMessage.error("请填写扫描编号、单据、仓库、库位、批次、物料和有效数量");
    return;
  }
  if (!scanToken.value) {
    ElMessage.error("扫描令牌未就绪，请刷新后重试");
    return;
  }

  processing.value = true;
  resultMessage.value = "";
  try {
    const response = await processScan(scanToken.value, form);
    const result = response?.data?.data;
    resultMessage.value = `扫描已处理：${result?.document_id || form.document_id}`;
    ElMessage.success(resultMessage.value);
    form.scan_id = createScanId();
    await load();
  } catch (error) {
    ElMessage.error(messageFrom(error, "扫码处理失败，请检查扫描数据后重试"));
  } finally {
    processing.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="scan-page" v-loading="loading">
    <el-page-header content="移动扫码入库" />
    <el-alert
      v-if="resultMessage"
      class="result"
      :title="resultMessage"
      type="success"
      show-icon
      closable
      @close="resultMessage = ''"
    />

    <el-card class="scan-card" shadow="never">
      <template #header>扫描信息</template>
      <el-form label-position="top" @submit.prevent="submit">
        <div class="form-grid">
          <el-form-item label="扫描编号" required>
            <el-input v-model="form.scan_id" name="scan_id" autocomplete="off" />
          </el-form-item>
          <el-form-item label="操作" required>
            <el-select v-model="form.action" class="full-width">
              <el-option label="采购入库" value="receive" />
            </el-select>
          </el-form-item>
          <el-form-item label="入库单" required>
            <el-select v-model="form.document_id" class="full-width" filterable @change="applyTask">
              <el-option v-for="task in tasks" :key="task.document_id" :label="task.document_no" :value="task.document_id" />
            </el-select>
          </el-form-item>
          <el-form-item label="仓库" required><el-input v-model="form.warehouse_id" /></el-form-item>
          <el-form-item label="库位" required><el-input v-model="form.location_id" /></el-form-item>
          <el-form-item label="批次" required><el-input v-model="form.batch_id" /></el-form-item>
          <el-form-item label="物料" required><el-input v-model="form.material_id" /></el-form-item>
          <el-form-item label="数量" required><el-input-number v-model="form.quantity" :min="0.0001" class="full-width" /></el-form-item>
          <el-form-item label="单位成本"><el-input-number v-model="form.unit_cost" :min="0" :precision="2" class="full-width" /></el-form-item>
        </div>
        <el-button native-type="submit" type="primary" :loading="processing" class="submit-button">提交扫码</el-button>
      </el-form>
    </el-card>
  </section>
</template>

<style scoped>
.scan-page { max-width: 860px; margin: 0 auto; padding: 12px; }
.scan-card, .result { margin-top: 16px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; }
.full-width { width: 100%; }
.submit-button { width: 100%; min-height: 44px; }
@media (max-width: 640px) {
  .scan-page { padding: 8px; }
  .form-grid { grid-template-columns: 1fr; gap: 0; }
}
</style>

## frontend/tests/phase2-scan-page.test.ts
import { describe, expect, it } from "vitest";
// @ts-expect-error The project does not currently include @types/node; Vitest provides this runtime module.
import { readFileSync } from "node:fs";
// @ts-expect-error The project does not currently include @types/node; Vitest provides this runtime module.
import { resolve } from "node:path";

describe("phase 2 mobile scan page contract", () => {
  it("uses the scan API, carries scan_id, and presents processing errors", () => {
    // @ts-expect-error The project does not currently include @types/node; Vitest provides this runtime global.
    const source = readFileSync(resolve(process.cwd(), "src/views/inventory-advanced/Scan.vue"), "utf8");

    expect(source).toContain("createScanToken");
    expect(source).toContain("processScan");
    expect(source).toContain("scan_id");
    expect(source).toContain("ElMessage.error");
  });
});
