# Task 5 fix review snapshot
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
- Production users require explicit active warehouse assignments for stock operations, just like inventory users. Organization-wide access is granted only through the clearly named `warehouse:all` permission (or superuser/`*`).

## Review-fix addendum

### Findings addressed

1. Removed the `production:manage` warehouse-access bypass. Only superusers, `*`, and the explicit `warehouse:all` permission bypass `InvWarehouseAccess`; an unassigned production manager now receives application error 403.
2. Added the shared warehouse scope to legacy inventory reads and operations:
   - `list_stock`, `list_stock_transactions`, `list_transfers`, `list_counts`, and `list_safety_warnings` filter to assigned warehouses.
   - The `/api/inventory/stock` endpoint accepts an optional `warehouse_id`, checks access before returning that warehouse’s stock, and uses the same scope for unqualified list requests.
   - Count creation/completion and transfer creation/approval/completion check warehouse access before stock preparation or ledger work. Transfers require access to both endpoints.
3. Location and batch duplicate detection now includes soft-deleted rows and deterministically returns `AppError(..., code=409)` instead of allowing a database unique-constraint exception.
4. Slow-moving rules now select by specificity, then most recently updated rule, then ascending rule ID as a stable final tie-breaker.

### Test fixture changes

- `test_inventory_ledger.py`, `test_work_order_phase2.py`, and `test_subcontract_phase2.py` now seed explicit `InvWarehouseAccess` records for warehouses used by their authenticated API flows.
- No production test receives a global warehouse permission. The focused global bypass test uses only `warehouse:all`.

### Review-fix TDD evidence

