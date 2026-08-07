# Task 3 review package (Git unavailable)
## Report
# Task 3 Report: Production Work Orders, Material Issue/Return, Reporting, and Completion

Date: 2026-08-02

## Status

Implemented the Task 3 production work-order flow in the requested workspace. No Git repository was initialized and no commit was created.

## Changed files

- `backend/app/models/production.py`
  - Added audited work-order, work-order-material, material-issue/return (and line), and work-report models.
  - Captures work-order BOM/plan snapshots and quantity/status fields.
- `backend/app/models/inventory.py`
  - Added named inventory source constants for production issue, return, and completion postings.
- `backend/app/models/__init__.py`
  - Exposes the new production models for metadata loading.
- `backend/app/schemas/production.py`
  - Added request schemas for work orders, material movements, returns, and reports.
- `backend/app/services/inventory_service.py`
  - Added the stock-cost lookup used by ledger-backed production postings.
- `backend/app/services/production_service.py`
  - Added creation, release, issue, return, report, completion, cancellation, serialization, audit logging, and completion-event handling.
- `backend/app/api/production.py`
  - Added permission-protected, unified-response work-order API endpoints.
- `backend/tests/test_work_order_phase2.py`
  - Added real FastAPI/service integration coverage for production flow, guardrails, return/cancellation, source traceability, audit records, and MPS source links.

## Behavior delivered

- Work-order lifecycle: `draft -> released -> in_progress -> completed`, plus cancellation from `released` or `in_progress`.
- Creation snapshots the approved effective BOM and planned quantity; optional source links use the established source-reference/org validation.
- Issue and return are constrained to BOM materials and issue/return quantities, update tracked material quantities, and post through `post_stock_transaction` with `mfg_material_issue` / `mfg_material_return` source records.
- Reporting validates positive good-plus-scrap quantity and prevents cumulative quantities from exceeding the work-order quantity.
- Completion posts finished goods through `post_stock_transaction` with `mfg_completion`, marks the work order complete, emits `work_order.completed` idempotently, and returns the existing completed work order on retry.
- All mutating actions write operation-audit entries. Routes require `production:manage` and retain the application’s `{code, msg, data}` response envelope.

## TDD evidence

### RED: missing work-order implementation

Command run from `backend`:

```bash
./.venv/bin/python -m pytest tests/test_work_order_phase2.py -q
```

Result before production implementation: `3 failed, 1 warning in 0.70s`.

All failures reached the missing public endpoint `POST /api/production/work-orders` and received HTTP 404. The test expectation then raised `KeyError: 'code'`; the absence of the endpoint was the intended feature-level failure.

### GREEN: production flow

Command run from `backend` after implementation:

```bash
./.venv/bin/python -m pytest tests/test_work_order_phase2.py -q
```

Result: `3 passed, 1 warning in 0.75s`.

### RED: validated source-link reuse

During review, a missing source-link behavior was found: work-order creation rejected even a valid MPS source. A real API test was added first.

Command run from `backend`:

```bash
./.venv/bin/python -m pytest tests/test_work_order_phase2.py::test_work_order_keeps_a_validated_mps_source_link -q
```

Result before the source-validation change: `1 failed, 1 warning in 0.28s`; the endpoint returned unified error code `400` rather than accepting the valid `mfg_mps` source.

The implementation then reused `planning_service._validate_source_reference`.

## Final verification

All commands below were run from `backend` using the required virtual environment.

```bash
./.venv/bin/python -m pytest tests/test_work_order_phase2.py -q
```

Result: `4 passed, 1 warning in 0.91s`.

```bash
./.venv/bin/python -m pytest tests/test_work_order_phase2.py tests/test_inventory_ledger.py -q
```

Result: `10 passed, 1 warning in 2.01s`.

```bash
./.venv/bin/python -m pytest -q
```

Result: `71 passed, 1 warning in 11.04s`.

```bash
./.venv/bin/python -m compileall -q app
```

Result: exit code `0`; no output.

The one warning in each pytest invocation is the existing FastAPI/Starlette TestClient deprecation warning about `httpx`; it is unrelated to Task 3.

## Self-review

- Verified all inventory mutations are made through `post_stock_transaction`; no direct inventory quantity changes occur in production services.
- Verified public route tests exercise authentication/permission dependencies, unified responses, ORM persistence, stock balances, ledger source records, audit rows, and outbox idempotency rather than mocks.
- Verified state checks reject material movement after cancellation and quantity checks reject over-BOM issue/report values.
- Verified a completion retry makes no second completion ledger transaction or event and returns the same work-order identity.
- Verified existing inventory ledger tests and the full backend suite remain green.

