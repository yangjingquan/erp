# Task 2 fix review snapshot
## Report
# Task 2 Report: BOM, MPS, and MRP Net Requirements

## Status

Completed in the current workspace. No Git repository was initialized and no commit was created, per instruction.

## Changed Files

- `backend/app/models/production.py` — SQLAlchemy BOM, MPS, MRP run, and MRP result models with UUID, organization, audit, status, source, and snapshot fields.
- `backend/app/schemas/production.py` — validated BOM/MPS request schemas.
- `backend/app/services/planning_service.py` — BOM lifecycle/circular-reference validation, MPS creation, deterministic recursive MRP netting, snapshots, and idempotent MRP confirmation that creates one existing purchase request.
- `backend/app/api/production.py` — authenticated production routes for BOM/MPS/MRP create, lifecycle, list/detail, run, and confirmation.
- `backend/app/models/__init__.py` — production model registration.
- `backend/app/main.py` — production router registration.
- `backend/app/services/startup_check.py` — MPS/MRP tables added to the existing startup schema contract.
- `database/init.sql` — expanded BOM fields, MPS/MRP tables, and MPS/MRP number-rule seeds.
- `backend/tests/test_production_planning_phase2.py` — API-level lifecycle, net-requirement/snapshot, idempotency, invalid-input, and authentication coverage.

## TDD Evidence

### RED

Test file was created before any Task 2 production model, schema, service, API, router registration, or SQL changes.

Command:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_production_planning_phase2.py -q
```

Result: `3 failed, 1 warning in 0.65s`.

Expected failure cause: all calls to `/api/production/boms` returned `404 Not Found`, because the production API was absent and unregistered. The failures were from missing response data/code caused by that 404, not test setup errors.

### GREEN

After the minimal implementation:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_production_planning_phase2.py -q
```

Result: `3 passed, 1 warning in 0.69s`.

Covered behavior:

- `draft → submitted → approved` BOM lifecycle.
- Duplicate BOM components and invalid effective-date range return unified `code: 400` errors.
- MRP explodes `5 × 2`, subtracts available stock `3` and open purchase supply `1`, and stores a component net requirement of `6.000000` with immutable input snapshots.
- Reconfirming one MRP result returns the original purchase-request source IDs instead of creating another request.
- Production routes require authentication.

## Verification Commands and Results

```bash
backend/.venv/bin/python -m compileall -q backend/app && \
backend/.venv/bin/python -m pytest \
  backend/tests/test_phase2_foundation.py \
  backend/tests/test_schema_contract.py \
  backend/tests/test_purchase_flow.py \
  backend/tests/test_business_extensions.py -q
```

Result: compile completed successfully; `13 passed, 1 warning in 1.61s`.

```bash
backend/.venv/bin/python -m pytest backend/tests -q
```

Result: `62 passed, 1 warning in 9.47s`.

The only warning in each FastAPI test run is the existing Starlette deprecation warning for `httpx` use by `TestClient`.

## Self-Review

- Reused `UserContext`, `AppError`, `next_doc_no`, SQLAlchemy `AuditMixin`/`UUIDModel`, and the project-wide unified response envelope.
- Kept scope to production planning: no work-order implementation, subcontracting, FIFO, CRM, quality, HR, or frontend changes.
- BOM approval rejects cyclic graphs and only MRP-runs against an effective approved BOM version.
- BOM disabling rejects an MRP-referenced version; there are intentionally no BOM update/delete routes in this task, so immutable referenced versions cannot be modified or deleted through the new API.
- MRP quantities are quantized to six decimals. A new MRP run is created for every execution, while confirmation locks and reuses a result's stored source document IDs.
- MRP confirmation creates a purchase request using the existing purchase-request model and its existing number rule; it does not introduce work orders.

## Concerns

- Automated tests use SQLite, so MySQL-specific JSON storage and row-lock concurrency semantics (`FOR UPDATE`) should be smoke-tested in the deployment database before concurrent production use.

## Review Fix Report

### Findings Addressed

- Added a repeatable MySQL 8.0 upgrade path in `database/init.sql`. It checks `information_schema.columns`, adds every Task 2 expansion missing from the Task 1 `mfg_bom` stub, backfills `effective_from` from `created_at`, and then makes it non-null. Re-running the initialization script on either a fresh or existing database is safe; new MPS/MRP tables remain covered by their `CREATE TABLE IF NOT EXISTS` statements.
- Added the seeded `production:manage` permission and applied `require_permission("production:manage")` to every production write action: BOM create/submit/approve/disable, MPS create, MRP run, and MRP-result confirmation. The existing `require_permission` behavior continues to allow superusers and `*` permissions.
- Added organization ownership validation before creating a BOM or MPS. Parent/component materials and optional warehouses must be active records in `context.org_id`; known source document types also require a matching org-scoped record. Missing or cross-organization references return `AppError` 404 without consuming a document number.
- Added coverage for indirect circular BOMs, missing approved BOM versions, distinct MRP run IDs for repeated execution, approved-to-disabled transition for unreferenced BOMs, and refusal to disable an MRP-referenced BOM.

### Additional Changed Files

