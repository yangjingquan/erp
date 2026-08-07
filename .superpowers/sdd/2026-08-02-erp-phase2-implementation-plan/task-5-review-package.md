# Task 5 review package (Git unavailable)
## Report
# Task 5 Report: locations, batches, FIFO, slow-moving stock, and warehouse isolation

## Status

Implemented Task 5 in `/Users/yangjingquan/Documents/ERP` without initializing Git or creating a commit.

## Changed files

- `backend/app/models/inventory_advanced.py` — registered SQLAlchemy models for zones, locations, batches, FIFO layers/consumptions, slow-moving rules, and warehouse assignments.
- `backend/app/models/inventory.py` — added transaction location, batch, and immutable consumed-layer references.
- `backend/app/models/__init__.py` — imports advanced inventory models so metadata registration includes them.
- `backend/app/schemas/inventory_advanced.py` — request validation for locations, batches, and FIFO movements.
- `backend/app/services/inventory_advanced_service.py` — organization and warehouse validation, location/batch creation, atomic FIFO posting, consumption rows, and read-only slow-moving snapshots.
- `backend/app/services/inventory_service.py` — ledger entry points carry location/batch/layer traceability and enforce warehouse access, retaining `inv_stock` and `inv_stock_transaction` as the stock/ledger authority.
- `backend/app/services/auth_service.py` — loads active warehouse assignments into `UserContext`.
- `backend/app/api/inventory_advanced.py` — advanced inventory endpoints, permissions, and unified responses.
- `backend/app/main.py` — registers the advanced inventory router.
- `backend/tests/test_inventory_advanced_phase2.py` — Task 5 behavior, security, and regression tests.
- `database/init.sql` — fresh schema fields/tables plus repeatable Task 5 MySQL column/index guards.

## Behavior delivered

- Locations are unique by `(warehouse_id, code)` and enforce organization, warehouse access, and zone ownership.
- Batches are organization/material-scoped and include production/expiry dates plus status.
- FIFO inbound creates the existing stock ledger transaction and a cost layer in the same unit of work.
- FIFO outbound locks eligible layers ordered by `(created_at, id)`, validates aggregate layer availability before writing, posts the existing stock ledger, decrements layers, and records immutable per-layer consumptions.
- Transaction serialization exposes `location_id`, `batch_id`, and `consumed_layer_ids`.
- Slow-moving results are computed without stock mutation, use the most-specific active organization/warehouse/material threshold (fallback: 90 days), and only expose assigned warehouses.
- Warehouse assignments are loaded into `UserContext`; inventory users require an assignment. The established `production:manage` capability remains organization-wide so existing production stock operations continue through the same central access gate.
- Advanced writes require `inventory:manage`; advanced reads and writes retain the existing unified response format and application error code semantics.

## TDD evidence

### RED

1. Created `backend/tests/test_inventory_advanced_phase2.py` before creating any advanced inventory production module.
2. Ran:

   ```bash
   backend/.venv/bin/python -m pytest backend/tests/test_inventory_advanced_phase2.py -q
   ```

   Result: collection failed with `ModuleNotFoundError: No module named 'app.models.inventory_advanced'`, the expected absent-feature failure.

3. After the first implementation pass, focused tests exposed three test/integration defects (UUID ordering asserted instead of FIFO result ordering, tuple-shaped test warehouse IDs, and the established unified API error contract). The focused run reported `3 failed, 4 passed`.
4. The full-suite regression exposed that production operations now traverse the central warehouse gate but legacy `production:manage` flows have no per-warehouse assignment. Added `test_production_manager_has_organization_wide_warehouse_access`; it failed with `AppError: 无权访问该仓库` before the permission compatibility rule.

### GREEN

1. Focused Task 5 tests:

   ```bash
   backend/.venv/bin/python -m pytest backend/tests/test_inventory_advanced_phase2.py -q
   ```

   Result: `8 passed, 1 warning`.

2. Task 5 plus existing inventory-ledger regression tests:

   ```bash
   backend/.venv/bin/python -m pytest backend/tests/test_inventory_advanced_phase2.py backend/tests/test_inventory_ledger.py -q
   ```

   Result: `14 passed, 1 warning`.

3. Bytecode compilation:

   ```bash
   backend/.venv/bin/python -m compileall -q backend/app
   ```

   Result: exit code `0`, no output.

4. Full backend suite:

   ```bash
   backend/.venv/bin/python -m pytest backend/tests -q
   ```

   Result: `91 passed, 1 warning` in 14.77s. The only warning is the pre-existing Starlette TestClient deprecation for the installed `httpx` version.

## Self-review

- FIFO does not replace or bypass the ledger: every advanced movement calls `post_stock_transaction`, which updates `inv_stock` and appends `inv_stock_transaction` before layer effects are persisted in the same SQLAlchemy transaction.
- Outbound checks all candidate locked layers before stock/consumption writes, avoiding partial layer depletion on insufficient stock.
- Source duplicate detection is performed before FIFO mutation and the underlying ledger keeps its existing duplicate guard.
- Organization ownership is checked before warehouse access, so cross-organization references return not-found rather than revealing access state.
- Batch/location IDs are validated against the chosen material/warehouse and copied into the immutable ledger record.
- SQL includes `CREATE TABLE IF NOT EXISTS` for new tables and idempotent `information_schema`-guarded `ALTER TABLE`/index procedures for existing Phase 2 databases.
- No scan UI, cost allocation/month close, CRM, quality, HR, or platform work was added.

## Concerns