Added focused tests before changing the implementation. The first RED run was:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_inventory_advanced_phase2.py -q
```

Result: `6 failed, 7 passed`. The failures directly proved the role bypass, unscoped legacy list reads, missing operation guards, soft-delete unique exception, and unstable slow-rule tie.

The stock-endpoint scope test was then added separately and failed RED because `/api/inventory/stock?warehouse_id=warehouse-1` returned both warehouses; after adding `list_stock` and the API scope it passed GREEN.

### Review-fix verification

```bash
backend/.venv/bin/python -m pytest backend/tests/test_inventory_advanced_phase2.py backend/tests/test_inventory_ledger.py backend/tests/test_production_planning_phase2.py backend/tests/test_work_order_phase2.py backend/tests/test_subcontract_phase2.py -q
```

Result: `44 passed, 1 warning`.

```bash
backend/.venv/bin/python -m compileall -q backend/app
```

Result: exit code `0`.

```bash
backend/.venv/bin/python -m pytest backend/tests -q
```

Result: `97 passed, 1 warning` in 15.18s. The warning remains the installed Starlette TestClient/httpx deprecation.
## Access
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
## Inventory service
from datetime import date
from decimal import Decimal

from sqlalchemy import false, select
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


def _apply_warehouse_scope(statement, warehouse_column, context: UserContext):
    from app.services.inventory_advanced_service import allowed_warehouse_ids

    warehouse_ids = allowed_warehouse_ids(context)
    if warehouse_ids is None:
        return statement
    if not warehouse_ids:
        return statement.where(false())
    return statement.where(warehouse_column.in_(warehouse_ids))


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


def list_stock(db: Session, context: UserContext, warehouse_id: str | None = None) -> list[InvStock]:
    from app.services.inventory_advanced_service import assert_warehouse_access

    statement = select(InvStock).where(InvStock.org_id == context.org_id)
    if warehouse_id is not None:
        assert_warehouse_access(context, warehouse_id)
        statement = statement.where(InvStock.warehouse_id == warehouse_id)
    else:
        statement = _apply_warehouse_scope(statement, InvStock.warehouse_id, context)
    return list(db.scalars(statement.order_by(InvStock.warehouse_id, InvStock.material_id)).all())


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
    from app.services.inventory_advanced_service import assert_warehouse_access

    if from_warehouse_id == to_warehouse_id:
        raise AppError("调出仓库和调入仓库不能相同", code=400)
    assert_warehouse_access(context, from_warehouse_id)
    assert_warehouse_access(context, to_warehouse_id)
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
    statement = _apply_warehouse_scope(
        select(InvStockTransaction)
        .where(InvStockTransaction.org_id == context.org_id)
        .order_by(InvStockTransaction.transaction_date.desc()),
        InvStockTransaction.warehouse_id,
        context,
    )
    return [serialize_transaction(row) for row in db.scalars(statement).all()]


def list_transfers(db: Session, context: UserContext) -> list[dict]:
    statement = select(InvTransfer).where(InvTransfer.org_id == context.org_id)
    statement = _apply_warehouse_scope(statement, InvTransfer.from_warehouse_id, context)
    statement = _apply_warehouse_scope(statement, InvTransfer.to_warehouse_id, context)
    statement = statement.order_by(InvTransfer.transfer_date.desc())
    return [serialize_transfer(row) for row in db.scalars(statement).all()]


def list_counts(db: Session, context: UserContext) -> list[dict]:
    statement = _apply_warehouse_scope(
        select(InvCount).where(InvCount.org_id == context.org_id).order_by(InvCount.count_date.desc()),
        InvCount.warehouse_id,
        context,
    )
    return [serialize_count(row) for row in db.scalars(statement).all()]


def approve_transfer(db: Session, transfer_id: str, context: UserContext) -> InvTransfer:
    from app.services.inventory_advanced_service import assert_warehouse_access

    transfer = db.get(InvTransfer, transfer_id)
    if transfer is None or transfer.org_id != context.org_id:
        raise AppError("调拨单不存在", code=404)
    assert_warehouse_access(context, transfer.from_warehouse_id)
    assert_warehouse_access(context, transfer.to_warehouse_id)
    if transfer.status != "draft":
        raise AppError("只有草稿调拨单才能审核", code=400)
    transfer.status = "approved"
    db.flush()
    return transfer


def complete_transfer(db: Session, transfer_id: str, context: UserContext) -> InvTransfer:
    from app.services.inventory_advanced_service import assert_warehouse_access

    transfer = db.get(InvTransfer, transfer_id)
    if transfer is None or transfer.org_id != context.org_id:
        raise AppError("调拨单不存在", code=404)
    assert_warehouse_access(context, transfer.from_warehouse_id)
    assert_warehouse_access(context, transfer.to_warehouse_id)
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
    from app.services.inventory_advanced_service import assert_warehouse_access

    assert_warehouse_access(context, warehouse_id)
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
    from app.services.inventory_advanced_service import assert_warehouse_access

    count = db.get(InvCount, count_id)
    if count is None or count.org_id != context.org_id:
        raise AppError("盘点单不存在", code=404)
    assert_warehouse_access(context, count.warehouse_id)
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
    statement = _apply_warehouse_scope(
        select(InvStock, MdMaterial)
        .join(MdMaterial, MdMaterial.id == InvStock.material_id)
        .where(InvStock.org_id == context.org_id, InvStock.quantity < MdMaterial.min_stock),
        InvStock.warehouse_id,
        context,
    )
    rows = db.execute(statement).all()
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
## Advanced service
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
## Tests
        ]
    )
    session.commit()

    rows = list_slow_moving(session, current_context, date(2026, 8, 2))

    assert rows[0]["threshold_days"] == 75


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


def test_production_manager_without_assignment_is_denied_warehouse_access(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)

    with pytest.raises(AppError) as error:
        assert_warehouse_access(_context(session, permissions={"production:manage"}), "warehouse-2")

    assert error.value.code == 403


def test_global_warehouse_permission_bypasses_assignments(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)

    assert_warehouse_access(_context(session, permissions={"warehouse:all"}), "warehouse-2")


def test_inventory_lists_only_return_assigned_warehouse_rows(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session, permissions={"inventory:manage"})
    material = session.get(MdMaterial, "material-1")
    material.min_stock = Decimal("5")
    session.add_all(
        [
            InvStock(id="stock-1", org_id="org-1", warehouse_id="warehouse-1", material_id="material-1", quantity=Decimal("1"), available_quantity=Decimal("1")),
            InvStock(id="stock-2", org_id="org-1", warehouse_id="warehouse-2", material_id="material-1", quantity=Decimal("1"), available_quantity=Decimal("1")),
            InvStockTransaction(id="txn-1", org_id="org-1", warehouse_id="warehouse-1", material_id="material-1", source_type="receipt", source_id="r1", direction="in", quantity=Decimal("1")),
            InvStockTransaction(id="txn-2", org_id="org-1", warehouse_id="warehouse-2", material_id="material-1", source_type="receipt", source_id="r2", direction="in", quantity=Decimal("1")),
            InvTransfer(id="transfer-1", org_id="org-1", doc_no="TR-1", from_warehouse_id="warehouse-1", to_warehouse_id="warehouse-1", transfer_date=date.today()),
            InvTransfer(id="transfer-2", org_id="org-1", doc_no="TR-2", from_warehouse_id="warehouse-2", to_warehouse_id="warehouse-2", transfer_date=date.today()),
            InvCount(id="count-1", org_id="org-1", doc_no="CT-1", warehouse_id="warehouse-1", count_date=date.today()),
            InvCount(id="count-2", org_id="org-1", doc_no="CT-2", warehouse_id="warehouse-2", count_date=date.today()),
        ]
    )
    session.commit()

    assert [row["warehouse_id"] for row in list_stock_transactions(session, current_context)] == ["warehouse-1"]
    assert [row["from_warehouse_id"] for row in list_transfers(session, current_context)] == ["warehouse-1"]
    assert [row["warehouse_id"] for row in list_counts(session, current_context)] == ["warehouse-1"]
    assert [row["warehouse_id"] for row in list_safety_warnings(session, current_context)] == ["warehouse-1"]


def test_stock_api_rejects_unassigned_warehouse_before_returning_stock(client_and_session):
    client, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    session.add_all(
        [
            InvStock(id="stock-1", org_id="org-1", warehouse_id="warehouse-1", material_id="material-1", quantity=Decimal("1"), available_quantity=Decimal("1")),
            InvStock(id="stock-2", org_id="org-1", warehouse_id="warehouse-2", material_id="material-1", quantity=Decimal("2"), available_quantity=Decimal("2")),
        ]
    )
    session.commit()
    headers = {"Authorization": f"Bearer {create_access_token('user-1', ['inventory:manage'])}"}

    allowed = client.get("/api/inventory/stock?warehouse_id=warehouse-1", headers=headers)
    denied = client.get("/api/inventory/stock?warehouse_id=warehouse-2", headers=headers)

    assert [row["id"] for row in allowed.json()["data"]] == ["stock-1"]
    assert denied.json()["code"] == 403


def test_inventory_count_and_transfer_operations_reject_unassigned_warehouses(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session, permissions={"inventory:manage"})
    transfer = InvTransfer(
        id="transfer-2", org_id="org-1", doc_no="TR-2", from_warehouse_id="warehouse-2",
        to_warehouse_id="warehouse-1", status="draft", transfer_date=date.today(),
    )
    count = InvCount(
        id="count-2", org_id="org-1", doc_no="CT-2", warehouse_id="warehouse-2", status="draft", count_date=date.today(),
    )
    session.add_all([transfer, count])
    session.commit()

    with pytest.raises(AppError) as create_count_error:
        create_count(session, current_context, warehouse_id="warehouse-2", items=[])
    with pytest.raises(AppError) as create_transfer_error:
        create_transfer(session, current_context, from_warehouse_id="warehouse-1", to_warehouse_id="warehouse-2", items=[])
    with pytest.raises(AppError) as approve_error:
        approve_transfer(session, transfer.id, current_context)
    transfer.status = "approved"
    with pytest.raises(AppError) as complete_transfer_error:
        complete_transfer(session, transfer.id, current_context)
    with pytest.raises(AppError) as complete_count_error:
        complete_count(session, count.id, current_context)

    assert {error.value.code for error in [create_count_error, create_transfer_error, approve_error, complete_transfer_error, complete_count_error]} == {403}