- `backend/app/api/production.py`
- `backend/app/services/planning_service.py`
- `backend/tests/test_production_planning_phase2.py`
- `database/init.sql`
- `task-2-report.md`

### Review-Fix TDD Evidence

RED command:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_production_planning_phase2.py -q
```

Result: `3 failed, 5 passed, 1 warning in 1.52s`.

The failures demonstrated the reported gaps: an authenticated token without `production:manage` received `code: 0`, cross-organization component and warehouse IDs received `code: 0`, and `init.sql` did not contain a repeatable schema-upgrade path.

GREEN command:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_production_planning_phase2.py -q
```

Result: `8 passed, 1 warning in 1.49s`.

### Final Review-Fix Verification

Required focused command, run from `backend`:

```bash
.venv/bin/python -m pytest tests/test_production_planning_phase2.py -q
```

Result: `8 passed, 1 warning in 1.47s`.

```bash
.venv/bin/python -m compileall -q app && .venv/bin/python -m pytest tests -q
```

Result: compilation completed successfully; `67 passed, 1 warning in 10.19s`.

The sole warning remains the existing Starlette `TestClient` deprecation warning for `httpx`.

### Remaining Concern

The repeatable upgrade SQL uses standard MySQL 8.0 stored-procedure and prepared-statement syntax and is not run by SQLite tests. It should be executed through a MySQL client as part of deployment; no separate additive migration is required.
## API
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.production import BomCreate, MpsCreate
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

router = APIRouter(prefix="/api/production", tags=["production"])


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
## Service
from collections import OrderedDict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError
from app.models.inventory import InvStock
from app.models.master_data import MdMaterial, MdWarehouse
from app.models.production import MfgBom, MfgBomItem, MfgMps, MfgMrpResult, MfgMrpRun
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.business_extensions import PurchaseRequest, PurchaseRequestItem
from app.models.sales import SalesOrder, SalesOrderItem
from app.services.auth_service import UserContext
from app.services.configuration_service import next_doc_no


QUANTITY_SCALE = Decimal("0.000001")
OPEN_ORDER_STATUSES = ("submitted", "approved")


def _quantity(value: Decimal | int | str | None) -> Decimal:
    return Decimal(value or 0).quantize(QUANTITY_SCALE, rounding=ROUND_HALF_UP)


def _serialize_snapshot_value(value: Decimal) -> str:
    return format(value.normalize(), "f") if value else "0"


def serialize_bom(bom: MfgBom) -> dict:
    return {
        "id": bom.id,
        "material_id": bom.material_id,
        "bom_version": bom.bom_version,
        "status": bom.status,
        "effective_from": bom.effective_from.isoformat(),
        "effective_to": bom.effective_to.isoformat() if bom.effective_to else None,
        "source_type": bom.source_type,
        "source_id": bom.source_id,
        "items": [
            {
                "id": item.id,
                "material_id": item.material_id,
                "quantity": f"{_quantity(item.quantity):.6f}",
                "line_no": item.line_no,
            }
            for item in bom.items
            if not item.is_deleted
        ],
    }


def serialize_mps(mps: MfgMps) -> dict:
    return {
        "id": mps.id,
        "doc_no": mps.doc_no,
        "material_id": mps.material_id,
        "warehouse_id": mps.warehouse_id,
        "plan_date": mps.plan_date.isoformat(),
        "plan_quantity": f"{_quantity(mps.plan_quantity):.6f}",
        "status": mps.status,
        "source_type": mps.source_type,
        "source_id": mps.source_id,
    }


def serialize_mrp_result(result: MfgMrpResult) -> dict:
    return {
        "id": result.id,
        "material_id": result.material_id,
        "gross_requirement": f"{_quantity(result.gross_requirement):.6f}",
        "available_stock": f"{_quantity(result.available_stock):.6f}",
        "open_supply_quantity": f"{_quantity(result.open_supply_quantity):.6f}",
        "safety_stock": f"{_quantity(result.safety_stock):.6f}",
        "net_requirement": f"{_quantity(result.net_requirement):.6f}",
        "status": result.status,
        "source_snapshot": result.source_snapshot,
        "source_document_ids": result.confirmed_source_ids,
    }


def serialize_mrp_run(run: MfgMrpRun) -> dict:
    return {
        "id": run.id,
        "doc_no": run.doc_no,
        "mps_id": run.mps_id,
        "bom_id": run.bom_id,
        "status": run.status,
        "source_snapshot": run.source_snapshot,
        "results": [serialize_mrp_result(result) for result in run.results if not result.is_deleted],
    }


def _get_bom(db: Session, bom_id: str, context: UserContext) -> MfgBom:
    bom = db.scalar(
        select(MfgBom)
        .options(selectinload(MfgBom.items))
        .where(MfgBom.id == bom_id, MfgBom.org_id == context.org_id, MfgBom.is_deleted.is_(False))
    )
    if bom is None:
        raise AppError("BOM 不存在", code=404)
    return bom