## Concerns

- The Task 3 file scope did not include `database/init.sql` or a migration. The existing SQL bootstrap defines only the earlier minimal work-order tables and does not include the newly modeled work-order columns or the material issue/return tables. SQLite integration tests create the SQLAlchemy metadata and pass; a production MySQL deployment needs a separately authorized schema migration/bootstrap update before these endpoints can run against an initialized database.
- The test environment emits the pre-existing TestClient deprecation warning noted above.

## backend/app/models/production.py
from datetime import date, datetime, timezone
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


class MfgWorkOrder(AuditMixin, UUIDModel):
    __tablename__ = "mfg_work_order"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    bom_id: Mapped[str] = mapped_column(String(36), nullable=False)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reported_good_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    reported_scrap_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    completed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    bom_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    materials: Mapped[list["MfgWorkOrderMaterial"]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan", order_by="MfgWorkOrderMaterial.line_no"
    )
    issues: Mapped[list["MfgMaterialIssue"]] = relationship(back_populates="work_order")
    reports: Mapped[list["MfgReport"]] = relationship(back_populates="work_order")


class MfgWorkOrderMaterial(AuditMixin, UUIDModel):
    __tablename__ = "mfg_work_order_material"

    work_order_id: Mapped[str] = mapped_column(ForeignKey("mfg_work_order.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    required_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    issued_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    returned_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False, default=1)
    work_order: Mapped[MfgWorkOrder] = relationship(back_populates="materials")


class MfgMaterialIssue(AuditMixin, UUIDModel):
    __tablename__ = "mfg_material_issue"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    work_order_id: Mapped[str] = mapped_column(ForeignKey("mfg_work_order.id"), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    work_order: Mapped[MfgWorkOrder] = relationship(back_populates="issues")
    items: Mapped[list["MfgMaterialIssueItem"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan", order_by="MfgMaterialIssueItem.line_no"
    )


class MfgMaterialIssueItem(AuditMixin, UUIDModel):
    __tablename__ = "mfg_material_issue_item"

    issue_id: Mapped[str] = mapped_column(ForeignKey("mfg_material_issue.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    returned_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False, default=1)
    issue: Mapped[MfgMaterialIssue] = relationship(back_populates="items")


class MfgMaterialReturn(AuditMixin, UUIDModel):
    __tablename__ = "mfg_material_return"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    work_order_id: Mapped[str] = mapped_column(ForeignKey("mfg_work_order.id"), nullable=False)
    issue_id: Mapped[str] = mapped_column(ForeignKey("mfg_material_issue.id"), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    items: Mapped[list["MfgMaterialReturnItem"]] = relationship(
        back_populates="material_return", cascade="all, delete-orphan", order_by="MfgMaterialReturnItem.line_no"
    )


class MfgMaterialReturnItem(AuditMixin, UUIDModel):
    __tablename__ = "mfg_material_return_item"

    return_id: Mapped[str] = mapped_column(ForeignKey("mfg_material_return.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False, default=1)
    material_return: Mapped[MfgMaterialReturn] = relationship(back_populates="items")


class MfgReport(AuditMixin, UUIDModel):
    __tablename__ = "mfg_work_report"

    work_order_id: Mapped[str] = mapped_column(ForeignKey("mfg_work_order.id"), nullable=False)
    good_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    scrap_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    report_time: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    work_order: Mapped[MfgWorkOrder] = relationship(back_populates="reports")

## backend/app/services/production_service.py
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError
from app.models.inventory import (
    MFG_COMPLETION_SOURCE,
    MFG_MATERIAL_ISSUE_SOURCE,
    MFG_MATERIAL_RETURN_SOURCE,
)
from app.models.master_data import MdMaterial
from app.models.production import (
    MfgMaterialIssue,
    MfgMaterialIssueItem,
    MfgMaterialReturn,
    MfgMaterialReturnItem,
    MfgReport,
    MfgWorkOrder,
    MfgWorkOrderMaterial,
)
from app.services.audit_service import write_operation_log
from app.services.auth_service import UserContext
from app.services.configuration_service import next_doc_no
from app.services.event_service import emit_event
from app.services.inventory_service import get_stock_unit_cost, post_stock_transaction
from app.services.planning_service import (
    _approved_bom_for_material,
    _require_material,
    _require_warehouse,
    _validate_source_reference,
)


QUANTITY_SCALE = Decimal("0.000001")


def _quantity(value: Decimal | int | str | None) -> Decimal:
    return Decimal(value or 0).quantize(QUANTITY_SCALE, rounding=ROUND_HALF_UP)


def _snapshot_quantity(value: Decimal) -> str:
    return format(_quantity(value).normalize(), "f") if value else "0"


def _serialize_material(row: MfgWorkOrderMaterial) -> dict:
    return {
        "material_id": row.material_id,
        "planned_quantity": f"{_quantity(row.required_quantity):.6f}",
        "issued_quantity": f"{_quantity(row.issued_quantity):.6f}",
        "returned_quantity": f"{_quantity(row.returned_quantity):.6f}",
    }


def serialize_work_order(row: MfgWorkOrder) -> dict:
    return {
        "id": row.id,
        "doc_no": row.doc_no,
        "material_id": row.material_id,
        "warehouse_id": row.warehouse_id,
        "bom_id": row.bom_id,
        "plan_date": row.plan_date.isoformat(),
        "quantity": f"{_quantity(row.quantity):.6f}",
        "status": row.status,
        "reported_good_quantity": f"{_quantity(row.reported_good_quantity):.6f}",
        "reported_scrap_quantity": f"{_quantity(row.reported_scrap_quantity):.6f}",
        "completed_quantity": f"{_quantity(row.completed_quantity):.6f}",
        "bom_snapshot": row.bom_snapshot,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "materials": [_serialize_material(item) for item in row.materials if not item.is_deleted],
    }


def serialize_issue(row: MfgMaterialIssue) -> dict:
    return {
        "id": row.id,
        "work_order_id": row.work_order_id,
        "warehouse_id": row.warehouse_id,
        "items": [
            {
                "material_id": item.material_id,
                "quantity": f"{_quantity(item.quantity):.6f}",
                "returned_quantity": f"{_quantity(item.returned_quantity):.6f}",
            }
            for item in row.items
            if not item.is_deleted
        ],
    }


def serialize_return(row: MfgMaterialReturn) -> dict:
    return {
        "id": row.id,
        "issue_id": row.issue_id,
        "work_order_id": row.work_order_id,
        "warehouse_id": row.warehouse_id,
        "items": [
            {"material_id": item.material_id, "quantity": f"{_quantity(item.quantity):.6f}"}
            for item in row.items
            if not item.is_deleted
        ],
    }


def serialize_report(row: MfgReport) -> dict:
    return {
        "id": row.id,
        "work_order_id": row.work_order_id,
        "good_quantity": f"{_quantity(row.good_quantity):.6f}",
        "scrap_quantity": f"{_quantity(row.scrap_quantity):.6f}",
        "hours": f"{_quantity(row.hours):.6f}",
        "report_time": row.report_time.isoformat(),
    }


def _get_work_order(db: Session, work_order_id: str, context: UserContext, *, lock: bool = False) -> MfgWorkOrder:
    statement = (
        select(MfgWorkOrder)
        .options(selectinload(MfgWorkOrder.materials))
        .where(
            MfgWorkOrder.id == work_order_id,
            MfgWorkOrder.org_id == context.org_id,
            MfgWorkOrder.is_deleted.is_(False),
        )
    )
    if lock:
        statement = statement.with_for_update()
    row = db.scalar(statement)
    if row is None:
        raise AppError("生产工单不存在", code=404)
    return row


def _require_allowed_status(row: MfgWorkOrder, action: str, allowed: set[str]) -> None:
    if row.status not in allowed:
        raise AppError(f"工单状态 {row.status} 不允许{action}", code=400)


def _validate_source(payload, db: Session, context: UserContext) -> None:
    _validate_source_reference(db, payload.source_type, payload.source_id, context)


def _ensure_distinct_items(items) -> None:
    material_ids = [item.material_id for item in items]
    if len(material_ids) != len(set(material_ids)):
        raise AppError("物料明细不能重复", code=400)


def create_work_order(db: Session, payload, context: UserContext) -> MfgWorkOrder:
    _require_material(db, payload.material_id, context)
    _require_warehouse(db, payload.warehouse_id, context)
    _validate_source(payload, db, context)
    bom = _approved_bom_for_material(db, context.org_id, payload.material_id, payload.plan_date)
    if bom is None:
        raise AppError("成品缺少有效的已审核 BOM 版本", code=400)
    quantity = _quantity(payload.quantity)
    snapshot_items = [
        {"material_id": item.material_id, "quantity": _snapshot_quantity(item.quantity)}
        for item in bom.items
        if not item.is_deleted
    ]
    row = MfgWorkOrder(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "mfg_work_order", context.org_id, payload.plan_date),
        material_id=payload.material_id,
        warehouse_id=payload.warehouse_id,
        bom_id=bom.id,
        plan_date=payload.plan_date,
        quantity=quantity,
        status="draft",
        bom_snapshot={
            "bom_id": bom.id,
            "bom_version": bom.bom_version,
            "plan_quantity": _snapshot_quantity(quantity),
            "items": snapshot_items,
        },
        source_type=payload.source_type,
        source_id=payload.source_id,
        created_by=context.id,
        updated_by=context.id,
    )
    row.materials = [
        MfgWorkOrderMaterial(
            material_id=item.material_id,
            required_quantity=_quantity(quantity * _quantity(item.quantity)),
            line_no=index,
        )
        for index, item in enumerate(bom.items, start=1)
        if not item.is_deleted
    ]
    db.add(row)
    db.flush()
    write_operation_log(db, user=context.user, action="create", resource="mfg_work_order", target_id=row.id)
    return row


def release_work_order(db: Session, work_order_id: str, context: UserContext) -> MfgWorkOrder:
    row = _get_work_order(db, work_order_id, context, lock=True)
    _require_allowed_status(row, "下达", {"draft"})
    row.status = "released"
    row.updated_by = context.id
    write_operation_log(db, user=context.user, action="release", resource="mfg_work_order", target_id=row.id)
    db.flush()
    return row


def issue_material(db: Session, work_order_id: str, items, context: UserContext) -> MfgMaterialIssue:
    row = _get_work_order(db, work_order_id, context, lock=True)
    _require_allowed_status(row, "领料", {"released", "in_progress"})
    _ensure_distinct_items(items)
    material_lines = {line.material_id: line for line in row.materials if not line.is_deleted}
    quantities = {item.material_id: _quantity(item.quantity) for item in items}
    for material_id, quantity in quantities.items():
        line = material_lines.get(material_id)
        if line is None:
            raise AppError("领料物料不在工单 BOM 快照中", code=400)
        if _quantity(line.issued_quantity + quantity) > _quantity(line.required_quantity):
            raise AppError("领料数量超过 BOM 计划数量", code=400)

    issue = MfgMaterialIssue(
        org_id=context.org_id,
        work_order_id=row.id,
        warehouse_id=row.warehouse_id,
        created_by=context.id,
    )
    db.add(issue)
    db.flush()
    for index, item in enumerate(items, start=1):
        quantity = quantities[item.material_id]
        unit_cost = get_stock_unit_cost(db, context, row.warehouse_id, item.material_id)
        issue.items.append(
            MfgMaterialIssueItem(
                material_id=item.material_id,
                quantity=quantity,
                unit_cost=unit_cost,
                line_no=index,
            )
        )
        post_stock_transaction(
            db,
            context,
            source_type=MFG_MATERIAL_ISSUE_SOURCE,
            source_id=issue.id,
            warehouse_id=row.warehouse_id,
            material_id=item.material_id,
            quantity=quantity,
            direction="out",
            unit_cost=unit_cost,
        )
        material_lines[item.material_id].issued_quantity = _quantity(
            material_lines[item.material_id].issued_quantity + quantity
        )
    row.status = "in_progress"
    row.updated_by = context.id
    write_operation_log(
        db, user=context.user, action="issue", resource="mfg_work_order", target_id=row.id, detail={"issue_id": issue.id}
    )
    db.flush()
    return issue


def return_material(db: Session, issue_id: str, items, context: UserContext) -> MfgMaterialReturn:
    issue = db.scalar(
        select(MfgMaterialIssue)
        .options(selectinload(MfgMaterialIssue.items))
        .where(MfgMaterialIssue.id == issue_id, MfgMaterialIssue.org_id == context.org_id, MfgMaterialIssue.is_deleted.is_(False))
        .with_for_update()
    )
    if issue is None:
        raise AppError("生产领料单不存在", code=404)
    row = _get_work_order(db, issue.work_order_id, context, lock=True)
    _require_allowed_status(row, "退料", {"released", "in_progress"})
    _ensure_distinct_items(items)
    issue_lines = {line.material_id: line for line in issue.items if not line.is_deleted}
    work_order_lines = {line.material_id: line for line in row.materials if not line.is_deleted}
    quantities = {item.material_id: _quantity(item.quantity) for item in items}
    for material_id, quantity in quantities.items():
        issue_line = issue_lines.get(material_id)
        if issue_line is None or _quantity(issue_line.returned_quantity + quantity) > _quantity(issue_line.quantity):
            raise AppError("退料数量超过原领料数量", code=400)

    material_return = MfgMaterialReturn(
        org_id=context.org_id,
        work_order_id=row.id,
        issue_id=issue.id,
        warehouse_id=row.warehouse_id,
        created_by=context.id,
    )
    db.add(material_return)
    db.flush()
    for index, item in enumerate(items, start=1):
        issue_line = issue_lines[item.material_id]
        quantity = quantities[item.material_id]
        material_return.items.append(
            MfgMaterialReturnItem(
                material_id=item.material_id,
                quantity=quantity,
                unit_cost=issue_line.unit_cost,
                line_no=index,
            )
        )
        post_stock_transaction(
            db,
            context,
            source_type=MFG_MATERIAL_RETURN_SOURCE,
            source_id=material_return.id,
            warehouse_id=row.warehouse_id,
            material_id=item.material_id,
            quantity=quantity,
            direction="in",
            unit_cost=issue_line.unit_cost,
        )
        issue_line.returned_quantity = _quantity(issue_line.returned_quantity + quantity)
        work_order_lines[item.material_id].returned_quantity = _quantity(
            work_order_lines[item.material_id].returned_quantity + quantity
        )
    row.updated_by = context.id
    write_operation_log(
        db, user=context.user, action="return", resource="mfg_work_order", target_id=row.id, detail={"return_id": material_return.id}
    )
    db.flush()
    return material_return


def report_work(db: Session, work_order_id: str, payload, context: UserContext) -> MfgReport:
    row = _get_work_order(db, work_order_id, context, lock=True)
    _require_allowed_status(row, "报工", {"released", "in_progress"})
    good_quantity = _quantity(payload.good_quantity)
    scrap_quantity = _quantity(payload.scrap_quantity)
    if good_quantity + scrap_quantity <= 0:
        raise AppError("合格数量和报废数量之和必须大于零", code=400)
    reported_total = _quantity(row.reported_good_quantity + row.reported_scrap_quantity + good_quantity + scrap_quantity)
    if reported_total > _quantity(row.quantity):
        raise AppError("报工数量超过工单计划数量", code=400)
    report = MfgReport(
        work_order_id=row.id,
        good_quantity=good_quantity,
        scrap_quantity=scrap_quantity,
        hours=_quantity(payload.hours),
        created_by=context.id,
    )
    db.add(report)
    row.reported_good_quantity = _quantity(row.reported_good_quantity + good_quantity)
    row.reported_scrap_quantity = _quantity(row.reported_scrap_quantity + scrap_quantity)
    row.status = "in_progress"
    row.updated_by = context.id
    db.flush()
    write_operation_log(
        db, user=context.user, action="report", resource="mfg_work_order", target_id=row.id, detail={"report_id": report.id}
    )
    return report


def complete_work_order(db: Session, work_order_id: str, context: UserContext) -> MfgWorkOrder:
    row = _get_work_order(db, work_order_id, context, lock=True)
    if row.status == "completed":
        return row
    _require_allowed_status(row, "完工", {"released", "in_progress"})
    completion_quantity = _quantity(row.reported_good_quantity - row.completed_quantity)
    if completion_quantity <= 0:
        raise AppError("工单没有可完工入库的合格数量", code=400)
    material = db.scalar(
        select(MdMaterial).where(
            MdMaterial.id == row.material_id,
            MdMaterial.org_id == context.org_id,
            MdMaterial.is_deleted.is_(False),
        )
    )
    if material is None:
        raise AppError("成品物料不存在或不属于当前组织", code=404)
    post_stock_transaction(
        db,
        context,
        source_type=MFG_COMPLETION_SOURCE,
        source_id=row.id,
        warehouse_id=row.warehouse_id,
        material_id=row.material_id,
        quantity=completion_quantity,
        direction="in",
        unit_cost=_quantity(material.standard_cost),
    )
    row.completed_quantity = _quantity(row.completed_quantity + completion_quantity)
    row.status = "completed"
    row.updated_by = context.id
    emit_event(
        db,
        "work_order.completed",
        "mfg_work_order",
        row.id,
        {"work_order_id": row.id, "quantity": f"{completion_quantity:.6f}"},
    )
    write_operation_log(db, user=context.user, action="complete", resource="mfg_work_order", target_id=row.id)
    db.flush()
    return row


def cancel_work_order(db: Session, work_order_id: str, context: UserContext) -> MfgWorkOrder:
    row = _get_work_order(db, work_order_id, context, lock=True)
    _require_allowed_status(row, "取消", {"released", "in_progress"})
    row.status = "cancelled"
    row.updated_by = context.id
    write_operation_log(db, user=context.user, action="cancel", resource="mfg_work_order", target_id=row.id)
    db.flush()
    return row

## backend/app/api/production.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.production import (
    BomCreate,
    MaterialIssueCreate,
    MaterialReturnCreate,
    MpsCreate,
    WorkOrderCreate,
    WorkReportCreate,
)
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
from app.services.production_service import (
    cancel_work_order,
    complete_work_order,
    create_work_order,
    issue_material,
    release_work_order,
    report_work,
    return_material,
    serialize_issue,
    serialize_report,
    serialize_return,
    serialize_work_order,
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


@router.post("/work-orders")
def create_work_order_api(payload: WorkOrderCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = create_work_order(db, payload, context)
    db.commit()
    return ok(serialize_work_order(row))


@router.post("/work-orders/{work_order_id}/release")
def release_work_order_api(work_order_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = release_work_order(db, work_order_id, context)
    db.commit()
    return ok(serialize_work_order(row))


@router.post("/work-orders/{work_order_id}/issue")
def issue_material_api(work_order_id: str, payload: MaterialIssueCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = issue_material(db, work_order_id, payload.items, context)
    db.commit()
    return ok(serialize_issue(row))


@router.post("/material-issues/{issue_id}/return")
def return_material_api(issue_id: str, payload: MaterialReturnCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = return_material(db, issue_id, payload.items, context)
    db.commit()
    return ok(serialize_return(row))


@router.post("/work-orders/{work_order_id}/reports")
def report_work_api(work_order_id: str, payload: WorkReportCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = report_work(db, work_order_id, payload, context)
    db.commit()
    return ok(serialize_report(row))


@router.post("/work-orders/{work_order_id}/complete")
def complete_work_order_api(work_order_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = complete_work_order(db, work_order_id, context)
    db.commit()
    return ok(serialize_work_order(row))


@router.post("/work-orders/{work_order_id}/cancel")
def cancel_work_order_api(work_order_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = cancel_work_order(db, work_order_id, context)
    db.commit()
    return ok(serialize_work_order(row))

## backend/app/schemas/production.py
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


class WorkOrderCreate(BaseModel):
    material_id: str = Field(min_length=1)
    warehouse_id: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    plan_date: date
    source_type: str | None = Field(default=None, max_length=64)
    source_id: str | None = Field(default=None, max_length=36)


class MaterialMovementItem(BaseModel):
    material_id: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)


class MaterialIssueCreate(BaseModel):
    items: list[MaterialMovementItem] = Field(min_length=1)


class MaterialReturnCreate(BaseModel):
    items: list[MaterialMovementItem] = Field(min_length=1)


class WorkReportCreate(BaseModel):
    good_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    scrap_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    hours: Decimal = Field(default=Decimal("0"), ge=0)

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
    {MFG_MATERIAL_ISSUE_SOURCE, MFG_MATERIAL_RETURN_SOURCE, MFG_COMPLETION_SOURCE}
)


def get_stock_unit_cost(
    db: Session, context: UserContext, warehouse_id: str, material_id: str
) -> Decimal:
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
) -> InvStockTransaction:
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
        source_type=source_type,
        source_id=source_id,
        direction=direction,
        quantity=quantity,
        unit_cost=unit_cost,
        amount=(quantity * unit_cost).quantize(Decimal("0.01")),
        created_by=context.id,
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
        "source_type": transaction.source_type,
        "source_id": transaction.source_id,
        "direction": transaction.direction,
        "quantity": str(transaction.quantity),
        "unit_cost": str(transaction.unit_cost),
        "amount": str(transaction.amount),
        "transaction_date": transaction.transaction_date.isoformat(),
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

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDModel


MFG_MATERIAL_ISSUE_SOURCE = "mfg_material_issue"
MFG_MATERIAL_RETURN_SOURCE = "mfg_material_return"
MFG_COMPLETION_SOURCE = "mfg_completion"


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

## backend/tests/test_work_order_phase2.py
from datetime import date
from decimal import Decimal

from app.core.security import create_access_token
from app.models.configuration import CfgNumberRule
from app.models.inventory import InvStock, InvStockTransaction
from app.models.logging import SysOperationLog
from app.models.master_data import MdMaterial, MdWarehouse
from app.models.platform import ExtEventOutbox
from app.models.production import MfgMps


def headers():
    return {"Authorization": f"Bearer {create_access_token('user-1', ['production:manage'])}"}


def seed_work_order_data(session):
    session.add_all(
        [
            CfgNumberRule(
                id="rule-mfg-work-order",
                org_id="org-1",
                rule_key="mfg_work_order",
                prefix="WO",
                date_format="%Y%m%d",
                sequence_length=4,
                reset_cycle="day",
            ),
            MdMaterial(id="finished-1", org_id="org-1", code="FG-1", name="Finished goods"),
            MdMaterial(id="component-1", org_id="org-1", code="CMP-1", name="Component"),
            MdWarehouse(id="warehouse-1", org_id="org-1", code="WH-1", name="Main warehouse"),
            InvStock(
                id="component-stock",
                org_id="org-1",
                warehouse_id="warehouse-1",
                material_id="component-1",
                quantity=Decimal("12"),
                available_quantity=Decimal("12"),
                average_cost=Decimal("3"),
            ),
        ]
    )
    session.commit()


def create_approved_bom(client):
    created = client.post(
        "/api/production/boms",
        json={
            "material_id": "finished-1",
            "bom_version": "1.0",
            "effective_from": "2026-08-01",
            "items": [{"material_id": "component-1", "quantity": "2"}],
        },
        headers=headers(),
    )
    bom_id = created.json()["data"]["id"]
    assert client.post(f"/api/production/boms/{bom_id}/submit", headers=headers()).json()["code"] == 0
    assert client.post(f"/api/production/boms/{bom_id}/approve", headers=headers()).json()["code"] == 0
    return bom_id


def create_released_work_order(client):
    created = client.post(
        "/api/production/work-orders",
        json={
            "material_id": "finished-1",
            "warehouse_id": "warehouse-1",
            "quantity": "5",
            "plan_date": "2026-08-02",
        },
        headers=headers(),
    )
    assert created.json()["code"] == 0
    work_order = created.json()["data"]
    assert work_order["status"] == "draft"
    assert work_order["bom_snapshot"]["items"] == [
        {"material_id": "component-1", "quantity": "2"}
    ]
    released = client.post(f"/api/production/work-orders/{work_order['id']}/release", headers=headers())
    assert released.json()["code"] == 0
    return released.json()["data"]


def test_work_order_issue_report_complete_updates_inventory_and_is_traceable(client_and_session):
    """Removing ledger posts or the completion event breaks the public production trace."""
    client, session = client_and_session
    seed_work_order_data(session)
    create_approved_bom(client)
    work_order = create_released_work_order(client)

    issue = client.post(
        f"/api/production/work-orders/{work_order['id']}/issue",
        json={"items": [{"material_id": "component-1", "quantity": "10"}]},
        headers=headers(),
    )
    assert issue.json()["code"] == 0
    report = client.post(
        f"/api/production/work-orders/{work_order['id']}/reports",
        json={"good_quantity": "5", "scrap_quantity": "0", "hours": "3"},
        headers=headers(),
    )
    assert report.json()["code"] == 0
    completed = client.post(f"/api/production/work-orders/{work_order['id']}/complete", headers=headers())

    assert completed.json()["code"] == 0
    assert completed.json()["data"]["status"] == "completed"
    assert session.query(InvStockTransaction).filter_by(
        source_type="mfg_material_issue", source_id=issue.json()["data"]["id"]
    ).count() == 1
    assert session.query(InvStockTransaction).filter_by(
        source_type="mfg_completion", source_id=work_order["id"]
    ).count() == 1
    assert session.get(InvStock, "component-stock").quantity == Decimal("2.000000")
    finished_stock = session.query(InvStock).filter_by(
        org_id="org-1", warehouse_id="warehouse-1", material_id="finished-1"
    ).one()
    assert finished_stock.quantity == Decimal("5.000000")
    assert session.query(ExtEventOutbox).filter_by(
        event_type="work_order.completed", aggregate_id=work_order["id"]
    ).count() == 1
    assert session.query(SysOperationLog).filter_by(resource="mfg_work_order", target_id=work_order["id"]).count() >= 4


def test_work_order_rejects_issue_over_bom_quantity_and_double_completion(client_and_session):
    """Permitting excess component consumption or repeated completion corrupts quantities and stock."""
    client, session = client_and_session
    seed_work_order_data(session)
    create_approved_bom(client)
    work_order = create_released_work_order(client)

    over_issue = client.post(
        f"/api/production/work-orders/{work_order['id']}/issue",
        json={"items": [{"material_id": "component-1", "quantity": "11"}]},
        headers=headers(),
    )
    report = client.post(
        f"/api/production/work-orders/{work_order['id']}/reports",
        json={"good_quantity": "5", "scrap_quantity": "0", "hours": "3"},
        headers=headers(),
    )
    first_completion = client.post(f"/api/production/work-orders/{work_order['id']}/complete", headers=headers())
    second_completion = client.post(f"/api/production/work-orders/{work_order['id']}/complete", headers=headers())

    assert over_issue.json()["code"] == 400
    assert report.json()["code"] == 0
    assert first_completion.json()["code"] == 0
    assert second_completion.json()["code"] == 0
    assert second_completion.json()["data"]["id"] == first_completion.json()["data"]["id"]
    assert session.query(InvStockTransaction).filter_by(
        source_type="mfg_completion", source_id=work_order["id"]
    ).count() == 1


def test_work_order_return_restores_stock_and_released_order_can_be_cancelled(client_and_session):
    """A return must be ledger-backed, and cancelled work orders must reject further material movement."""
    client, session = client_and_session
    seed_work_order_data(session)
    create_approved_bom(client)
    work_order = create_released_work_order(client)
    issue = client.post(
        f"/api/production/work-orders/{work_order['id']}/issue",
        json={"items": [{"material_id": "component-1", "quantity": "4"}]},
        headers=headers(),
    )
    returned = client.post(
        f"/api/production/material-issues/{issue.json()['data']['id']}/return",
        json={"items": [{"material_id": "component-1", "quantity": "1"}]},
        headers=headers(),
    )
    cancelled = client.post(f"/api/production/work-orders/{work_order['id']}/cancel", headers=headers())
    issue_after_cancel = client.post(
        f"/api/production/work-orders/{work_order['id']}/issue",
        json={"items": [{"material_id": "component-1", "quantity": "1"}]},
        headers=headers(),
    )

    assert returned.json()["code"] == 0
    assert session.query(InvStockTransaction).filter_by(
        source_type="mfg_material_return", source_id=returned.json()["data"]["id"]
    ).count() == 1
    assert session.get(InvStock, "component-stock").quantity == Decimal("9.000000")
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert issue_after_cancel.json()["code"] == 400


def test_work_order_keeps_a_validated_mps_source_link(client_and_session):
    """Removing source ownership validation must reject a linked planning document instead of silently accepting it."""
    client, session = client_and_session
    seed_work_order_data(session)
    create_approved_bom(client)
    session.add(
        MfgMps(
            id="mps-source-1",
            org_id="org-1",
            doc_no="MPS-SOURCE-1",
            material_id="finished-1",
            warehouse_id="warehouse-1",
            plan_date=date(2026, 8, 2),
            plan_quantity=Decimal("5"),
        )
    )
    session.commit()

    created = client.post(
        "/api/production/work-orders",
        json={
            "material_id": "finished-1",
            "warehouse_id": "warehouse-1",
            "quantity": "5",
            "plan_date": "2026-08-02",
            "source_type": "mfg_mps",
            "source_id": "mps-source-1",
        },
        headers=headers(),
    )

    assert created.json()["code"] == 0
    assert created.json()["data"]["source_type"] == "mfg_mps"
    assert created.json()["data"]["source_id"] == "mps-source-1"
## SQL phase2 production tail
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
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_routing_operation_routing (routing_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_work_order (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_work_order_doc_no (org_id, doc_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_work_order_material (
  id CHAR(36) PRIMARY KEY,
  work_order_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  required_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  issued_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_work_order_material_order (work_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_work_report (
  id CHAR(36) PRIMARY KEY,
  work_order_id CHAR(36) NOT NULL,
  reported_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  report_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_work_report_order (work_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_zone (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_inv_zone_code (warehouse_id, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_location (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  zone_id CHAR(36) NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_inv_location_code (warehouse_id, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_batch (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  batch_no VARCHAR(64) NOT NULL,
  production_date DATE NULL,
  expiry_date DATE NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_inv_batch_material_no (org_id, material_id, batch_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_cost_layer (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  source_type VARCHAR(64) NOT NULL,
  source_id CHAR(36) NOT NULL,
  remaining_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  unit_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_inv_cost_layer_material (org_id, material_id, warehouse_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cost_period_close (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  period VARCHAR(16) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'open',
  closed_at DATETIME(6) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
