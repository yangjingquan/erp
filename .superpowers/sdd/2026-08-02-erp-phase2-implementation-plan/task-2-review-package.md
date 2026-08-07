# Task 2 review package (Git unavailable)

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

- `database/init.sql` provisions the expanded schema for new environments. Existing deployed MySQL databases need the equivalent additive migration before this API can be used; no migration framework exists in the current project and none was introduced outside task scope.
- Automated tests use SQLite, so MySQL-specific JSON storage and row-lock concurrency semantics (`FOR UPDATE`) should be smoke-tested in the deployment database before concurrent production use.

## Changed-file snapshots

### backend/app/models/production.py
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, UUIDModel


class MfgBom(AuditMixin, UUIDModel):
    __tablename__ = "mfg_bom"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    bom_version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    items: Mapped[list["MfgBomItem"]] = relationship(
        back_populates="bom", cascade="all, delete-orphan", order_by="MfgBomItem.line_no"
    )


class MfgBomItem(AuditMixin, UUIDModel):
    __tablename__ = "mfg_bom_item"

    bom_id: Mapped[str] = mapped_column(ForeignKey("mfg_bom.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False, default=1)
    bom: Mapped[MfgBom] = relationship(back_populates="items")


class MfgMps(AuditMixin, UUIDModel):
    __tablename__ = "mfg_mps"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    plan_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    runs: Mapped[list["MfgMrpRun"]] = relationship(back_populates="mps")


class MfgMrpRun(AuditMixin, UUIDModel):
    __tablename__ = "mfg_mrp_run"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    mps_id: Mapped[str] = mapped_column(ForeignKey("mfg_mps.id"), nullable=False)
    bom_id: Mapped[str] = mapped_column(ForeignKey("mfg_bom.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    source_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    mps: Mapped[MfgMps] = relationship(back_populates="runs")
    results: Mapped[list["MfgMrpResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="MfgMrpResult.material_id"
    )


class MfgMrpResult(AuditMixin, UUIDModel):
    __tablename__ = "mfg_mrp_result"

    run_id: Mapped[str] = mapped_column(ForeignKey("mfg_mrp_run.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    gross_requirement: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    available_stock: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    open_supply_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    net_requirement: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confirmed_source_ids: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    run: Mapped[MfgMrpRun] = relationship(back_populates="results")

### backend/app/schemas/production.py
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class BomItemCreate(BaseModel):
    material_id: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)


class BomCreate(BaseModel):
    material_id: str = Field(min_length=1)
    bom_version: str = Field(default="1.0", min_length=1, max_length=32)
    effective_from: date
    effective_to: date | None = None
    source_type: str | None = Field(default=None, max_length=64)
    source_id: str | None = Field(default=None, max_length=36)
    items: list[BomItemCreate] = Field(min_length=1)


class MpsCreate(BaseModel):
    material_id: str = Field(min_length=1)
    warehouse_id: str | None = Field(default=None, min_length=1)
    plan_date: date
    plan_quantity: Decimal = Field(gt=0)
    source_type: str | None = Field(default=None, max_length=64)
    source_id: str | None = Field(default=None, max_length=36)

### backend/app/services/planning_service.py
from collections import OrderedDict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError
from app.models.inventory import InvStock
from app.models.master_data import MdMaterial
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

### backend/app/api/production.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
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
def create_bom_api(payload: BomCreate, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    bom = create_bom(db, payload, context)
    db.commit()
    return ok(serialize_bom(bom))


@router.get("/boms/{bom_id}")
def bom_detail(bom_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(serialize_bom(_get_bom(db, bom_id, context)))


@router.post("/boms/{bom_id}/submit")
def submit_bom_api(bom_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    bom = submit_bom(db, bom_id, context)
    db.commit()
    return ok(serialize_bom(bom))


@router.post("/boms/{bom_id}/approve")
def approve_bom_api(bom_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    bom = approve_bom(db, bom_id, context)
    db.commit()
    return ok(serialize_bom(bom))


@router.post("/boms/{bom_id}/disable")
def disable_bom_api(bom_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    bom = disable_bom(db, bom_id, context)
    db.commit()
    return ok(serialize_bom(bom))


@router.get("/mps")
def list_mps_api(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_mps(db, context))


@router.post("/mps")
def create_mps_api(payload: MpsCreate, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
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
def run_mrp_api(mps_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    run = run_mrp(db, mps_id, context)
    db.commit()
    return ok(serialize_mrp_run(run))


@router.get("/mrp-runs/{run_id}")
def mrp_run_detail(run_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(serialize_mrp_run(_get_mrp_run(db, run_id, context)))


@router.post("/mrp-results/{result_id}/confirm")
def confirm_mrp_result_api(result_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    confirmation = confirm_mrp_result(db, result_id, context)
    db.commit()
    return ok(confirmation)

### backend/tests/test_production_planning_phase2.py
from datetime import date
from decimal import Decimal

from app.core.security import create_access_token
from app.models.configuration import CfgNumberRule
from app.models.inventory import InvStock
from app.models.master_data import MdMaterial
from app.models.purchase import PurchaseOrder, PurchaseOrderItem


def headers():
    return {"Authorization": f"Bearer {create_access_token('user-1', ['production:manage'])}"}


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
    client, _ = client_and_session

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

### backend/app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.system import router as system_router
from app.api.master_data import router as master_data_router
from app.api.config import router as config_router
from app.api.workflow import router as workflow_router
from app.api.sales import router as sales_router
from app.api.purchase import router as purchase_router
from app.api.inventory import router as inventory_router
from app.api.finance import router as finance_router
from app.api.dashboard import router as dashboard_router
from app.api.search import router as search_router
from app.api.backup import router as backup_router
from app.api.admin import router as admin_router
from app.api.production import router as production_router
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.middleware.error_handler import register_exception_handlers
from app.middleware.request_context import RequestContextMiddleware
from app.services.startup_check import check_schema

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    db = SessionLocal()
    try:
        schema_status = check_schema(db)
        application.state.schema_status = schema_status
        if not schema_status.connected:
            logging.getLogger("erp.startup").warning(
                "MySQL unavailable: %s", schema_status.guidance
            )
        elif not schema_status.initialized:
            logging.getLogger("erp.startup").warning(schema_status.guidance)
        yield
    finally:
        db.close()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(system_router)
app.include_router(master_data_router)
app.include_router(config_router)
app.include_router(workflow_router)
app.include_router(sales_router)
app.include_router(purchase_router)
app.include_router(inventory_router)
app.include_router(finance_router)
app.include_router(dashboard_router)
app.include_router(search_router)
app.include_router(backup_router)
app.include_router(admin_router)
app.include_router(production_router)

### backend/app/models/__init__.py
"""SQLAlchemy model package."""

from app.models.business_extensions import (  # noqa: F401,E402
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseReturnItem,
    SalesQuote,
    SalesQuoteItem,
    SalesReturnItem,
)
from app.models.platform import ExtEventOutbox  # noqa: F401,E402
from app.models.production import MfgBom, MfgBomItem, MfgMps, MfgMrpResult, MfgMrpRun  # noqa: F401,E402

## SQL production references
930-  KEY idx_ext_event_outbox_claim_token (claim_token),
931-  KEY idx_ext_event_outbox_status_retry (status, next_retry_at)
932-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
933-
934:CREATE TABLE IF NOT EXISTS mfg_bom (
935-  id CHAR(36) PRIMARY KEY,
936-  org_id CHAR(36) NOT NULL,
937-  material_id CHAR(36) NOT NULL,
938-  bom_version VARCHAR(32) NOT NULL DEFAULT '1.0',
--
946-  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
947-  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
948-  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
949-  version INT NOT NULL DEFAULT 1,
950:  UNIQUE KEY uk_mfg_bom_material_version (org_id, material_id, bom_version)
951-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
952-
953:CREATE TABLE IF NOT EXISTS mfg_bom_item (
954-  id CHAR(36) PRIMARY KEY,
955-  bom_id CHAR(36) NOT NULL,
956-  material_id CHAR(36) NOT NULL,
957-  quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
--
959-  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
960-  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
961-  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
962-  version INT NOT NULL DEFAULT 1,
963:  KEY idx_mfg_bom_item_bom (bom_id)
964-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
965-
966:CREATE TABLE IF NOT EXISTS mfg_mps (
967-  id CHAR(36) PRIMARY KEY,
968-  org_id CHAR(36) NOT NULL,
969-  doc_no VARCHAR(64) NOT NULL,
970-  material_id CHAR(36) NOT NULL,
--
979-  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
980-  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
981-  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
982-  version INT NOT NULL DEFAULT 1,
983:  UNIQUE KEY uk_mfg_mps_doc_no (org_id, doc_no),
984:  KEY idx_mfg_mps_material_date (org_id, material_id, plan_date)
985-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
986-
987:CREATE TABLE IF NOT EXISTS mfg_mrp_run (
988-  id CHAR(36) PRIMARY KEY,
989-  org_id CHAR(36) NOT NULL,
990-  doc_no VARCHAR(64) NOT NULL,
991-  mps_id CHAR(36) NOT NULL,
--
996-  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
997-  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
998-  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
999-  version INT NOT NULL DEFAULT 1,
1000:  UNIQUE KEY uk_mfg_mrp_run_doc_no (org_id, doc_no),
1001:  KEY idx_mfg_mrp_run_mps (mps_id),
1002:  KEY idx_mfg_mrp_run_bom (bom_id)
1003-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1004-
1005:CREATE TABLE IF NOT EXISTS mfg_mrp_result (
1006-  id CHAR(36) PRIMARY KEY,
1007-  run_id CHAR(36) NOT NULL,
1008-  material_id CHAR(36) NOT NULL,
1009-  gross_requirement DECIMAL(18,6) NOT NULL,
--
1019-  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
1020-  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
1021-  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
1022-  version INT NOT NULL DEFAULT 1,
1023:  KEY idx_mfg_mrp_result_run (run_id),
1024:  KEY idx_mfg_mrp_result_material (material_id)
1025-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1026-
1027-CREATE TABLE IF NOT EXISTS mfg_routing (
1028-  id CHAR(36) PRIMARY KEY,
--
1047-  version INT NOT NULL DEFAULT 1,
1048-  KEY idx_mfg_routing_operation_routing (routing_id)
1049-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1050-
1051:CREATE TABLE IF NOT EXISTS mfg_work_order (
1052-  id CHAR(36) PRIMARY KEY,
1053-  org_id CHAR(36) NOT NULL,
1054-  doc_no VARCHAR(64) NOT NULL,
1055-  material_id CHAR(36) NOT NULL,
--
1058-  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
1059-  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
1060-  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
1061-  version INT NOT NULL DEFAULT 1,
1062:  UNIQUE KEY uk_mfg_work_order_doc_no (org_id, doc_no)
1063-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1064-
1065:CREATE TABLE IF NOT EXISTS mfg_work_order_material (
1066-  id CHAR(36) PRIMARY KEY,
1067-  work_order_id CHAR(36) NOT NULL,
1068-  material_id CHAR(36) NOT NULL,
1069-  required_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
--
1071-  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
1072-  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
1073-  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
1074-  version INT NOT NULL DEFAULT 1,
1075:  KEY idx_mfg_work_order_material_order (work_order_id)
1076-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1077-
1078-CREATE TABLE IF NOT EXISTS mfg_work_report (
1079-  id CHAR(36) PRIMARY KEY,
--
1118-  id CHAR(36) PRIMARY KEY,
1119-  org_id CHAR(36) NOT NULL,
1120-  material_id CHAR(36) NOT NULL,
1121-  batch_no VARCHAR(64) NOT NULL,
1122:  production_date DATE NULL,
1123-  expiry_date DATE NULL,
1124-  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
1125-  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
1126-  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
--
1362-('10000000-0000-0000-0000-000000000004', 'purchase:view', '采购管理', '/purchase', 'Purchase', 'menu', 30),
1363-('10000000-0000-0000-0000-000000000005', 'inventory:view', '库存管理', '/inventory', 'Inventory', 'menu', 40),
1364-('10000000-0000-0000-0000-000000000006', 'finance:view', '财务管理', '/finance', 'Finance', 'menu', 50),
1365-('10000000-0000-0000-0000-000000000007', 'system:view', '系统管理', '/system', 'System', 'menu', 90),
1366:('10000000-0000-0000-0000-000000000008', 'production:view', '生产管理', '/production', 'Production', 'menu', 35),
1367-('10000000-0000-0000-0000-000000000009', 'cost:view', '成本管理', '/cost', 'Cost', 'menu', 45),
1368-('10000000-0000-0000-0000-000000000010', 'crm:view', 'CRM', '/crm', 'Crm', 'menu', 25),
1369-('10000000-0000-0000-0000-000000000011', 'quality:view', '质量管理', '/quality', 'Quality', 'menu', 55),
1370-('10000000-0000-0000-0000-000000000012', 'hr:view', '人事管理', '/hr', 'Hr', 'menu', 60)
--
1398-('30000000-0000-0000-0000-000000000006', '00000000-0000-0000-0000-000000000001', 'sales_quote', 'QT', '%Y%m%d', 4, 'day'),
1399-('30000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000001', 'purchase_request', 'PRQ', '%Y%m%d', 4, 'day'),
1400-('30000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000001', 'purchase_return', 'PTR', '%Y%m%d', 4, 'day'),
1401-('30000000-0000-0000-0000-000000000009', '00000000-0000-0000-0000-000000000001', 'sales_return', 'STR', '%Y%m%d', 4, 'day'),
1402:('30000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'mfg_work_order', 'WO', '%Y%m%d', 4, 'day'),
1403-('30000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000001', 'qa_inspection', 'QI', '%Y%m%d', 4, 'day'),
1404:('30000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000001', 'mfg_mps', 'MPS', '%Y%m%d', 4, 'day'),
1405:('30000000-0000-0000-0000-000000000013', '00000000-0000-0000-0000-000000000001', 'mfg_mrp', 'MRP', '%Y%m%d', 4, 'day')
1406-ON DUPLICATE KEY UPDATE prefix = VALUES(prefix), date_format = VALUES(date_format), sequence_length = VALUES(sequence_length);
1407-
1408-INSERT INTO cfg_global_parameter (id, org_id, parameter_key, parameter_value, value_type, description)
1409-VALUES
--
1413-ON DUPLICATE KEY UPDATE parameter_value = VALUES(parameter_value), value_type = VALUES(value_type), description = VALUES(description);
1414-
1415-INSERT INTO ext_module_registry (id, module_key, module_name, phase, enabled)
1416-VALUES
1417:('40000000-0000-0000-0000-000000000001', 'production', '生产管理', 'phase2', 0),
1418-('40000000-0000-0000-0000-000000000002', 'crm', 'CRM', 'phase2', 0),
1419-('40000000-0000-0000-0000-000000000003', 'quality', '质量管理', 'phase2', 0),
1420-('40000000-0000-0000-0000-000000000004', 'hr', '人事考勤薪资', 'phase2', 0),
1421-('40000000-0000-0000-0000-000000000010', 'inventory_cost', '库存与成本', 'phase2', 0),