def _validate_bom(bom: MfgBom) -> None:
    if bom.effective_to is not None and bom.effective_to < bom.effective_from:
        raise AppError("BOM 生效日期范围无效", code=400)
    component_ids = [item.material_id for item in bom.items if not item.is_deleted]
    if len(component_ids) != len(set(component_ids)):
        raise AppError("BOM 组件物料不能重复", code=400)
    if bom.material_id in component_ids:
        raise AppError("BOM 不允许引用自身", code=400)
    if not component_ids or any(item.quantity <= 0 for item in bom.items if not item.is_deleted):
        raise AppError("BOM 组件数量必须大于零", code=400)


def _require_material(db: Session, material_id: str, context: UserContext) -> None:
    material = db.scalar(
        select(MdMaterial).where(
            MdMaterial.id == material_id,
            MdMaterial.org_id == context.org_id,
            MdMaterial.is_deleted.is_(False),
        )
    )
    if material is None:
        raise AppError("物料不存在或不属于当前组织", code=404)


def _require_warehouse(db: Session, warehouse_id: str, context: UserContext) -> None:
    warehouse = db.scalar(
        select(MdWarehouse).where(
            MdWarehouse.id == warehouse_id,
            MdWarehouse.org_id == context.org_id,
            MdWarehouse.is_deleted.is_(False),
        )
    )
    if warehouse is None:
        raise AppError("仓库不存在或不属于当前组织", code=404)


def _validate_source_reference(
    db: Session, source_type: str | None, source_id: str | None, context: UserContext
) -> None:
    if bool(source_type) != bool(source_id):
        raise AppError("来源类型和来源单据必须同时提供", code=400)
    if source_type is None:
        return
    source_models = {
        "sales_order": SalesOrder,
        "purchase_order": PurchaseOrder,
        "purchase_request": PurchaseRequest,
        "mfg_bom": MfgBom,
        "mfg_mps": MfgMps,
    }
    source_model = source_models.get(source_type)
    if source_model is None:
        raise AppError("不支持的来源单据类型", code=400)
    statement = select(source_model).where(
        source_model.id == source_id,
        source_model.org_id == context.org_id,
    )
    if hasattr(source_model, "is_deleted"):
        statement = statement.where(source_model.is_deleted.is_(False))
    if db.scalar(statement) is None:
        raise AppError("来源单据不存在或不属于当前组织", code=404)


def _approved_bom_for_material(db: Session, org_id: str, material_id: str, on_date) -> MfgBom | None:
    return db.scalar(
        select(MfgBom)
        .options(selectinload(MfgBom.items))
        .where(
            MfgBom.org_id == org_id,
            MfgBom.material_id == material_id,
            MfgBom.status == "approved",
            MfgBom.is_deleted.is_(False),
            MfgBom.effective_from <= on_date,
            (MfgBom.effective_to.is_(None) | (MfgBom.effective_to >= on_date)),
        )
        .order_by(MfgBom.effective_from.desc(), MfgBom.created_at.desc())
    )


def _would_be_circular(db: Session, bom: MfgBom) -> bool:
    graph: dict[str, set[str]] = {}
    approved = db.scalars(
        select(MfgBom).options(selectinload(MfgBom.items)).where(
            MfgBom.org_id == bom.org_id,
            MfgBom.status == "approved",
            MfgBom.is_deleted.is_(False),
        )
    ).all()
    for version in approved:
        graph.setdefault(version.material_id, set()).update(
            item.material_id for item in version.items if not item.is_deleted
        )
    graph[bom.material_id] = {item.material_id for item in bom.items if not item.is_deleted}

    def visit(material_id: str, path: set[str]) -> bool:
        if material_id in path:
            return True
        return any(visit(component, path | {material_id}) for component in graph.get(material_id, set()))

    return visit(bom.material_id, set())


def create_bom(db: Session, payload, context: UserContext) -> MfgBom:
    _require_material(db, payload.material_id, context)
    for item in payload.items:
        _require_material(db, item.material_id, context)
    _validate_source_reference(db, payload.source_type, payload.source_id, context)
    duplicate = db.scalar(
        select(MfgBom).where(
            MfgBom.org_id == context.org_id,
            MfgBom.material_id == payload.material_id,
            MfgBom.bom_version == payload.bom_version,
            MfgBom.is_deleted.is_(False),
        )
    )
    if duplicate is not None:
        raise AppError("BOM 版本已存在", code=409)
    bom = MfgBom(
        org_id=context.org_id,
        material_id=payload.material_id,
        bom_version=payload.bom_version,
        status="draft",
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        source_type=payload.source_type,
        source_id=payload.source_id,
        created_by=context.id,
        updated_by=context.id,
    )
    bom.items = [
        MfgBomItem(material_id=item.material_id, quantity=_quantity(item.quantity), line_no=index)
        for index, item in enumerate(payload.items, start=1)
    ]
    _validate_bom(bom)
    db.add(bom)
    db.flush()
    return bom


def submit_bom(db: Session, bom_id: str, context: UserContext) -> MfgBom:
    bom = _get_bom(db, bom_id, context)
    if bom.status != "draft":
        raise AppError(f"BOM 状态 {bom.status} 不允许提交", code=400)
    _validate_bom(bom)
    bom.status = "submitted"
    bom.updated_by = context.id
    db.flush()
    return bom