- The local test environment uses SQLite; MySQL-specific Task 5 upgrade procedures were statically reviewed and use the project’s existing repeatable-procedure pattern, but were not executed against a live MySQL instance in this workspace.
- `production:manage` is deliberately treated as organization-wide warehouse access to preserve the existing production role contract. Inventory-only users remain restricted to explicit active warehouse assignments.

## backend/app/models/inventory_advanced.py
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, UUIDModel


class InvZone(AuditMixin, UUIDModel):
    __tablename__ = "inv_zone"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (UniqueConstraint("warehouse_id", "code", name="uk_inv_zone_code"),)


class InvLocation(AuditMixin, UUIDModel):
    __tablename__ = "inv_location"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("inv_zone.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (UniqueConstraint("warehouse_id", "code", name="uk_inv_location_code"),)


class InvBatch(AuditMixin, UUIDModel):
    __tablename__ = "inv_batch"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(String(64), nullable=False)
    production_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (UniqueConstraint("org_id", "material_id", "batch_no", name="uk_inv_batch_material_no"),)


class InvCostLayer(AuditMixin, UUIDModel):
    __tablename__ = "inv_cost_layer"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("inv_location.id"), nullable=False, index=True)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("inv_batch.id"), nullable=True, index=True)
    inbound_transaction_id: Mapped[str] = mapped_column(ForeignKey("inv_stock_transaction.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    original_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)


class InvCostLayerConsumption(UUIDModel):
    __tablename__ = "inv_cost_layer_consumption"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    outbound_transaction_id: Mapped[str] = mapped_column(ForeignKey("inv_stock_transaction.id"), nullable=False, index=True)
    cost_layer_id: Mapped[str] = mapped_column(ForeignKey("inv_cost_layer.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)


class InvSlowMovingRule(AuditMixin, UUIDModel):
    __tablename__ = "inv_slow_moving_rule"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    material_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    threshold_days: Mapped[int] = mapped_column(nullable=False, default=90)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class InvWarehouseAccess(AuditMixin, UUIDModel):
    __tablename__ = "inv_warehouse_access"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    access_level: Mapped[str] = mapped_column(String(32), default="view", nullable=False)

    __table_args__ = (UniqueConstraint("warehouse_id", "user_id", name="uk_inv_warehouse_access_user"),)

## backend/app/schemas/inventory_advanced.py
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class LocationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    status: str = Field(default="active", min_length=1, max_length=32)


class BatchCreate(BaseModel):
    batch_no: str = Field(min_length=1, max_length=64)
    production_date: date | None = None
    expiry_date: date | None = None
    status: str = Field(default="active", min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.production_date and self.expiry_date and self.expiry_date < self.production_date:
            raise ValueError("expiry_date must not precede production_date")
        return self


class FifoInboundCreate(BaseModel):
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=36)
    warehouse_id: str = Field(min_length=1)
    location_id: str = Field(min_length=1)
    material_id: str = Field(min_length=1)
    batch_id: str | None = None
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)


class FifoOutboundCreate(BaseModel):
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=36)
    warehouse_id: str = Field(min_length=1)
    location_id: str = Field(min_length=1)
    material_id: str = Field(min_length=1)
    batch_id: str | None = None
    quantity: Decimal = Field(gt=0)

## backend/app/services/inventory_advanced_service.py
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
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
from app.services.audit_service import write_operation_log
from app.services.auth_service import UserContext
from app.services.inventory_service import post_stock_transaction


DEFAULT_SLOW_MOVING_DAYS = 90
QUANTITY_SCALE = Decimal("0.000001")


def _decimal(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(QUANTITY_SCALE)


def _number(value: Decimal) -> str:
    return format(_decimal(value).normalize(), "f") if value else "0"


def assert_warehouse_access(context: UserContext, warehouse_id: str) -> None:
    if (
        "*" in context.permissions
        or "production:manage" in context.permissions
        or getattr(context.user, "is_superuser", False)
    ):
        return
    if warehouse_id not in context.warehouse_ids:
        raise AppError("无权访问该仓库", code=403)


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
            InvLocation.is_deleted.is_(False),
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
            InvBatch.is_deleted.is_(False),
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
    return max(
        rules,
        key=lambda rule: int(rule.warehouse_id is not None) + int(rule.material_id is not None),
    ).threshold_days


def list_slow_moving(db: Session, context: UserContext, as_of: date | datetime) -> list[dict]:
    snapshot_date = as_of.date() if isinstance(as_of, datetime) else as_of
    statement = select(InvStock).where(InvStock.org_id == context.org_id, InvStock.quantity > 0)
    if "*" not in context.permissions and not getattr(context.user, "is_superuser", False):
        if not context.warehouse_ids:
            return []
        statement = statement.where(InvStock.warehouse_id.in_(context.warehouse_ids))
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
    list_locations,
    list_slow_moving,
    post_fifo_inbound,
    post_fifo_outbound,
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

## backend/app/services/inventory_service.py
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.inventory import (
    MFG_COMPLETION_SOURCE,
    MFG_MATERIAL_ISSUE_SOURCE,
    MFG_MATERIAL_RETURN_SOURCE,
    SUBCONTRACT_MATERIAL_ISSUE_SOURCE,
    SUBCONTRACT_RECEIPT_SOURCE,
    InvCount,
    InvCountItem,
    InvStock,
    InvStockTransaction,
    InvTransfer,
    InvTransferItem,
)
from app.models.master_data import MdMaterial
from app.models.purchase import PurchaseReceipt
from app.models.sales import SalesDelivery
from app.services.auth_service import UserContext


PRODUCTION_STOCK_SOURCES = frozenset(
    {
        MFG_MATERIAL_ISSUE_SOURCE,
        MFG_MATERIAL_RETURN_SOURCE,
        MFG_COMPLETION_SOURCE,
        SUBCONTRACT_MATERIAL_ISSUE_SOURCE,
        SUBCONTRACT_RECEIPT_SOURCE,
    }
)


def get_stock_unit_cost(
    db: Session, context: UserContext, warehouse_id: str, material_id: str
) -> Decimal:
    from app.services.inventory_advanced_service import assert_warehouse_access

    assert_warehouse_access(context, warehouse_id)
    stock = db.scalar(
        select(InvStock).where(
            InvStock.org_id == context.org_id,
            InvStock.warehouse_id == warehouse_id,
            InvStock.material_id == material_id,
        )
    )
    return Decimal(stock.average_cost) if stock is not None else Decimal("0")


def _get_or_create_stock(db: Session, context: UserContext, warehouse_id: str, material_id: str) -> InvStock:
    stock = db.scalar(
        select(InvStock)
        .where(InvStock.org_id == context.org_id, InvStock.warehouse_id == warehouse_id, InvStock.material_id == material_id)
        .with_for_update()
    )
    if stock is None:
        stock = InvStock(
            org_id=context.org_id,
            warehouse_id=warehouse_id,
            material_id=material_id,
            quantity=Decimal("0"),
            available_quantity=Decimal("0"),
        )
        db.add(stock)
        db.flush()
    return stock


def post_stock_transaction(
    db: Session,
    context: UserContext,
    *,
    source_type: str,
    source_id: str,
    warehouse_id: str,
    material_id: str,
    quantity: Decimal,
    direction: str,
    unit_cost: Decimal = Decimal("0"),
    location_id: str | None = None,
    batch_id: str | None = None,
    consumed_layer_ids: list[str] | None = None,
) -> InvStockTransaction:
    from app.services.inventory_advanced_service import assert_warehouse_access

    assert_warehouse_access(context, warehouse_id)
    if quantity <= 0 or direction not in {"in", "out"}:
        raise AppError("库存数量或方向无效", code=400)
    duplicate = db.scalar(
        select(InvStockTransaction).where(
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
    stock = _get_or_create_stock(db, context, warehouse_id, material_id)
    if direction == "out" and stock.available_quantity < quantity:
        raise AppError("可用库存不足", code=400)
    delta = quantity if direction == "in" else -quantity
    stock.quantity += delta
    stock.available_quantity = stock.quantity - stock.locked_quantity
    transaction = InvStockTransaction(
        org_id=context.org_id,
        warehouse_id=warehouse_id,
        material_id=material_id,
        location_id=location_id,
        batch_id=batch_id,
        source_type=source_type,
        source_id=source_id,
        direction=direction,
        quantity=quantity,
        unit_cost=unit_cost,
        amount=(quantity * unit_cost).quantize(Decimal("0.01")),
        created_by=context.id,
        consumed_layer_ids=consumed_layer_ids or [],
    )
    db.add(transaction)
    db.flush()
    return transaction


def create_transfer(db: Session, context: UserContext, *, from_warehouse_id: str, to_warehouse_id: str, items: list[dict]) -> InvTransfer:
    if from_warehouse_id == to_warehouse_id:
        raise AppError("调出仓库和调入仓库不能相同", code=400)
    transfer = InvTransfer(
        org_id=context.org_id,
        doc_no=f"TR-{context.id[:8]}-{date.today().strftime('%Y%m%d%H%M%S')}",
        from_warehouse_id=from_warehouse_id,
        to_warehouse_id=to_warehouse_id,
        status="draft",
        transfer_date=date.today(),
        created_by=context.id,
    )
    transfer.items = [InvTransferItem(material_id=item["material_id"], quantity=item["quantity"], unit_cost=item.get("unit_cost", 0)) for item in items]
    db.add(transfer)
    db.flush()
    return transfer


def serialize_transfer(transfer: InvTransfer) -> dict:
    return {
        "id": transfer.id,
        "doc_no": transfer.doc_no,
        "from_warehouse_id": transfer.from_warehouse_id,
        "to_warehouse_id": transfer.to_warehouse_id,
        "status": transfer.status,
        "transfer_date": transfer.transfer_date.isoformat(),
        "items": [
            {
                "id": item.id,
                "material_id": item.material_id,
                "quantity": str(item.quantity),
                "unit_cost": str(item.unit_cost),
            }
            for item in transfer.items
        ],
    }


def serialize_count(count: InvCount) -> dict:
    return {
        "id": count.id,
        "doc_no": count.doc_no,
        "warehouse_id": count.warehouse_id,
        "status": count.status,
        "count_date": count.count_date.isoformat(),
        "items": [
            {
                "id": item.id,
                "material_id": item.material_id,
                "system_quantity": str(item.system_quantity),
                "actual_quantity": str(item.actual_quantity),
                "difference_quantity": str(item.difference_quantity),
            }
            for item in count.items
        ],
    }


def serialize_transaction(transaction: InvStockTransaction) -> dict:
    return {
        "id": transaction.id,
        "warehouse_id": transaction.warehouse_id,
        "material_id": transaction.material_id,
        "location_id": transaction.location_id,
        "batch_id": transaction.batch_id,
        "source_type": transaction.source_type,
        "source_id": transaction.source_id,
        "direction": transaction.direction,
        "quantity": str(transaction.quantity),
        "unit_cost": str(transaction.unit_cost),
        "amount": str(transaction.amount),
        "transaction_date": transaction.transaction_date.isoformat(),
        "consumed_layer_ids": list(transaction.consumed_layer_ids or []),
    }


def list_stock_transactions(db: Session, context: UserContext) -> list[dict]:
    statement = (
        select(InvStockTransaction)
        .where(InvStockTransaction.org_id == context.org_id)
        .order_by(InvStockTransaction.transaction_date.desc())
    )
    return [serialize_transaction(row) for row in db.scalars(statement).all()]


def list_transfers(db: Session, context: UserContext) -> list[dict]:
    statement = select(InvTransfer).where(InvTransfer.org_id == context.org_id).order_by(InvTransfer.transfer_date.desc())
    return [serialize_transfer(row) for row in db.scalars(statement).all()]


def list_counts(db: Session, context: UserContext) -> list[dict]:
    statement = select(InvCount).where(InvCount.org_id == context.org_id).order_by(InvCount.count_date.desc())
    return [serialize_count(row) for row in db.scalars(statement).all()]


def approve_transfer(db: Session, transfer_id: str, context: UserContext) -> InvTransfer:
    transfer = db.get(InvTransfer, transfer_id)
    if transfer is None or transfer.org_id != context.org_id:
        raise AppError("调拨单不存在", code=404)
    if transfer.status != "draft":
        raise AppError("只有草稿调拨单才能审核", code=400)
    transfer.status = "approved"
    db.flush()
    return transfer


def complete_transfer(db: Session, transfer_id: str, context: UserContext) -> InvTransfer:
    transfer = db.get(InvTransfer, transfer_id)
    if transfer is None or transfer.org_id != context.org_id:
        raise AppError("调拨单不存在", code=404)
    if transfer.status != "approved":
        raise AppError("只有已审核调拨单才能完成", code=400)
    for item in transfer.items:
        post_stock_transaction(
            db, context, source_type="transfer", source_id=transfer.id,
            warehouse_id=transfer.from_warehouse_id, material_id=item.material_id,
            quantity=item.quantity, direction="out", unit_cost=item.unit_cost,
        )
        post_stock_transaction(
            db, context, source_type="transfer", source_id=transfer.id,
            warehouse_id=transfer.to_warehouse_id, material_id=item.material_id,
            quantity=item.quantity, direction="in", unit_cost=item.unit_cost,
        )
    transfer.status = "completed"
    db.flush()
    return transfer


def create_count(db: Session, context: UserContext, *, warehouse_id: str, items: list[dict]) -> InvCount:
    count = InvCount(
        org_id=context.org_id,
        doc_no=f"CT-{context.id[:8]}-{date.today().strftime('%Y%m%d%H%M%S')}",
        warehouse_id=warehouse_id,
        status="draft",
        count_date=date.today(),
        created_by=context.id,
    )
    count.items = []
    for item in items:
        stock = db.scalar(select(InvStock).where(InvStock.org_id == context.org_id, InvStock.warehouse_id == warehouse_id, InvStock.material_id == item["material_id"]))
        system_quantity = stock.quantity if stock else Decimal("0")
        actual_quantity = Decimal(item["actual_quantity"])
        count.items.append(
            InvCountItem(
                material_id=item["material_id"],
                system_quantity=system_quantity,
                actual_quantity=actual_quantity,
                difference_quantity=actual_quantity - system_quantity,
                unit_cost=stock.average_cost if stock else Decimal("0"),
            )
        )
    db.add(count)
    db.flush()
    return count


def complete_count(db: Session, count_id: str, context: UserContext) -> InvCount:
    count = db.get(InvCount, count_id)
    if count is None or count.org_id != context.org_id:
        raise AppError("盘点单不存在", code=404)
    if count.status != "draft":
        raise AppError("盘点单当前不可完成", code=400)
    for item in count.items:
        if item.difference_quantity > 0:
            post_stock_transaction(db, context, source_type="count", source_id=count.id, warehouse_id=count.warehouse_id, material_id=item.material_id, quantity=item.difference_quantity, direction="in", unit_cost=item.unit_cost)
        elif item.difference_quantity < 0:
            post_stock_transaction(db, context, source_type="count", source_id=count.id, warehouse_id=count.warehouse_id, material_id=item.material_id, quantity=-item.difference_quantity, direction="out", unit_cost=item.unit_cost)
    count.status = "completed"
    db.flush()
    return count


def list_safety_warnings(db: Session, context: UserContext) -> list[dict]:
    rows = db.execute(
        select(InvStock, MdMaterial)
        .join(MdMaterial, MdMaterial.id == InvStock.material_id)
        .where(InvStock.org_id == context.org_id, InvStock.quantity < MdMaterial.min_stock)
    ).all()
    return [
        {
            "warehouse_id": stock.warehouse_id,
            "material_id": stock.material_id,
            "current_quantity": str(stock.quantity),
            "min_quantity": str(material.min_stock),
        }
        for stock, material in rows
    ]


def complete_sales_delivery(db: Session, delivery_id: str, context: UserContext) -> SalesDelivery:
    delivery = db.get(SalesDelivery, delivery_id)
    if delivery is None or delivery.org_id != context.org_id:
        raise AppError("销售出库单不存在", code=404)
    if delivery.status != "draft":
        raise AppError("销售出库单当前不可完成", code=400)
    for item in delivery.items:
        post_stock_transaction(
            db,
            context,
            source_type="sales_delivery",
            source_id=delivery.id,
            warehouse_id=delivery.warehouse_id,
            material_id=item.material_id,
            quantity=item.quantity,
            direction="out",
            unit_cost=item.unit_price,
        )
    delivery.status = "completed"
    db.flush()
    return delivery


def complete_purchase_receipt(db: Session, receipt_id: str, context: UserContext) -> PurchaseReceipt:
    receipt = db.get(PurchaseReceipt, receipt_id)
    if receipt is None or receipt.org_id != context.org_id:
        raise AppError("采购入库单不存在", code=404)
    if receipt.status != "draft":
        raise AppError("采购入库单当前不可完成", code=400)
    for item in receipt.items:
        post_stock_transaction(
            db,
            context,
            source_type="purchase_receipt",
            source_id=receipt.id,
            warehouse_id=receipt.warehouse_id,
            material_id=item.material_id,
            quantity=item.quantity,
            direction="in",
            unit_cost=item.unit_price,
        )
    receipt.status = "completed"
    db.flush()
    return receipt

## backend/app/models/inventory.py
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDModel


MFG_MATERIAL_ISSUE_SOURCE = "mfg_material_issue"
MFG_MATERIAL_RETURN_SOURCE = "mfg_material_return"
MFG_COMPLETION_SOURCE = "mfg_completion"
SUBCONTRACT_MATERIAL_ISSUE_SOURCE = "subcontract_material_issue"
SUBCONTRACT_RECEIPT_SOURCE = "subcontract_receipt"


class InvStock(UUIDModel):
    __tablename__ = "inv_stock"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    locked_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    available_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )


class InvStockTransaction(UUIDModel):
    __tablename__ = "inv_stock_transaction"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    location_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    consumed_layer_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class InvTransfer(UUIDModel):
    __tablename__ = "inv_transfer"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    from_warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    to_warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    transfer_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    items: Mapped[list["InvTransferItem"]] = relationship(
        back_populates="transfer", cascade="all, delete-orphan"
    )


class InvTransferItem(UUIDModel):
    __tablename__ = "inv_transfer_item"

    transfer_id: Mapped[str] = mapped_column(ForeignKey("inv_transfer.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    transfer: Mapped[InvTransfer] = relationship(back_populates="items")


class InvCount(UUIDModel):
    __tablename__ = "inv_count"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    count_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    items: Mapped[list["InvCountItem"]] = relationship(
        back_populates="count", cascade="all, delete-orphan"
    )


class InvCountItem(UUIDModel):
    __tablename__ = "inv_count_item"

    count_id: Mapped[str] = mapped_column(ForeignKey("inv_count.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    system_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    actual_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    difference_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    count: Mapped[InvCount] = relationship(back_populates="items")


class InvWarning(UUIDModel):
    __tablename__ = "inv_warning"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    current_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    min_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)

## backend/app/services/auth_service.py
from dataclasses import dataclass

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import verify_password
from app.models.auth import sys_role_permission, sys_user_role
from app.models.system import SysPermission, SysRole, SysUser


@dataclass
class UserContext:
    user: SysUser
    permissions: set[str]
    warehouse_ids: set[str] = None

    def __post_init__(self) -> None:
        if self.warehouse_ids is None:
            self.warehouse_ids = set()

    @property
    def id(self) -> str:
        return self.user.id

    @property
    def org_id(self) -> str:
        return self.user.org_id

    @property
    def department_id(self) -> str | None:
        return self.user.department_id


def authenticate_user(db: Session, username: str, password: str) -> SysUser:
    user = db.scalar(
        select(SysUser).where(
            SysUser.username == username,
            SysUser.is_deleted.is_(False),
        )
    )
    if user is None or user.status != "active" or not verify_password(
        password, user.password_hash
    ):
        raise AppError("用户名或密码错误", code=401)
    return user


def load_permissions(db: Session, user: SysUser) -> set[str]:
    if user.is_superuser:
        return {"*"}
    statement = (
        select(SysPermission.code)
        .join(
            sys_role_permission,
            sys_role_permission.c.permission_id == SysPermission.id,
        )
        .join(sys_user_role, sys_user_role.c.role_id == sys_role_permission.c.role_id)
        .where(sys_user_role.c.user_id == user.id)
    )
    return set(db.scalars(statement).all())


def build_user_context(db: Session, user: SysUser, permissions=None) -> UserContext:
    from app.models.inventory_advanced import InvWarehouseAccess

    warehouse_ids = set(
        db.scalars(
            select(InvWarehouseAccess.warehouse_id).where(
                InvWarehouseAccess.org_id == user.org_id,
                InvWarehouseAccess.user_id == user.id,
                InvWarehouseAccess.is_deleted.is_(False),
            )
        ).all()
    )
    return UserContext(
        user=user,
        permissions=set(permissions) if permissions is not None else load_permissions(db, user),
        warehouse_ids=warehouse_ids,
    )


def data_scope_condition(model, user: object, scope_type: str = "department"):
    if getattr(user, "is_superuser", False) or scope_type == "all":
        return True
    conditions = [model.org_id == getattr(user, "org_id")]
    if scope_type == "own" and hasattr(model, "owner_id"):
        conditions.append(model.owner_id == getattr(user, "id"))
    elif scope_type == "department" and hasattr(model, "department_id"):
        conditions.append(model.department_id == getattr(user, "department_id"))
    return or_(*conditions)


def apply_data_scope(statement: Select, model, context: UserContext, scope_type="department"):
    condition = data_scope_condition(model, context.user, scope_type)
    return statement if condition is True else statement.where(condition)

## backend/tests/test_inventory_advanced_phase2.py
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.exceptions import AppError
from app.core.security import create_access_token
from app.models.inventory import InvStock, InvStockTransaction
from app.models.inventory_advanced import (
    InvBatch,
    InvCostLayer,
    InvCostLayerConsumption,
    InvLocation,
    InvSlowMovingRule,
    InvWarehouseAccess,
)
from app.models.master_data import MdMaterial, MdWarehouse
from app.models.system import SysUser
from app.schemas.inventory_advanced import BatchCreate, FifoInboundCreate, LocationCreate
from app.services.auth_service import UserContext
from app.services.inventory_advanced_service import (
    assert_warehouse_access,
    create_batch,
    create_location,
    list_slow_moving,
    post_fifo_inbound,
    post_fifo_outbound,
)
from app.services.inventory_service import serialize_transaction


def _context(session, user_id: str = "user-1", permissions: set[str] | None = None) -> UserContext:
    return UserContext(
        user=session.get(SysUser, user_id),
        permissions=permissions or {"*"},
        warehouse_ids=set(session.scalars(select(InvWarehouseAccess.warehouse_id).where(
            InvWarehouseAccess.user_id == user_id, InvWarehouseAccess.org_id == "org-1"
        )).all()),
    )


def _seed_inventory(session) -> None:
    session.add_all(
        [
            MdWarehouse(id="warehouse-1", org_id="org-1", code="WH-1", name="Main"),
            MdWarehouse(id="warehouse-2", org_id="org-1", code="WH-2", name="Overflow"),
            MdWarehouse(id="warehouse-other", org_id="org-2", code="WH-X", name="Other"),
            MdMaterial(id="material-1", org_id="org-1", code="MAT-1", name="Material one"),
            MdMaterial(id="material-other", org_id="org-2", code="MAT-X", name="Other material"),
        ]
    )
    session.commit()


def _grant(session, warehouse_id: str, user_id: str = "user-1") -> None:
    session.add(
        InvWarehouseAccess(
            org_id="org-1",
            warehouse_id=warehouse_id,
            user_id=user_id,
            access_level="manage",
        )
    )
    session.flush()


def _location(session, context, code: str = "A-01") -> InvLocation:
    return create_location(
        session,
        "warehouse-1",
        None,
        LocationCreate(code=code, name=f"Location {code}"),
        context,
    )


def _batch(session, context, batch_no: str) -> InvBatch:
    return create_batch(
        session,
        "material-1",
        BatchCreate(batch_no=batch_no, expiry_date=date.today() + timedelta(days=30)),
        context,
    )


def test_fifo_outbound_consumes_oldest_layers_and_records_source_layer(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session)
    location = _location(session, current_context)
    first_batch = _batch(session, current_context, "B-1")
    second_batch = _batch(session, current_context, "B-2")

    post_fifo_inbound(
        session, "receipt", "r1", "warehouse-1", location.id, "material-1", first_batch.id,
        Decimal("3"), Decimal("10"), current_context,
    )
    post_fifo_inbound(
        session, "receipt", "r2", "warehouse-1", location.id, "material-1", second_batch.id,
        Decimal("4"), Decimal("12"), current_context,
    )
    consumed = post_fifo_outbound(
        session, "delivery", "d1", "warehouse-1", location.id, "material-1", None,
        Decimal("5"), current_context,
    )

    assert [(row["quantity"], row["unit_cost"]) for row in consumed] == [
        ("3", "10"),
        ("2", "12"),
    ]
    assert {row.cost_layer_id for row in session.query(InvCostLayerConsumption)} == {
        consumed[0]["cost_layer_id"], consumed[1]["cost_layer_id"]
    }
    assert [str(row.remaining_quantity) for row in session.query(InvCostLayer).order_by(InvCostLayer.created_at)] == [
        "0.000000", "2.000000"
    ]


def test_fifo_outbound_rejects_insufficient_layer_stock_without_writing_ledger(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session)
    location = _location(session, current_context)
    batch = _batch(session, current_context, "B-1")
    post_fifo_inbound(
        session, "receipt", "r1", "warehouse-1", location.id, "material-1", batch.id,
        Decimal("2"), Decimal("10"), current_context,
    )
    session.flush()

    with pytest.raises(AppError) as error:
        post_fifo_outbound(
            session, "delivery", "d1", "warehouse-1", location.id, "material-1", None,
            Decimal("3"), current_context,
        )

    assert error.value.code == 400
    assert session.query(InvStockTransaction).count() == 1
    assert session.query(InvCostLayerConsumption).count() == 0
    assert str(session.query(InvCostLayer).one().remaining_quantity) == "2.000000"


def test_fifo_preserves_batch_location_traceability_in_ledger_and_layers(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session)
    location = _location(session, current_context)
    batch = _batch(session, current_context, "LOT-202608")

    layers = post_fifo_inbound(
        session, "receipt", "r1", "warehouse-1", location.id, "material-1", batch.id,
        Decimal("2"), Decimal("9.50"), current_context,
    )
    transaction = session.query(InvStockTransaction).one()

    assert layers[0].location_id == location.id
    assert layers[0].batch_id == batch.id
    assert serialize_transaction(transaction)["location_id"] == location.id
    assert serialize_transaction(transaction)["batch_id"] == batch.id
    assert serialize_transaction(transaction)["consumed_layer_ids"] == []


def test_location_and_batch_reject_duplicate_or_cross_organization_references(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session)
    _location(session, current_context, "A-01")

    with pytest.raises(AppError) as duplicate:
        _location(session, current_context, "A-01")
    with pytest.raises(AppError) as cross_org:
        create_batch(
            session,
            "material-other",
            BatchCreate(batch_no="X-1"),
            current_context,
        )

    assert duplicate.value.code == 409
    assert cross_org.value.code == 404


def test_slow_moving_uses_most_specific_threshold_without_mutating_stock(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session)
    session.add(
        InvStock(
            id="stock-1", org_id="org-1", warehouse_id="warehouse-1", material_id="material-1",
            quantity=Decimal("4"), available_quantity=Decimal("4"),
        )
    )
    session.add_all(
        [
            InvStockTransaction(
                id="txn-old", org_id="org-1", warehouse_id="warehouse-1", material_id="material-1",
                source_type="receipt", source_id="old", direction="in", quantity=Decimal("4"), unit_cost=Decimal("10"),
                transaction_date=datetime(2026, 4, 1),
            ),
            InvSlowMovingRule(org_id="org-1", threshold_days=90),
            InvSlowMovingRule(org_id="org-1", warehouse_id="warehouse-1", material_id="material-1", threshold_days=60),
        ]
    )
    session.commit()

    rows = list_slow_moving(session, current_context, date(2026, 8, 2))

    assert rows == [{
        "warehouse_id": "warehouse-1", "material_id": "material-1", "quantity": "4",
        "days_since_movement": 123, "threshold_days": 60,
    }]
    assert str(session.get(InvStock, "stock-1").quantity) == "4.000000"


def test_warehouse_access_blocks_unassigned_warehouse_and_cross_org_access(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session, permissions={"inventory:manage"})

    assert_warehouse_access(current_context, "warehouse-1")
    with pytest.raises(AppError) as unassigned:
        assert_warehouse_access(current_context, "warehouse-2")
    with pytest.raises(AppError) as cross_org:
        create_location(
            session, "warehouse-other", None, LocationCreate(code="X-01", name="Other"), current_context
        )

    assert unassigned.value.code == 403
    assert cross_org.value.code == 404


def test_production_manager_has_organization_wide_warehouse_access(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)

    assert_warehouse_access(_context(session, permissions={"production:manage"}), "warehouse-2")


def test_advanced_api_requires_inventory_permission_and_warehouse_assignment(client_and_session):
    client, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    no_permission_headers = {"Authorization": f"Bearer {create_access_token('user-1', [])}"}
    manage_headers = {"Authorization": f"Bearer {create_access_token('user-1', ['inventory:manage'])}"}

    denied = client.post(
        "/api/inventory/advanced/locations",
        json={"warehouse_id": "warehouse-1", "code": "A-01", "name": "A-01"},
        headers=no_permission_headers,
    )
    forbidden_warehouse = client.get(
        "/api/inventory/advanced/locations?warehouse_id=warehouse-2", headers=manage_headers
    )

    assert denied.status_code == 200
    assert denied.json()["code"] == 403
    assert forbidden_warehouse.status_code == 200
    assert forbidden_warehouse.json()["code"] == 403
## SQL advanced inventory
1460-CALL phase2_add_task4_index('mfg_material_issue', 'uk_mfg_material_issue_subcontract_order', 'UNIQUE KEY uk_mfg_material_issue_subcontract_order (subcontract_order_id)');
1461-CALL phase2_add_task4_index('mfg_subcontract_receipt', 'uk_mfg_subcontract_receipt_operation', 'UNIQUE KEY uk_mfg_subcontract_receipt_operation (org_id, subcontract_order_id, operation_key)');
1462-DROP PROCEDURE IF EXISTS phase2_add_task4_column;
1463-DROP PROCEDURE IF EXISTS phase2_add_task4_index;
1464-
1465:CREATE TABLE IF NOT EXISTS inv_zone (
1466-  id CHAR(36) PRIMARY KEY,
1467-  org_id CHAR(36) NOT NULL,
1468-  warehouse_id CHAR(36) NOT NULL,
1469-  code VARCHAR(64) NOT NULL,
1470-  name VARCHAR(128) NOT NULL,
1471-  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
1472-  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
1473-  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
1474-  version INT NOT NULL DEFAULT 1,
1475:  UNIQUE KEY uk_inv_zone_code (warehouse_id, code)
1476-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1477-
1478:CREATE TABLE IF NOT EXISTS inv_location (
1479-  id CHAR(36) PRIMARY KEY,
1480-  org_id CHAR(36) NOT NULL,
1481-  warehouse_id CHAR(36) NOT NULL,
1482-  zone_id CHAR(36) NULL,
1483-  code VARCHAR(64) NOT NULL,
--
1485-  status VARCHAR(32) NOT NULL DEFAULT 'active',
1486-  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
1487-  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
1488-  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
1489-  version INT NOT NULL DEFAULT 1,
1490:  UNIQUE KEY uk_inv_location_code (warehouse_id, code)
1491-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1492-
1493:CREATE TABLE IF NOT EXISTS inv_batch (
1494-  id CHAR(36) PRIMARY KEY,
1495-  org_id CHAR(36) NOT NULL,
1496-  material_id CHAR(36) NOT NULL,
1497-  batch_no VARCHAR(64) NOT NULL,
1498-  production_date DATE NULL,
--
1500-  status VARCHAR(32) NOT NULL DEFAULT 'active',
1501-  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
1502-  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
1503-  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
1504-  version INT NOT NULL DEFAULT 1,
1505:  UNIQUE KEY uk_inv_batch_material_no (org_id, material_id, batch_no)
1506-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1507-
1508:CREATE TABLE IF NOT EXISTS inv_cost_layer (
1509-  id CHAR(36) PRIMARY KEY,
1510-  org_id CHAR(36) NOT NULL,
1511-  material_id CHAR(36) NOT NULL,
1512-  warehouse_id CHAR(36) NOT NULL,
1513-  location_id CHAR(36) NOT NULL,
--
1520-  unit_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
1521-  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
1522-  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
1523-  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
1524-  version INT NOT NULL DEFAULT 1,
1525:  KEY idx_inv_cost_layer_material (org_id, material_id, warehouse_id)
1526-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1527-
1528:CREATE TABLE IF NOT EXISTS inv_cost_layer_consumption (
1529-  id CHAR(36) PRIMARY KEY,
1530-  org_id CHAR(36) NOT NULL,
1531-  outbound_transaction_id CHAR(36) NOT NULL,
1532-  cost_layer_id CHAR(36) NOT NULL,
1533-  source_type VARCHAR(64) NOT NULL,
--
1537-  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
1538-  KEY idx_inv_layer_consumption_outbound (outbound_transaction_id),
1539-  KEY idx_inv_layer_consumption_layer (cost_layer_id)
1540-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1541-
1542:CREATE TABLE IF NOT EXISTS inv_slow_moving_rule (
1543-  id CHAR(36) PRIMARY KEY,
1544-  org_id CHAR(36) NOT NULL,
1545-  warehouse_id CHAR(36) NULL,
1546-  material_id CHAR(36) NULL,
1547-  threshold_days INT NOT NULL DEFAULT 90,
1548-  status VARCHAR(32) NOT NULL DEFAULT 'active',
1549-  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
1550-  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
1551-  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
1552-  version INT NOT NULL DEFAULT 1,
1553:  KEY idx_inv_slow_moving_rule_scope (org_id, warehouse_id, material_id)
1554-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1555-
1556-CREATE TABLE IF NOT EXISTS inv_warehouse_access (
1557-  id CHAR(36) PRIMARY KEY,
1558-  org_id CHAR(36) NOT NULL,
--
1567-  KEY idx_inv_warehouse_access_org_user (org_id, user_id)
1568-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1569-
1570--- Upgrade Task 5 advanced inventory fields safely when this script is re-run
1571--- against a Phase 2 foundation database that already has the placeholder tables.
1572:DROP PROCEDURE IF EXISTS phase2_add_task5_column;
1573-DELIMITER //
1574:CREATE PROCEDURE phase2_add_task5_column(
1575-  IN table_name_input VARCHAR(64),
1576-  IN column_name_input VARCHAR(64),
1577-  IN column_definition TEXT
1578-)
1579-BEGIN
--
1592-    DEALLOCATE PREPARE phase2_task5_statement;
1593-  END IF;
1594-END//
1595-DELIMITER ;
1596-
1597:DROP PROCEDURE IF EXISTS phase2_add_task5_index;
1598-DELIMITER //
1599:CREATE PROCEDURE phase2_add_task5_index(
1600-  IN table_name_input VARCHAR(64),
1601-  IN index_name_input VARCHAR(64),
1602-  IN index_definition TEXT
1603-)
1604-BEGIN
--
1615-    DEALLOCATE PREPARE phase2_task5_index_statement;
1616-  END IF;
1617-END//
1618-DELIMITER ;
1619-
1620:CALL phase2_add_task5_column('inv_stock_transaction', 'location_id', 'CHAR(36) NULL');
1621:CALL phase2_add_task5_column('inv_stock_transaction', 'batch_id', 'CHAR(36) NULL');
1622:CALL phase2_add_task5_column('inv_stock_transaction', 'consumed_layer_ids', 'JSON NULL');
1623:CALL phase2_add_task5_column('inv_location', 'status', 'VARCHAR(32) NOT NULL DEFAULT ''active''');
1624:CALL phase2_add_task5_column('inv_batch', 'status', 'VARCHAR(32) NOT NULL DEFAULT ''active''');
1625:CALL phase2_add_task5_column('inv_cost_layer', 'location_id', 'CHAR(36) NOT NULL DEFAULT ''''');
1626:CALL phase2_add_task5_column('inv_cost_layer', 'batch_id', 'CHAR(36) NULL');
1627:CALL phase2_add_task5_column('inv_cost_layer', 'inbound_transaction_id', 'CHAR(36) NOT NULL DEFAULT ''''');
1628:CALL phase2_add_task5_column('inv_cost_layer', 'original_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
1629:CALL phase2_add_task5_index('inv_cost_layer', 'idx_inv_cost_layer_fifo', 'KEY idx_inv_cost_layer_fifo (org_id, warehouse_id, location_id, material_id, created_at)');
1630:CALL phase2_add_task5_index('inv_stock_transaction', 'idx_inv_transaction_location_batch', 'KEY idx_inv_transaction_location_batch (warehouse_id, location_id, batch_id)');
1631:DROP PROCEDURE IF EXISTS phase2_add_task5_column;
1632:DROP PROCEDURE IF EXISTS phase2_add_task5_index;
1633-
1634-CREATE TABLE IF NOT EXISTS cost_period_close (
1635-  id CHAR(36) PRIMARY KEY,
1636-  org_id CHAR(36) NOT NULL,
1637-  period VARCHAR(16) NOT NULL,