def approve_bom(db: Session, bom_id: str, context: UserContext) -> MfgBom:
    bom = _get_bom(db, bom_id, context)
    if bom.status != "submitted":
        raise AppError(f"BOM 状态 {bom.status} 不允许审核", code=400)
    _validate_bom(bom)
    if _would_be_circular(db, bom):
        raise AppError("BOM 存在循环引用", code=400)
    bom.status = "approved"
    bom.updated_by = context.id
    db.flush()
    return bom


def disable_bom(db: Session, bom_id: str, context: UserContext) -> MfgBom:
    bom = _get_bom(db, bom_id, context)
    if bom.status != "approved":
        raise AppError("只有已审核 BOM 才能停用", code=400)
    referenced = db.scalar(
        select(MfgMrpRun.id).where(MfgMrpRun.bom_id == bom.id, MfgMrpRun.is_deleted.is_(False))
    )
    if referenced is not None:
        raise AppError("BOM 已被 MRP 引用，禁止停用", code=400)
    bom.status = "disabled"
    bom.updated_by = context.id
    db.flush()
    return bom


def list_boms(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(
        select(MfgBom)
        .options(selectinload(MfgBom.items))
        .where(MfgBom.org_id == context.org_id, MfgBom.is_deleted.is_(False))
        .order_by(MfgBom.created_at.desc())
    ).all()
    return [serialize_bom(row) for row in rows]


def create_mps(db: Session, payload, context: UserContext) -> MfgMps:
    _require_material(db, payload.material_id, context)
    if payload.warehouse_id is not None:
        _require_warehouse(db, payload.warehouse_id, context)
    _validate_source_reference(db, payload.source_type, payload.source_id, context)
    mps = MfgMps(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "mfg_mps", context.org_id, payload.plan_date),
        material_id=payload.material_id,
        warehouse_id=payload.warehouse_id,
        plan_date=payload.plan_date,
        plan_quantity=_quantity(payload.plan_quantity),
        status="draft",
        source_type=payload.source_type,
        source_id=payload.source_id,
        created_by=context.id,
        updated_by=context.id,
    )
    db.add(mps)
    db.flush()
    return mps


def list_mps(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(
        select(MfgMps)
        .where(MfgMps.org_id == context.org_id, MfgMps.is_deleted.is_(False))
        .order_by(MfgMps.created_at.desc())
    ).all()
    return [serialize_mps(row) for row in rows]


def _open_purchase_quantity(db: Session, org_id: str, material_id: str, warehouse_id: str | None) -> Decimal:
    statement = (
        select(func.coalesce(func.sum(PurchaseOrderItem.quantity - PurchaseOrderItem.received_quantity), 0))
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.order_id)
        .where(
            PurchaseOrder.org_id == org_id,
            PurchaseOrder.status.in_(OPEN_ORDER_STATUSES),
            PurchaseOrder.is_deleted.is_(False),
            PurchaseOrderItem.material_id == material_id,
        )
    )
    if warehouse_id is not None:
        statement = statement.where(PurchaseOrderItem.warehouse_id == warehouse_id)
    return _quantity(db.scalar(statement))


def _open_sales_quantity(db: Session, org_id: str, material_id: str, warehouse_id: str | None) -> Decimal:
    statement = (
        select(func.coalesce(func.sum(SalesOrderItem.quantity - SalesOrderItem.delivered_quantity), 0))
        .join(SalesOrder, SalesOrder.id == SalesOrderItem.order_id)
        .where(
            SalesOrder.org_id == org_id,
            SalesOrder.status.in_(OPEN_ORDER_STATUSES),
            SalesOrder.is_deleted.is_(False),
            SalesOrderItem.material_id == material_id,
        )
    )
    if warehouse_id is not None:
        statement = statement.where(SalesOrderItem.warehouse_id == warehouse_id)
    return _quantity(db.scalar(statement))


def _material_supply_snapshot(
    db: Session, mps: MfgMps, material_id: str, bom_version: str | None
) -> tuple[Decimal, Decimal, Decimal, dict]:
    stock_statement = select(func.coalesce(func.sum(InvStock.available_quantity), 0)).where(
        InvStock.org_id == mps.org_id,
        InvStock.material_id == material_id,
    )
    if mps.warehouse_id is not None:
        stock_statement = stock_statement.where(InvStock.warehouse_id == mps.warehouse_id)
    available_stock = _quantity(db.scalar(stock_statement))
    open_purchase = _open_purchase_quantity(db, mps.org_id, material_id, mps.warehouse_id)
    open_sales = _open_sales_quantity(db, mps.org_id, material_id, mps.warehouse_id)
    material = db.scalar(
        select(MdMaterial).where(MdMaterial.id == material_id, MdMaterial.org_id == mps.org_id, MdMaterial.is_deleted.is_(False))
    )
    safety_stock = _quantity(material.min_stock if material else Decimal("0"))
    return available_stock, open_purchase, safety_stock, {
        "mps_id": mps.id,
        "plan_quantity": _serialize_snapshot_value(_quantity(mps.plan_quantity)),
        "bom_version": bom_version,
        "available_stock": _serialize_snapshot_value(available_stock),
        "open_purchase_quantity": _serialize_snapshot_value(open_purchase),
        "open_sales_quantity": _serialize_snapshot_value(open_sales),
        "safety_stock": _serialize_snapshot_value(safety_stock),
    }


def run_mrp(db: Session, mps_id: str, context: UserContext) -> MfgMrpRun:
    mps = db.get(MfgMps, mps_id)
    if mps is None or mps.org_id != context.org_id or mps.is_deleted:
        raise AppError("MPS 不存在", code=404)
    root_bom = _approved_bom_for_material(db, context.org_id, mps.material_id, mps.plan_date)
    if root_bom is None:
        raise AppError("MPS 物料缺少有效的已审核 BOM 版本", code=400)

    root_stock, root_purchase, root_safety, root_snapshot = _material_supply_snapshot(
        db, mps, mps.material_id, root_bom.bom_version
    )
    run = MfgMrpRun(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "mfg_mrp", context.org_id, mps.plan_date),
        mps_id=mps.id,
        bom_id=root_bom.id,
        status="running",
        source_snapshot=root_snapshot,
        created_by=context.id,
    )
    db.add(run)
    db.flush()

    gross_by_material: OrderedDict[str, Decimal] = OrderedDict()
    net_by_material: dict[str, Decimal] = {}
    details: dict[str, tuple[Decimal, Decimal, Decimal, dict]] = {}
    pending: OrderedDict[str, Decimal] = OrderedDict([(mps.material_id, _quantity(mps.plan_quantity))])

    while pending:
        material_id, increment = pending.popitem(last=False)
        previous_gross = gross_by_material.get(material_id, Decimal("0"))
        gross_requirement = _quantity(previous_gross + increment)
        bom = _approved_bom_for_material(db, context.org_id, material_id, mps.plan_date)
        available_stock, open_purchase, safety_stock, snapshot = _material_supply_snapshot(
            db, mps, material_id, bom.bom_version if bom else None
        )
        net_requirement = _quantity(max(gross_requirement - available_stock - open_purchase + safety_stock, Decimal("0")))
        gross_by_material[material_id] = gross_requirement
        details[material_id] = (available_stock, open_purchase, safety_stock, snapshot)
        net_increment = _quantity(net_requirement - net_by_material.get(material_id, Decimal("0")))
        net_by_material[material_id] = net_requirement
        if bom is not None and net_increment > 0:
            for item in bom.items:
                if item.is_deleted:
                    continue
                child_increment = _quantity(net_increment * _quantity(item.quantity))
                pending[item.material_id] = _quantity(pending.get(item.material_id, Decimal("0")) + child_increment)

    for material_id, gross_requirement in gross_by_material.items():
        available_stock, open_purchase, safety_stock, snapshot = details[material_id]
        run.results.append(
            MfgMrpResult(
                material_id=material_id,
                gross_requirement=gross_requirement,
                available_stock=available_stock,
                open_supply_quantity=open_purchase,
                safety_stock=safety_stock,
                net_requirement=net_by_material[material_id],
                source_snapshot=snapshot,
            )
        )
    run.status = "completed"
    mps.status = "planned"
    mps.updated_by = context.id
    db.flush()
    return run


def _get_mrp_run(db: Session, run_id: str, context: UserContext) -> MfgMrpRun:
    run = db.scalar(
        select(MfgMrpRun)
        .options(selectinload(MfgMrpRun.results))
        .where(MfgMrpRun.id == run_id, MfgMrpRun.org_id == context.org_id, MfgMrpRun.is_deleted.is_(False))
    )
    if run is None:
        raise AppError("MRP 运算记录不存在", code=404)
    return run


def confirm_mrp_result(db: Session, result_id: str, context: UserContext) -> dict:
    result = db.scalar(
        select(MfgMrpResult)
        .join(MfgMrpRun, MfgMrpRun.id == MfgMrpResult.run_id)
        .where(
            MfgMrpResult.id == result_id,
            MfgMrpResult.is_deleted.is_(False),
            MfgMrpRun.org_id == context.org_id,
            MfgMrpRun.is_deleted.is_(False),
        )
        .with_for_update()
    )
    if result is None:
        raise AppError("MRP 结果不存在", code=404)
    if result.confirmed_source_ids:
        return {"id": result.id, "status": result.status, "source_document_ids": result.confirmed_source_ids}
    if result.net_requirement <= 0:
        raise AppError("净需求为零，无需确认", code=400)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    request = PurchaseRequest(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "purchase_request", context.org_id, now.date()),
        department_id=context.department_id,
        requester_id=context.id,
        status="draft",
        request_date=now.date(),
        remark=f"MRP 结果 {result.id}",
        created_by=context.id,
        created_at=now,
        updated_at=now,
    )
    request.items = [
        PurchaseRequestItem(
            material_id=result.material_id,
            quantity=_quantity(result.net_requirement),
            line_no=1,
        )
    ]
    db.add(request)
    db.flush()
    source_document_ids = {"purchase_request_id": request.id, "purchase_request_item_id": request.items[0].id}
    result.status = "confirmed"
    result.source_type = "purchase_request"
    result.source_id = request.id
    result.confirmed_source_ids = source_document_ids
    db.flush()
    return {"id": result.id, "status": result.status, "source_document_ids": source_document_ids}
## Tests
from datetime import date
from decimal import Decimal

from app.core.security import create_access_token
from app.models.configuration import CfgNumberRule
from app.models.inventory import InvStock
from app.models.master_data import MdMaterial, MdWarehouse
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from pathlib import Path


def headers():
    return {"Authorization": f"Bearer {create_access_token('user-1', ['production:manage'])}"}


def headers_without_production_permission():
    return {"Authorization": f"Bearer {create_access_token('user-1', [])}"}


def seed_number_rules(session):
    for key, prefix in [("mfg_mps", "MPS"), ("mfg_mrp", "MRP"), ("purchase_request", "PRQ")]:
        session.add(
            CfgNumberRule(
                id=f"rule-{key}",
                org_id="org-1",
                rule_key=key,
                prefix=prefix,
                date_format="%Y%m%d",
                sequence_length=4,
                reset_cycle="day",
            )
        )
    session.flush()


def create_approved_bom(client, material_id="finished-F", component_id="component-C", quantity="2"):
    created = client.post(
        "/api/production/boms",
        json={
            "material_id": material_id,
            "bom_version": "1.0",
            "effective_from": "2026-08-01",
            "items": [{"material_id": component_id, "quantity": quantity}],
        },
        headers=headers(),
    )
    bom_id = created.json()["data"]["id"]
    submitted = client.post(f"/api/production/boms/{bom_id}/submit", headers=headers())
    approved = client.post(f"/api/production/boms/{bom_id}/approve", headers=headers())
    assert submitted.json()["data"]["status"] == "submitted"
    assert approved.json()["data"]["status"] == "approved"
    return bom_id


def test_approved_bom_mrp_uses_stock_and_open_orders(client_and_session):
    """Removing supply snapshots or using gross instead of net demand breaks this contract."""
    client, session = client_and_session
    seed_number_rules(session)
    session.add_all(
        [
            MdMaterial(id="finished-F", org_id="org-1", code="F", name="Finished"),
            MdMaterial(id="component-C", org_id="org-1", code="C", name="Component"),
            MdWarehouse(id="warehouse-1", org_id="org-1", code="WH1", name="Main warehouse"),
            InvStock(
                org_id="org-1",
                warehouse_id="warehouse-1",
                material_id="component-C",
                quantity=Decimal("3"),
                available_quantity=Decimal("3"),
            ),
        ]
    )
    purchase_order = PurchaseOrder(
        id="open-purchase-order",
        org_id="org-1",
        doc_no="PO-OPEN",
        supplier_id="supplier-1",
        status="approved",
        order_date=date(2026, 8, 2),
    )
    purchase_order.items = [
        PurchaseOrderItem(
            material_id="component-C",
            warehouse_id="warehouse-1",
            quantity=Decimal("2"),
            received_quantity=Decimal("1"),
            unit_price=Decimal("10"),
        )
    ]
    session.add(purchase_order)
    session.commit()

    create_approved_bom(client)
    mps = client.post(
        "/api/production/mps",
        json={
            "material_id": "finished-F",
            "plan_date": "2026-08-10",
            "plan_quantity": "5",
            "warehouse_id": "warehouse-1",
        },
        headers=headers(),
    )
    run = client.post(f"/api/production/mps/{mps.json()['data']['id']}/run-mrp", headers=headers())

    assert run.json()["code"] == 0
    component_result = next(
        row for row in run.json()["data"]["results"] if row["material_id"] == "component-C"
    )
    assert component_result["gross_requirement"] == "10.000000"
    assert component_result["net_requirement"] == "6.000000"
    assert component_result["source_snapshot"]["available_stock"] == "3"
    assert component_result["source_snapshot"]["open_purchase_quantity"] == "1"


def test_bom_rejects_duplicate_components_and_invalid_effective_range(client_and_session):
    """Dropping BOM semantic validation must be visible through the public response contract."""
    client, session = client_and_session
    session.add_all(
        [
            MdMaterial(id="finished-F", org_id="org-1", code="F", name="Finished"),
            MdMaterial(id="component-C", org_id="org-1", code="C", name="Component"),
        ]
    )
    session.commit()

    duplicate = client.post(
        "/api/production/boms",
        json={
            "material_id": "finished-F",
            "effective_from": "2026-08-10",
            "items": [
                {"material_id": "component-C", "quantity": "1"},
                {"material_id": "component-C", "quantity": "2"},
            ],
        },
        headers=headers(),
    )
    invalid_range = client.post(
        "/api/production/boms",
        json={
            "material_id": "finished-F",
            "effective_from": "2026-08-10",
            "effective_to": "2026-08-01",
            "items": [{"material_id": "component-C", "quantity": "1"}],
        },
        headers=headers(),
    )

    assert duplicate.json()["code"] == 400
    assert "BOM" in duplicate.json()["msg"]
    assert invalid_range.json()["code"] == 400
    assert "BOM" in invalid_range.json()["msg"]


def test_mrp_confirmation_is_idempotent_and_production_routes_require_authentication(client_and_session):
    """A repeated confirmation must reuse its source document instead of duplicating procurement demand."""
    client, session = client_and_session
    seed_number_rules(session)
    session.add_all(
        [
            MdMaterial(id="finished-F", org_id="org-1", code="F", name="Finished"),
            MdMaterial(id="component-C", org_id="org-1", code="C", name="Component"),
        ]
    )
    session.commit()
    create_approved_bom(client)
    mps = client.post(
        "/api/production/mps",
        json={"material_id": "finished-F", "plan_date": "2026-08-10", "plan_quantity": "1"},
        headers=headers(),
    )
    run = client.post(f"/api/production/mps/{mps.json()['data']['id']}/run-mrp", headers=headers())
    component_result = next(
        row for row in run.json()["data"]["results"] if row["material_id"] == "component-C"
    )

    first = client.post(
        f"/api/production/mrp-results/{component_result['id']}/confirm", headers=headers()
    )
    second = client.post(
        f"/api/production/mrp-results/{component_result['id']}/confirm", headers=headers()
    )
    unauthenticated = client.get("/api/production/boms")

    assert first.json()["code"] == 0
    assert second.json()["data"]["source_document_ids"] == first.json()["data"]["source_document_ids"]
    assert unauthenticated.json()["code"] == 401


def test_production_write_routes_require_production_manage_permission(client_and_session):
    """Removing the explicit permission dependency must deny an authenticated unprivileged user."""
    client, session = client_and_session
    session.add_all(
        [
            MdMaterial(id="finished-F", org_id="org-1", code="F", name="Finished"),
            MdMaterial(id="component-C", org_id="org-1", code="C", name="Component"),
        ]
    )
    session.commit()

    response = client.post(
        "/api/production/boms",
        json={
            "material_id": "finished-F",
            "effective_from": "2026-08-01",
            "items": [{"material_id": "component-C", "quantity": "1"}],
        },
        headers=headers_without_production_permission(),
    )

    assert response.json()["code"] == 403


def test_create_bom_and_mps_reject_cross_org_material_and_warehouse_references(client_and_session):
    """Dropping org ownership checks must prevent cross-organization planning references."""
    client, session = client_and_session
    seed_number_rules(session)
    session.add_all(
        [
            MdMaterial(id="finished-F", org_id="org-1", code="F", name="Finished"),
            MdMaterial(id="component-C", org_id="org-2", code="C", name="Other org component"),
            MdMaterial(id="component-own", org_id="org-1", code="CO", name="Own component"),
            MdWarehouse(id="warehouse-other", org_id="org-2", code="WH2", name="Other org warehouse"),
        ]
    )
    session.commit()

    cross_org_component = client.post(
        "/api/production/boms",
        json={
            "material_id": "finished-F",
            "effective_from": "2026-08-01",
            "items": [{"material_id": "component-C", "quantity": "1"}],
        },
        headers=headers(),
    )
    cross_org_warehouse = client.post(
        "/api/production/mps",
        json={
            "material_id": "finished-F",
            "warehouse_id": "warehouse-other",
            "plan_date": "2026-08-10",
            "plan_quantity": "1",
        },
        headers=headers(),
    )

    assert cross_org_component.json()["code"] == 404
    assert cross_org_warehouse.json()["code"] == 404


def test_bom_rejects_indirect_circular_reference_on_approval(client_and_session):
    client, session = client_and_session
    session.add_all(
        [
            MdMaterial(id="material-A", org_id="org-1", code="A", name="A"),
            MdMaterial(id="material-B", org_id="org-1", code="B", name="B"),
        ]
    )
    session.commit()
    create_approved_bom(client, material_id="material-B", component_id="material-A")
    circular = client.post(
        "/api/production/boms",
        json={
            "material_id": "material-A",
            "effective_from": "2026-08-01",
            "items": [{"material_id": "material-B", "quantity": "1"}],
        },
        headers=headers(),
    )
    bom_id = circular.json()["data"]["id"]
    client.post(f"/api/production/boms/{bom_id}/submit", headers=headers())

    approval = client.post(f"/api/production/boms/{bom_id}/approve", headers=headers())

    assert approval.json()["code"] == 400
    assert "循环" in approval.json()["msg"]


def test_mrp_requires_approved_bom_creates_fresh_runs_and_can_disable_unreferenced_bom(client_and_session):
    client, session = client_and_session
    seed_number_rules(session)
    session.add_all(
        [
            MdMaterial(id="finished-F", org_id="org-1", code="F", name="Finished"),
            MdMaterial(id="component-C", org_id="org-1", code="C", name="Component"),
            MdMaterial(id="finished-unused", org_id="org-1", code="FU", name="Unused finished"),
            MdMaterial(id="component-unused", org_id="org-1", code="CU", name="Unused component"),
        ]
    )
    session.commit()
    missing_bom_mps = client.post(
        "/api/production/mps",
        json={"material_id": "finished-F", "plan_date": "2026-08-10", "plan_quantity": "1"},
        headers=headers(),
    )
    missing_bom = client.post(
        f"/api/production/mps/{missing_bom_mps.json()['data']['id']}/run-mrp", headers=headers()
    )
    unreferenced_bom_id = create_approved_bom(
        client, material_id="finished-unused", component_id="component-unused"
    )
    disabled = client.post(f"/api/production/boms/{unreferenced_bom_id}/disable", headers=headers())
    bom_id = create_approved_bom(client)
    runnable_mps = client.post(
        "/api/production/mps",
        json={"material_id": "finished-F", "plan_date": "2026-08-10", "plan_quantity": "1"},
        headers=headers(),
    )
    first_run = client.post(
        f"/api/production/mps/{runnable_mps.json()['data']['id']}/run-mrp", headers=headers()
    )
    second_run = client.post(
        f"/api/production/mps/{runnable_mps.json()['data']['id']}/run-mrp", headers=headers()
    )

    assert missing_bom.json()["code"] == 400
    assert disabled.json()["data"]["status"] == "disabled"
    assert first_run.json()["data"]["id"] != second_run.json()["data"]["id"]
    assert client.post(f"/api/production/boms/{bom_id}/disable", headers=headers()).json()["code"] == 400


def test_sql_contains_repeatable_production_schema_upgrade_path():
    sql = (Path(__file__).parents[2] / "database" / "init.sql").read_text(encoding="utf-8").lower()

    assert "information_schema.columns" in sql
    assert "effective_from date" in sql
    assert "alter table `mfg_bom` add column" in sql
## SQL migration
  payload_json JSON NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  retry_count INT NOT NULL DEFAULT 0,
  next_retry_at DATETIME(6) NULL,
  claim_token CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_ext_event_outbox_aggregate_event (event_type, aggregate_type, aggregate_id),
  KEY idx_ext_event_outbox_claim_token (claim_token),
  KEY idx_ext_event_outbox_status_retry (status, next_retry_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_bom (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  bom_version VARCHAR(32) NOT NULL DEFAULT '1.0',
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  effective_from DATE NOT NULL,
  effective_to DATE NULL,
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  created_by CHAR(36) NULL,
  updated_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_bom_material_version (org_id, material_id, bom_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_bom_item (
  id CHAR(36) PRIMARY KEY,
  bom_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  line_no INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_bom_item_bom (bom_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_mps (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  material_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NULL,
  plan_date DATE NOT NULL,
  plan_quantity DECIMAL(18,6) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  created_by CHAR(36) NULL,
  updated_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_mps_doc_no (org_id, doc_no),
  KEY idx_mfg_mps_material_date (org_id, material_id, plan_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_mrp_run (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  mps_id CHAR(36) NOT NULL,
  bom_id CHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'completed',
  source_snapshot JSON NOT NULL,
  created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_mrp_run_doc_no (org_id, doc_no),
  KEY idx_mfg_mrp_run_mps (mps_id),
  KEY idx_mfg_mrp_run_bom (bom_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_mrp_result (
  id CHAR(36) PRIMARY KEY,
  run_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  gross_requirement DECIMAL(18,6) NOT NULL,
  available_stock DECIMAL(18,6) NOT NULL,
  open_supply_quantity DECIMAL(18,6) NOT NULL,
  safety_stock DECIMAL(18,6) NOT NULL,
  net_requirement DECIMAL(18,6) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  source_snapshot JSON NOT NULL,
  confirmed_source_ids JSON NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_mrp_result_run (run_id),
  KEY idx_mfg_mrp_result_material (material_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Upgrade the Task 1 BOM stub when this script is re-run against an existing
-- MySQL 8.0 database. CREATE TABLE IF NOT EXISTS does not add new columns.
DROP PROCEDURE IF EXISTS phase2_add_mfg_bom_column;
DELIMITER //
CREATE PROCEDURE phase2_add_mfg_bom_column(
  IN column_name_input VARCHAR(64),
  IN column_definition TEXT
)
BEGIN
  DECLARE column_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO column_exists
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'mfg_bom'
    AND column_name = column_name_input;
  IF column_exists = 0 THEN
    SET @phase2_mfg_sql = CONCAT(
      'ALTER TABLE `mfg_bom` ADD COLUMN `', column_name_input, '` ', column_definition
    );
    PREPARE phase2_mfg_statement FROM @phase2_mfg_sql;
    EXECUTE phase2_mfg_statement;
    DEALLOCATE PREPARE phase2_mfg_statement;
  END IF;
END//
DELIMITER ;

CALL phase2_add_mfg_bom_column('effective_from', 'DATE NULL');
CALL phase2_add_mfg_bom_column('effective_to', 'DATE NULL');
CALL phase2_add_mfg_bom_column('source_type', 'VARCHAR(64) NULL');
CALL phase2_add_mfg_bom_column('source_id', 'CHAR(36) NULL');
CALL phase2_add_mfg_bom_column('created_by', 'CHAR(36) NULL');
CALL phase2_add_mfg_bom_column('updated_by', 'CHAR(36) NULL');

UPDATE mfg_bom
SET effective_from = DATE(created_at)
WHERE effective_from IS NULL;
ALTER TABLE `mfg_bom` MODIFY COLUMN `effective_from` DATE NOT NULL;
DROP PROCEDURE IF EXISTS phase2_add_mfg_bom_column;

CREATE TABLE IF NOT EXISTS mfg_routing (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_routing_material (org_id, material_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_routing_operation (
  id CHAR(36) PRIMARY KEY,
  routing_id CHAR(36) NOT NULL,
  operation_name VARCHAR(128) NOT NULL,
  line_no INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
