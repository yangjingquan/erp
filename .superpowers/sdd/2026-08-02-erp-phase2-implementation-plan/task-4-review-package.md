# Task 4 review package (Git unavailable)
## Report
# Task 4 Report — 委外订单、委外发料和收货应付来源

## Status

Completed in `/Users/yangjingquan/Documents/ERP`. No Git operation, initialization, commit, or push was performed, per instruction.

## Delivered behavior

- Added subcontract order and receipt persistence with `draft → released → partially_received/completed` lifecycle and a terminal `cancelled` state before receipt.
- Added protected production API routes for creating, releasing, cancelling, issuing subcontract material, and receiving subcontract goods.
- Reused `post_stock_transaction` and `get_stock_unit_cost`; no duplicate inventory implementation was introduced.
- Reused finance payables by adding the idempotent `create_payable_from_subcontract_receipt` source adapter; payables preserve `source_type="subcontract_receipt"` and receipt ID.
- Preserved source tracing: subcontract orders, material issues, receipts, ledger transactions, and payables retain `source_type`/`source_id` relationships.
- Validated production permission and same-organization supplier, product material, issue material, warehouse, and source references.
- Added repeatable MySQL bootstrap tables, guarded Task 4 column upgrades, nullable legacy `mfg_material_issue.work_order_id` migration, and default number rules.

## Changed files

- `backend/app/models/production.py`
- `backend/app/models/inventory.py`
- `backend/app/models/__init__.py`
- `backend/app/schemas/production.py`
- `backend/app/api/production.py`
- `backend/app/services/production_service.py`
- `backend/app/services/finance_service.py`
- `backend/app/services/inventory_service.py`
- `backend/app/services/startup_check.py`
- `backend/tests/test_subcontract_phase2.py`
- `database/init.sql`

## TDD evidence

### RED

1. Initial command run from `backend/` used the instructed interpreter path incorrectly:

   ```text
   backend/.venv/bin/python -m pytest tests/test_subcontract_phase2.py -q
   zsh:1: no such file or directory: backend/.venv/bin/python
   ```

   The interpreter path is workspace-root relative, so the test command was rerun from the workspace root.

2. The new lifecycle, permission/org, and bootstrap tests were written before subcontract production code:

   ```text
   backend/.venv/bin/python -m pytest backend/tests/test_subcontract_phase2.py -q
   3 failed, 1 warning in 0.44s
   ```

   Expected failures were missing `/api/production/subcontract-orders` routes (404) and absent subcontract SQL tables/procedure.

3. The cancellation test was added before the cancellation route/service:

   ```text
   backend/.venv/bin/python -m pytest backend/tests/test_subcontract_phase2.py::test_subcontract_order_can_be_cancelled_before_receipt -q
   1 failed, 1 warning in 0.26s
   ```

   It failed because `/cancel` did not exist (404) and a post-cancellation issue was still accepted.

### GREEN

1. After the initial implementation:

   ```text
   backend/.venv/bin/python -m pytest backend/tests/test_subcontract_phase2.py -q
   3 passed, 1 warning in 0.44s
   ```

2. After the test-first cancellation implementation:

   ```text
   backend/.venv/bin/python -m pytest backend/tests/test_subcontract_phase2.py -q
   4 passed, 1 warning in 0.62s
   ```

The permission test was corrected to assert the project’s existing unified error payload (`{"code": 403}`) rather than HTTP status, matching existing production permission tests. This was test assertion alignment, not a production behavior change.

## Verification commands and results

```text
backend/.venv/bin/python -m pytest backend/tests/test_subcontract_phase2.py backend/tests/test_finance_flow.py backend/tests/test_inventory_ledger.py backend/tests/test_work_order_phase2.py backend/tests/test_production_planning_phase2.py -q
32 passed, 1 warning in 5.47s
```

```text
backend/.venv/bin/python -m pytest backend/tests -q
79 passed, 1 warning in 11.81s
```

```text
backend/.venv/bin/python -m compileall -q backend/app backend/tests
exit code 0; no output
```

All pytest runs emitted the pre-existing Starlette TestClient deprecation warning for `httpx`; no test failures or errors remained.

## Self-review

- The subcontract issue uses the established `MfgMaterialIssue` and `MfgMaterialIssueItem` records, with `subcontract_order_id` and source references, rather than duplicating material-movement data structures.
- Stock movements are posted only through the existing inventory ledger service and use distinct `subcontract_material_issue` and `subcontract_receipt` source types.
- Receipt payables are idempotent by receipt source and use only the subcontract processing-fee allocation; inventory receipt unit cost is not treated as an extra payable amount.
- Partial receipts prorate processing fees; the final receipt receives the residual to avoid rounding drift.
- Releasing, issuing the same subcontract order, receiving the same quantity/unit-cost payload, generating a payable, and cancelling an already-cancelled eligible order are idempotent.
- New write routes use the established `production:manage` dependency and responses use `ok(...)`, preserving the unified response envelope.
- No FIFO, CRM, quality, HR, frontend, or cost functionality was added.

## Concerns

- Cancellation is deliberately allowed only before any receipt (`draft` or `released`). Cancelling a partially received order would require explicit inventory/payable reversal documents and is outside Task 4’s minimal no-cost scope.
- Receipt idempotency is determined by order plus identical `good_quantity` and `unit_cost`, because the supplied interface contains no explicit idempotency key. A future API that needs two genuinely identical partial receipts should add a client operation key.
- The repeatable MySQL bootstrap includes `ALTER TABLE mfg_material_issue MODIFY COLUMN work_order_id ... NULL`; it is safe to re-run on MySQL but should be applied during a normal migration window for production lock management.

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


class MfgSubcontractOrder(AuditMixin, UUIDModel):
    __tablename__ = "mfg_subcontract_order"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    processing_fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    issues: Mapped[list["MfgMaterialIssue"]] = relationship(back_populates="subcontract_order")
    receipts: Mapped[list["MfgSubcontractReceipt"]] = relationship(
        back_populates="subcontract_order", order_by="MfgSubcontractReceipt.created_at"
    )


class MfgMaterialIssue(AuditMixin, UUIDModel):
    __tablename__ = "mfg_material_issue"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    work_order_id: Mapped[str | None] = mapped_column(ForeignKey("mfg_work_order.id"), nullable=True)
    subcontract_order_id: Mapped[str | None] = mapped_column(ForeignKey("mfg_subcontract_order.id"), nullable=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    work_order: Mapped[MfgWorkOrder | None] = relationship(back_populates="issues")
    subcontract_order: Mapped[MfgSubcontractOrder | None] = relationship(back_populates="issues")
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


class MfgSubcontractReceipt(AuditMixin, UUIDModel):
    __tablename__ = "mfg_subcontract_receipt"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    subcontract_order_id: Mapped[str] = mapped_column(ForeignKey("mfg_subcontract_order.id"), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    good_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    processing_fee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    subcontract_order: Mapped[MfgSubcontractOrder] = relationship(back_populates="receipts")


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
    SUBCONTRACT_MATERIAL_ISSUE_SOURCE,
    SUBCONTRACT_RECEIPT_SOURCE,
)
from app.models.master_data import MdMaterial, MdSupplier
from app.models.production import (
    MfgMaterialIssue,
    MfgMaterialIssueItem,
    MfgMaterialReturn,
    MfgMaterialReturnItem,
    MfgReport,
    MfgSubcontractOrder,
    MfgSubcontractReceipt,
    MfgWorkOrder,
    MfgWorkOrderMaterial,
)
from app.services.audit_service import write_operation_log
from app.services.auth_service import UserContext
from app.services.configuration_service import next_doc_no
from app.services.event_service import emit_event
from app.services.finance_service import create_payable_from_subcontract_receipt
from app.services.inventory_service import get_stock_unit_cost, post_stock_transaction
from app.services.planning_service import (
    _approved_bom_for_material,
    _require_material,
    _require_warehouse,
    _validate_source_reference,
)


QUANTITY_SCALE = Decimal("0.000001")
MONEY_SCALE = Decimal("0.01")


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
        "subcontract_order_id": row.subcontract_order_id,
        "warehouse_id": row.warehouse_id,
        "source_type": row.source_type,
        "source_id": row.source_id,
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


def serialize_subcontract_order(row: MfgSubcontractOrder) -> dict:
    return {
        "id": row.id,
        "doc_no": row.doc_no,
        "supplier_id": row.supplier_id,
        "material_id": row.material_id,
        "warehouse_id": row.warehouse_id,
        "plan_date": row.plan_date.isoformat(),
        "quantity": f"{_quantity(row.quantity):.6f}",
        "received_quantity": f"{_quantity(row.received_quantity):.6f}",
        "processing_fee": f"{Decimal(row.processing_fee).quantize(MONEY_SCALE):.2f}",
        "status": row.status,
        "source_type": row.source_type,
        "source_id": row.source_id,
    }


def serialize_subcontract_receipt(row: MfgSubcontractReceipt) -> dict:
    return {
        "id": row.id,
        "doc_no": row.doc_no,
        "subcontract_order_id": row.subcontract_order_id,
        "warehouse_id": row.warehouse_id,
        "material_id": row.material_id,
        "good_quantity": f"{_quantity(row.good_quantity):.6f}",
        "unit_cost": f"{_quantity(row.unit_cost):.6f}",
        "processing_fee_amount": f"{Decimal(row.processing_fee_amount).quantize(MONEY_SCALE):.2f}",
        "status": row.status,
        "source_type": row.source_type,
        "source_id": row.source_id,
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


def _get_subcontract_order(
    db: Session, order_id: str, context: UserContext, *, lock: bool = False
) -> MfgSubcontractOrder:
    statement = select(MfgSubcontractOrder).where(
        MfgSubcontractOrder.id == order_id,
        MfgSubcontractOrder.org_id == context.org_id,
        MfgSubcontractOrder.is_deleted.is_(False),
    )
    if lock:
        statement = statement.with_for_update()
    row = db.scalar(statement)
    if row is None:
        raise AppError("委外订单不存在", code=404)
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


def _require_supplier(db: Session, supplier_id: str, context: UserContext) -> None:
    supplier = db.scalar(
        select(MdSupplier).where(
            MdSupplier.id == supplier_id,
            MdSupplier.org_id == context.org_id,
            MdSupplier.is_deleted.is_(False),
        )
    )
    if supplier is None:
        raise AppError("供应商不存在或不属于当前组织", code=404)


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


def create_subcontract_order(db: Session, payload, context: UserContext) -> MfgSubcontractOrder:
    _require_supplier(db, payload.supplier_id, context)
    _require_material(db, payload.material_id, context)
    _require_warehouse(db, payload.warehouse_id, context)
    _validate_source(payload, db, context)
    quantity = _quantity(payload.quantity)
    processing_fee = Decimal(payload.processing_fee).quantize(MONEY_SCALE, rounding=ROUND_HALF_UP)
    if quantity <= 0 or processing_fee <= 0:
        raise AppError("委外数量和加工费必须大于零", code=400)
    row = MfgSubcontractOrder(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "mfg_subcontract_order", context.org_id, payload.plan_date),
        supplier_id=payload.supplier_id,
        material_id=payload.material_id,
        warehouse_id=payload.warehouse_id,
        plan_date=payload.plan_date,
        quantity=quantity,
        processing_fee=processing_fee,
        status="draft",
        source_type=payload.source_type,
        source_id=payload.source_id,
        created_by=context.id,
        updated_by=context.id,
    )
    db.add(row)
    db.flush()
    write_operation_log(db, user=context.user, action="create", resource="mfg_subcontract_order", target_id=row.id)
    return row


def release_subcontract_order(db: Session, order_id: str, context: UserContext) -> MfgSubcontractOrder:
    row = _get_subcontract_order(db, order_id, context, lock=True)
    if row.status in {"released", "partially_received", "completed"}:
        return row
    if row.status != "draft":
        raise AppError(f"委外订单状态 {row.status} 不允许下达", code=400)
    row.status = "released"
    row.updated_by = context.id
    write_operation_log(db, user=context.user, action="release", resource="mfg_subcontract_order", target_id=row.id)
    db.flush()
    return row


def cancel_subcontract_order(db: Session, order_id: str, context: UserContext) -> MfgSubcontractOrder:
    row = _get_subcontract_order(db, order_id, context, lock=True)
    if row.status == "cancelled":
        return row
    if row.status not in {"draft", "released"}:
        raise AppError(f"委外订单状态 {row.status} 不允许取消", code=400)
    row.status = "cancelled"
    row.updated_by = context.id
    write_operation_log(db, user=context.user, action="cancel", resource="mfg_subcontract_order", target_id=row.id)
    db.flush()
    return row


def issue_subcontract_material(db: Session, order_id: str, items, context: UserContext) -> MfgMaterialIssue:
    existing = db.scalar(
        select(MfgMaterialIssue)
        .options(selectinload(MfgMaterialIssue.items))
        .where(
            MfgMaterialIssue.subcontract_order_id == order_id,
            MfgMaterialIssue.org_id == context.org_id,
            MfgMaterialIssue.is_deleted.is_(False),
        )
    )
    if existing is not None:
        return existing
    row = _get_subcontract_order(db, order_id, context, lock=True)
    if row.status not in {"released", "partially_received"}:
        raise AppError(f"委外订单状态 {row.status} 不允许发料", code=400)
    _ensure_distinct_items(items)
    quantities = {item.material_id: _quantity(item.quantity) for item in items}
    for material_id, quantity in quantities.items():
        _require_material(db, material_id, context)
        if quantity <= 0:
            raise AppError("委外发料数量必须大于零", code=400)
    issue = MfgMaterialIssue(
        org_id=context.org_id,
        subcontract_order_id=row.id,
        warehouse_id=row.warehouse_id,
        source_type="mfg_subcontract_order",
        source_id=row.id,
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
            source_type=SUBCONTRACT_MATERIAL_ISSUE_SOURCE,
            source_id=issue.id,
            warehouse_id=row.warehouse_id,
            material_id=item.material_id,
            quantity=quantity,
            direction="out",
            unit_cost=unit_cost,
        )
    row.updated_by = context.id
    write_operation_log(
        db, user=context.user, action="issue", resource="mfg_subcontract_order", target_id=row.id, detail={"issue_id": issue.id}
    )
    db.flush()
    return issue


def receive_subcontract_order(db: Session, order_id: str, payload, context: UserContext) -> MfgSubcontractReceipt:
    good_quantity = _quantity(payload.good_quantity)
    unit_cost = _quantity(payload.unit_cost)
    existing = db.scalar(
        select(MfgSubcontractReceipt).where(
            MfgSubcontractReceipt.subcontract_order_id == order_id,
            MfgSubcontractReceipt.org_id == context.org_id,
            MfgSubcontractReceipt.good_quantity == good_quantity,
            MfgSubcontractReceipt.unit_cost == unit_cost,
            MfgSubcontractReceipt.is_deleted.is_(False),
        )
    )
    if existing is not None:
        return existing
    row = _get_subcontract_order(db, order_id, context, lock=True)
    if row.status not in {"released", "partially_received"}:
        raise AppError(f"委外订单状态 {row.status} 不允许收货", code=400)
    if good_quantity <= 0 or unit_cost <= 0:
        raise AppError("委外收货数量和单价必须大于零", code=400)
    if _quantity(row.received_quantity + good_quantity) > _quantity(row.quantity):
        raise AppError("委外收货数量超过订单数量", code=400)
    allocated_fee = (Decimal(row.processing_fee) * good_quantity / Decimal(row.quantity)).quantize(
        MONEY_SCALE, rounding=ROUND_HALF_UP
    )
    if _quantity(row.received_quantity + good_quantity) == _quantity(row.quantity):
        allocated_fee = Decimal(row.processing_fee) - sum(
            db.scalars(
                select(MfgSubcontractReceipt.processing_fee_amount).where(
                    MfgSubcontractReceipt.subcontract_order_id == row.id,
                    MfgSubcontractReceipt.org_id == context.org_id,
                    MfgSubcontractReceipt.is_deleted.is_(False),
                )
            )
        )
    receipt = MfgSubcontractReceipt(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "mfg_subcontract_receipt", context.org_id, row.plan_date),
        subcontract_order_id=row.id,
        warehouse_id=row.warehouse_id,
        material_id=row.material_id,
        good_quantity=good_quantity,
        unit_cost=unit_cost,
        processing_fee_amount=allocated_fee,
        status="completed",
        source_type="mfg_subcontract_order",
        source_id=row.id,
        created_by=context.id,
    )
    db.add(receipt)
    db.flush()
    post_stock_transaction(
        db,
        context,
        source_type=SUBCONTRACT_RECEIPT_SOURCE,
        source_id=receipt.id,
        warehouse_id=row.warehouse_id,
        material_id=row.material_id,
        quantity=good_quantity,
        direction="in",
        unit_cost=unit_cost,
    )
    row.received_quantity = _quantity(row.received_quantity + good_quantity)
    row.status = "completed" if row.received_quantity == _quantity(row.quantity) else "partially_received"
    row.updated_by = context.id
    create_payable_from_subcontract_receipt(db, receipt.id, context)
    write_operation_log(
        db, user=context.user, action="receive", resource="mfg_subcontract_order", target_id=row.id, detail={"receipt_id": receipt.id}
    )
    db.flush()
    return receipt


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

## backend/app/services/finance_service.py
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.finance import (
    FinExpense,
    FinReceipt,
    FinReceiptReconcile,
    FinPayment,
    FinVoucher,
    FinVoucherEntry,
    PurchasePayable,
    SalesReceivable,
)
from app.models.purchase import PurchaseReceipt
from app.models.production import MfgSubcontractReceipt
from app.models.sales import SalesDelivery
from app.services.auth_service import UserContext


def create_receivable_from_sales_delivery(db: Session, delivery_id: str, context: UserContext) -> SalesReceivable:
    delivery = db.get(SalesDelivery, delivery_id)
    if delivery is None or delivery.org_id != context.org_id:
        raise AppError("销售出库单不存在", code=404)
    existing = db.scalar(select(SalesReceivable).where(SalesReceivable.source_type == "sales_delivery", SalesReceivable.source_id == delivery.id))
    if existing:
        return existing
    receivable = SalesReceivable(
        org_id=context.org_id,
        doc_no=f"AR-{delivery.doc_no}",
        customer_id=delivery.customer_id,
        source_type="sales_delivery",
        source_id=delivery.id,
        total_amount=delivery.total_amount,
        status="open",
    )
    db.add(receivable)
    db.flush()
    return receivable


def create_payable_from_purchase_receipt(db: Session, receipt_id: str, context: UserContext) -> PurchasePayable:
    receipt = db.get(PurchaseReceipt, receipt_id)
    if receipt is None or receipt.org_id != context.org_id:
        raise AppError("采购入库单不存在", code=404)
    existing = db.scalar(select(PurchasePayable).where(PurchasePayable.source_type == "purchase_receipt", PurchasePayable.source_id == receipt.id))
    if existing:
        return existing
    payable = PurchasePayable(
        org_id=context.org_id,
        doc_no=f"AP-{receipt.doc_no}",
        supplier_id=receipt.supplier_id,
        source_type="purchase_receipt",
        source_id=receipt.id,
        total_amount=receipt.total_amount,
        status="open",
    )
    db.add(payable)
    db.flush()
    return payable


def create_payable_from_subcontract_receipt(
    db: Session, receipt_id: str, context: UserContext
) -> PurchasePayable:
    receipt = db.get(MfgSubcontractReceipt, receipt_id)
    if receipt is None or receipt.org_id != context.org_id:
        raise AppError("委外收货单不存在", code=404)
    existing = db.scalar(
        select(PurchasePayable).where(
            PurchasePayable.source_type == "subcontract_receipt", PurchasePayable.source_id == receipt.id
        )
    )
    if existing:
        return existing
    payable = PurchasePayable(
        org_id=context.org_id,
        doc_no=f"AP-{receipt.doc_no}",
        supplier_id=receipt.subcontract_order.supplier_id,
        source_type="subcontract_receipt",
        source_id=receipt.id,
        total_amount=receipt.processing_fee_amount,
        status="open",
    )
    db.add(payable)
    db.flush()
    return payable


def create_receipt(db: Session, context: UserContext, *, customer_id: str, amount: Decimal) -> FinReceipt:
    if amount <= 0:
        raise AppError("收款金额必须大于 0", code=400)
    receipt = FinReceipt(
        org_id=context.org_id,
        doc_no=f"RC-{context.id[:8]}-{date.today().strftime('%Y%m%d%H%M%S%f')}",
        customer_id=customer_id,
        amount=amount,
        receipt_date=date.today(),
        status="confirmed",
    )
    db.add(receipt)
    db.flush()
    return receipt


def reconcile_receivable(db: Session, receipt_id: str, receivable_id: str, amount: Decimal, context: UserContext) -> None:
    receipt = db.get(FinReceipt, receipt_id)
    receivable = db.get(SalesReceivable, receivable_id)
    if receipt is None or receivable is None or receipt.org_id != context.org_id or receivable.org_id != context.org_id:
        raise AppError("收款或应收单不存在", code=404)
    if amount <= 0 or amount > receivable.total_amount - receivable.reconciled_amount or amount > receipt.amount - sum(item.amount for item in receipt.reconciles):
        raise AppError("核销金额超过可核销余额", code=400)
    db.add(FinReceiptReconcile(receipt_id=receipt.id, receivable_id=receivable.id, amount=amount))
    receivable.reconciled_amount += amount
    receivable.status = "settled" if receivable.reconciled_amount == receivable.total_amount else "partial"
    db.flush()


def create_payment(db: Session, context: UserContext, *, supplier_id: str, amount: Decimal) -> FinPayment:
    if amount <= 0:
        raise AppError("付款金额必须大于 0", code=400)
    payment = FinPayment(
        org_id=context.org_id,
        doc_no=f"PY-{context.id[:8]}-{date.today().strftime('%Y%m%d%H%M%S%f')}",
        supplier_id=supplier_id,
        amount=amount,
        payment_date=date.today(),
        status="confirmed",
    )
    db.add(payment)
    db.flush()
    return payment


def reconcile_payable(db: Session, payment_id: str, payable_id: str, amount: Decimal, context: UserContext) -> None:
    payment = db.get(FinPayment, payment_id)
    payable = db.get(PurchasePayable, payable_id)
    if payment is None or payable is None or payment.org_id != context.org_id or payable.org_id != context.org_id:
        raise AppError("付款或应付单不存在", code=404)
    if amount <= 0 or amount > payable.total_amount - payable.reconciled_amount:
        raise AppError("核销金额超过可核销余额", code=400)
    payable.reconciled_amount += amount
    payable.status = "settled" if payable.reconciled_amount == payable.total_amount else "partial"
    db.flush()


def create_expense(db: Session, context: UserContext, *, amount: Decimal, expense_type: str, description: str = "") -> FinExpense:
    expense = FinExpense(
        org_id=context.org_id,
        doc_no=f"EX-{context.id[:8]}-{date.today().strftime('%Y%m%d%H%M%S%f')}",
        applicant_id=context.id,
        department_id=context.department_id,
        amount=amount,
        expense_date=date.today(),
        expense_type=expense_type,
        status="draft",
        description=description,
    )
    db.add(expense)
    db.flush()
    return expense


def approve_expense(db: Session, expense_id: str, context: UserContext) -> FinExpense:
    expense = db.get(FinExpense, expense_id)
    if expense is None or expense.org_id != context.org_id:
        raise AppError("报销单不存在", code=404)
    if expense.status != "draft":
        raise AppError("报销单当前不可审核", code=400)
    expense.status = "approved"
    db.flush()
    return expense


def settle_expense(db: Session, expense_id: str, context: UserContext) -> FinExpense:
    expense = db.get(FinExpense, expense_id)
    if expense is None or expense.org_id != context.org_id:
        raise AppError("报销单不存在", code=404)
    if expense.status != "approved":
        raise AppError("报销单必须先审核", code=400)
    expense.status = "settled"
    db.flush()
    return expense


def generate_voucher(db: Session, source_type: str, source_id: str, context: UserContext) -> FinVoucher:
    existing = db.scalar(select(FinVoucher).where(FinVoucher.source_type == source_type, FinVoucher.source_id == source_id))
    if existing:
        return existing
    amount = Decimal("0")
    if source_type == "expense":
        source = db.get(FinExpense, source_id)
        if source is None:
            raise AppError("凭证来源单据不存在", code=404)
        amount = source.amount
        entries = [
            FinVoucherEntry(line_no=1, account_code="6602", account_name="费用", summary="业务费用", debit_amount=amount, credit_amount=0),
            FinVoucherEntry(line_no=2, account_code="1002", account_name="银行存款", summary="费用支付", debit_amount=0, credit_amount=amount),
        ]
    elif source_type == "receipt":
        source = db.get(FinReceipt, source_id)
        if source is None:
            raise AppError("凭证来源单据不存在", code=404)
        amount = source.amount
        entries = [
            FinVoucherEntry(line_no=1, account_code="1002", account_name="银行存款", summary="收到客户款项", debit_amount=amount, credit_amount=0),
            FinVoucherEntry(line_no=2, account_code="1122", account_name="应收账款", summary="收款核销", debit_amount=0, credit_amount=amount),
        ]
    elif source_type == "payment":
        source = db.get(FinPayment, source_id)
        if source is None:
            raise AppError("凭证来源单据不存在", code=404)
        amount = source.amount
        entries = [
            FinVoucherEntry(line_no=1, account_code="2202", account_name="应付账款", summary="付款核销", debit_amount=amount, credit_amount=0),
            FinVoucherEntry(line_no=2, account_code="1002", account_name="银行存款", summary="支付供应商款项", debit_amount=0, credit_amount=amount),
        ]
    else:
        raise AppError("暂不支持该凭证来源", code=400)
    voucher = FinVoucher(
        org_id=context.org_id,
        voucher_no=f"FV-{context.id[:8]}-{date.today().strftime('%Y%m%d%H%M%S%f')}",
        voucher_date=date.today(),
        period=date.today().strftime("%Y-%m"),
        source_type=source_type,
        source_id=source_id,
        status="draft",
        total_debit=amount,
        total_credit=amount,
    )
    voucher.entries = entries
    db.add(voucher)
    db.flush()
    return voucher


def _money(value: Decimal) -> str:
    return str(value)


def list_receivables(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(
        select(SalesReceivable).where(SalesReceivable.org_id == context.org_id).order_by(SalesReceivable.id.desc())
    ).all()
    return [
        {
            "id": row.id,
            "doc_no": row.doc_no,
            "customer_id": row.customer_id,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "total_amount": _money(row.total_amount),
            "reconciled_amount": _money(row.reconciled_amount),
            "status": row.status,
            "due_date": row.due_date.isoformat() if row.due_date else None,
        }
        for row in rows
    ]


def list_payables(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(
        select(PurchasePayable).where(PurchasePayable.org_id == context.org_id).order_by(PurchasePayable.id.desc())
    ).all()
    return [
        {
            "id": row.id,
            "doc_no": row.doc_no,
            "supplier_id": row.supplier_id,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "total_amount": _money(row.total_amount),
            "reconciled_amount": _money(row.reconciled_amount),
            "status": row.status,
            "due_date": row.due_date.isoformat() if row.due_date else None,
        }
        for row in rows
    ]


def list_receipts(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(FinReceipt).where(FinReceipt.org_id == context.org_id).order_by(FinReceipt.id.desc())).all()
    return [
        {
            "id": row.id,
            "doc_no": row.doc_no,
            "customer_id": row.customer_id,
            "account_name": row.account_name,
            "amount": _money(row.amount),
            "receipt_date": row.receipt_date.isoformat(),
            "status": row.status,
            "reconciled_amount": _money(sum(item.amount for item in row.reconciles)),
        }
        for row in rows
    ]


def list_payments(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(FinPayment).where(FinPayment.org_id == context.org_id).order_by(FinPayment.id.desc())).all()
    return [
        {
            "id": row.id,
            "doc_no": row.doc_no,
            "supplier_id": row.supplier_id,
            "account_name": row.account_name,
            "amount": _money(row.amount),
            "payment_date": row.payment_date.isoformat(),
            "status": row.status,
        }
        for row in rows
    ]


def list_expenses(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(FinExpense).where(FinExpense.org_id == context.org_id).order_by(FinExpense.id.desc())).all()
    return [
        {
            "id": row.id,
            "doc_no": row.doc_no,
            "applicant_id": row.applicant_id,
            "department_id": row.department_id,
            "amount": _money(row.amount),
            "expense_date": row.expense_date.isoformat(),
            "expense_type": row.expense_type,
            "status": row.status,
            "description": row.description,
        }
        for row in rows
    ]


def list_vouchers(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(FinVoucher).where(FinVoucher.org_id == context.org_id).order_by(FinVoucher.id.desc())).all()
    return [
        {
            "id": row.id,
            "voucher_no": row.voucher_no,
            "voucher_date": row.voucher_date.isoformat(),
            "period": row.period,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "status": row.status,
            "total_debit": _money(row.total_debit),
            "total_credit": _money(row.total_credit),
        }
        for row in rows
    ]

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
    SubcontractOrderCreate,
    SubcontractReceiptCreate,
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
    cancel_subcontract_order,
    complete_work_order,
    create_work_order,
    create_subcontract_order,
    issue_material,
    issue_subcontract_material,
    release_work_order,
    release_subcontract_order,
    receive_subcontract_order,
    report_work,
    return_material,
    serialize_issue,
    serialize_report,
    serialize_subcontract_order,
    serialize_subcontract_receipt,
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


@router.post("/subcontract-orders")
def create_subcontract_order_api(payload: SubcontractOrderCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = create_subcontract_order(db, payload, context)
    db.commit()
    return ok(serialize_subcontract_order(row))


@router.post("/subcontract-orders/{order_id}/release")
def release_subcontract_order_api(order_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = release_subcontract_order(db, order_id, context)
    db.commit()
    return ok(serialize_subcontract_order(row))


@router.post("/subcontract-orders/{order_id}/cancel")
def cancel_subcontract_order_api(order_id: str, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = cancel_subcontract_order(db, order_id, context)
    db.commit()
    return ok(serialize_subcontract_order(row))


@router.post("/subcontract-orders/{order_id}/issue")
def issue_subcontract_material_api(order_id: str, payload: MaterialIssueCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = issue_subcontract_material(db, order_id, payload.items, context)
    db.commit()
    return ok(serialize_issue(row))


@router.post("/subcontract-orders/{order_id}/receipts")
def receive_subcontract_order_api(order_id: str, payload: SubcontractReceiptCreate, context: UserContext = Depends(require_permission("production:manage")), db: Session = Depends(get_db)):
    row = receive_subcontract_order(db, order_id, payload, context)
    db.commit()
    return ok(serialize_subcontract_receipt(row))


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


class SubcontractOrderCreate(BaseModel):
    supplier_id: str = Field(min_length=1)
    material_id: str = Field(min_length=1)
    warehouse_id: str = Field(min_length=1)
    plan_date: date
    quantity: Decimal = Field(gt=0)
    processing_fee: Decimal = Field(gt=0)
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


class SubcontractReceiptCreate(BaseModel):
    good_quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(gt=0)

## backend/tests/test_subcontract_phase2.py
from decimal import Decimal
from pathlib import Path

from app.core.security import create_access_token
from app.models.configuration import CfgNumberRule
from app.models.finance import PurchasePayable
from app.models.inventory import InvStock, InvStockTransaction
from app.models.master_data import MdMaterial, MdSupplier, MdWarehouse


def headers():
    return {"Authorization": f"Bearer {create_access_token('user-1', ['production:manage'])}"}


def seed_subcontract_data(session):
    session.add_all(
        [
            CfgNumberRule(
                id="rule-mfg-subcontract-order",
                org_id="org-1",
                rule_key="mfg_subcontract_order",
                prefix="SC",
                date_format="%Y%m%d",
                sequence_length=4,
                reset_cycle="day",
            ),
            CfgNumberRule(
                id="rule-mfg-subcontract-receipt",
                org_id="org-1",
                rule_key="mfg_subcontract_receipt",
                prefix="SR",
                date_format="%Y%m%d",
                sequence_length=4,
                reset_cycle="day",
            ),
            MdSupplier(id="supplier-1", org_id="org-1", code="SUP-1", name="Processor"),
            MdMaterial(id="subcontract-finished-1", org_id="org-1", code="SC-FG-1", name="Subcontract finished"),
            MdMaterial(id="subcontract-raw-1", org_id="org-1", code="SC-RM-1", name="Subcontract raw"),
            MdWarehouse(id="subcontract-warehouse-1", org_id="org-1", code="SC-WH-1", name="Subcontract warehouse"),
            InvStock(
                id="subcontract-raw-stock-1",
                org_id="org-1",
                warehouse_id="subcontract-warehouse-1",
                material_id="subcontract-raw-1",
                quantity=Decimal("10"),
                available_quantity=Decimal("10"),
                average_cost=Decimal("3"),
            ),
        ]
    )
    session.commit()


def order_payload(**overrides):
    payload = {
        "supplier_id": "supplier-1",
        "material_id": "subcontract-finished-1",
        "warehouse_id": "subcontract-warehouse-1",
        "plan_date": "2026-08-02",
        "quantity": "10",
        "processing_fee": "120",
    }
    payload.update(overrides)
    return payload


def test_subcontract_issue_then_receive_creates_inventory_and_payable_source(client_and_session):
    """Dropping subcontract ledger or payable integration loses physical and financial traceability."""
    client, session = client_and_session
    seed_subcontract_data(session)

    created = client.post("/api/production/subcontract-orders", json=order_payload(), headers=headers())
    assert created.status_code == 200
    order = created.json()["data"]
    assert order["status"] == "draft"

    released = client.post(f"/api/production/subcontract-orders/{order['id']}/release", headers=headers())
    issue = client.post(
        f"/api/production/subcontract-orders/{order['id']}/issue",
        json={"items": [{"material_id": "subcontract-raw-1", "quantity": "10"}]},
        headers=headers(),
    )
    received = client.post(
        f"/api/production/subcontract-orders/{order['id']}/receipts",
        json={"good_quantity": "10", "unit_cost": "12"},
        headers=headers(),
    )

    assert released.json()["data"]["status"] == "released"
    assert issue.json()["data"]["subcontract_order_id"] == order["id"]
    receipt = received.json()["data"]
    assert receipt["status"] == "completed"
    assert session.query(InvStockTransaction).filter_by(
        source_type="subcontract_material_issue", source_id=issue.json()["data"]["id"]
    ).count() == 1
    assert session.query(InvStockTransaction).filter_by(
        source_type="subcontract_receipt", source_id=receipt["id"]
    ).count() == 1
    payable = session.query(PurchasePayable).filter_by(
        source_type="subcontract_receipt", source_id=receipt["id"]
    ).one()
    assert payable.total_amount == Decimal("120.00")
    assert session.get(InvStock, "subcontract-raw-stock-1").quantity == Decimal("0.000000")

    assert client.post(f"/api/production/subcontract-orders/{order['id']}/release", headers=headers()).json()["data"]["id"] == order["id"]
    assert client.post(
        f"/api/production/subcontract-orders/{order['id']}/issue",
        json={"items": [{"material_id": "subcontract-raw-1", "quantity": "10"}]},
        headers=headers(),
    ).json()["data"]["id"] == issue.json()["data"]["id"]
    assert client.post(
        f"/api/production/subcontract-orders/{order['id']}/receipts",
        json={"good_quantity": "10", "unit_cost": "12"},
        headers=headers(),
    ).json()["data"]["id"] == receipt["id"]
    assert session.query(PurchasePayable).filter_by(source_type="subcontract_receipt", source_id=receipt["id"]).count() == 1


def test_subcontract_rejects_missing_permission_and_foreign_supplier(client_and_session):
    """Removing route permission or supplier-organization validation enables unauthorized foreign processing orders."""
    client, session = client_and_session
    seed_subcontract_data(session)
    session.add(MdSupplier(id="supplier-foreign", org_id="org-2", code="SUP-2", name="Foreign processor"))
    session.commit()

    forbidden = client.post(
        "/api/production/subcontract-orders",
        json=order_payload(),
        headers={"Authorization": f"Bearer {create_access_token('user-1', [])}"},
    )
    foreign_supplier = client.post(
        "/api/production/subcontract-orders",
        json=order_payload(supplier_id="supplier-foreign"),
        headers=headers(),
    )

    assert forbidden.json()["code"] == 403
    assert foreign_supplier.json()["code"] == 404


def test_subcontract_order_can_be_cancelled_before_receipt(client_and_session):
    """Allowing post-cancellation issue would create stock movement for a terminal subcontract order."""
    client, session = client_and_session
    seed_subcontract_data(session)
    order = client.post("/api/production/subcontract-orders", json=order_payload(), headers=headers()).json()["data"]
    client.post(f"/api/production/subcontract-orders/{order['id']}/release", headers=headers())

    cancelled = client.post(f"/api/production/subcontract-orders/{order['id']}/cancel", headers=headers())
    issue_after_cancel = client.post(
        f"/api/production/subcontract-orders/{order['id']}/issue",
        json={"items": [{"material_id": "subcontract-raw-1", "quantity": "1"}]},
        headers=headers(),
    )

    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert issue_after_cancel.json()["code"] == 400


def test_sql_contains_repeatable_subcontract_schema_bootstrap():
    """Removing subcontract tables or guarded upgrades breaks existing MySQL installations on re-run."""
    sql = (Path(__file__).parents[2] / "database" / "init.sql").read_text(encoding="utf-8").lower()

    for table in ("mfg_subcontract_order", "mfg_subcontract_receipt"):
        table_sql = sql.split(f"create table if not exists {table}", 1)[1].split("engine=", 1)[0]
        assert "is_deleted tinyint(1) not null default 0" in table_sql
        assert "created_at datetime(6) not null default current_timestamp(6)" in table_sql
        assert "updated_at datetime(6) not null default current_timestamp(6) on update current_timestamp(6)" in table_sql
        assert "version int not null default 1" in table_sql
    assert "create procedure phase2_add_task4_column" in sql
    assert "call phase2_add_task4_column('mfg_material_issue', 'subcontract_order_id'" in sql
## SQL subcontract
  quantity DECIMAL(18,6) NOT NULL,
  unit_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
  line_no INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_material_return_item_return (return_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_work_report (
  id CHAR(36) PRIMARY KEY,
  work_order_id CHAR(36) NOT NULL,
  good_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  scrap_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  hours DECIMAL(18,6) NOT NULL DEFAULT 0,
  report_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_work_report_order (work_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_subcontract_order (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  supplier_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  plan_date DATE NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  received_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  processing_fee DECIMAL(18,2) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  created_by CHAR(36) NULL,
  updated_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_subcontract_order_doc_no (org_id, doc_no),
  KEY idx_mfg_subcontract_order_supplier (org_id, supplier_id),
  KEY idx_mfg_subcontract_order_material (org_id, material_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_subcontract_receipt (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  subcontract_order_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  good_quantity DECIMAL(18,6) NOT NULL,
  unit_cost DECIMAL(18,6) NOT NULL,
  processing_fee_amount DECIMAL(18,2) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'completed',
  source_type VARCHAR(64) NOT NULL,
  source_id CHAR(36) NOT NULL,
  created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_subcontract_receipt_doc_no (org_id, doc_no),
  KEY idx_mfg_subcontract_receipt_order (subcontract_order_id),
  KEY idx_mfg_subcontract_receipt_source (org_id, source_type, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Upgrade the Task 1 work-order stub and any partial Task 3 schema when this
-- script is re-run. CREATE TABLE IF NOT EXISTS does not add columns.
DROP PROCEDURE IF EXISTS phase2_add_task3_column;
DELIMITER //
CREATE PROCEDURE phase2_add_task3_column(
  IN table_name_input VARCHAR(64),
  IN column_name_input VARCHAR(64),
  IN column_definition TEXT
)
BEGIN
  DECLARE column_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO column_exists
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = table_name_input
    AND column_name = column_name_input;
  IF column_exists = 0 THEN
    SET @phase2_task3_sql = CONCAT(
      'ALTER TABLE `', table_name_input, '` ADD COLUMN `', column_name_input, '` ', column_definition
    );
    PREPARE phase2_task3_statement FROM @phase2_task3_sql;
    EXECUTE phase2_task3_statement;
    DEALLOCATE PREPARE phase2_task3_statement;
  END IF;
END//
DELIMITER ;

DROP PROCEDURE IF EXISTS phase2_rename_task3_column;
DELIMITER //
CREATE PROCEDURE phase2_rename_task3_column(
  IN table_name_input VARCHAR(64),
  IN old_column_name_input VARCHAR(64),
  IN new_column_name_input VARCHAR(64),
  IN new_column_definition TEXT
)
BEGIN
  DECLARE old_column_exists INT DEFAULT 0;
  DECLARE new_column_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO old_column_exists
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = table_name_input
    AND column_name = old_column_name_input;
  SELECT COUNT(*) INTO new_column_exists
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = table_name_input
    AND column_name = new_column_name_input;
  IF old_column_exists = 1 AND new_column_exists = 0 THEN
    SET @phase2_task3_sql = CONCAT(
      'ALTER TABLE `', table_name_input, '` CHANGE COLUMN `', old_column_name_input,
      '` `', new_column_name_input, '` ', new_column_definition
    );
    PREPARE phase2_task3_statement FROM @phase2_task3_sql;
    EXECUTE phase2_task3_statement;
    DEALLOCATE PREPARE phase2_task3_statement;
  END IF;
END//
DELIMITER ;

CALL phase2_add_task3_column('mfg_work_order', 'warehouse_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_work_order', 'bom_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_work_order', 'plan_date', 'DATE NOT NULL DEFAULT ''1970-01-01''');
CALL phase2_add_task3_column('mfg_work_order', 'reported_good_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_order', 'reported_scrap_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_order', 'completed_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_order', 'bom_snapshot', 'JSON NULL');
CALL phase2_add_task3_column('mfg_work_order', 'source_type', 'VARCHAR(64) NULL');
CALL phase2_add_task3_column('mfg_work_order', 'source_id', 'CHAR(36) NULL');
CALL phase2_add_task3_column('mfg_work_order', 'created_by', 'CHAR(36) NULL');
CALL phase2_add_task3_column('mfg_work_order', 'updated_by', 'CHAR(36) NULL');

CALL phase2_add_task3_column('mfg_work_order_material', 'returned_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_order_material', 'line_no', 'INT NOT NULL DEFAULT 1');

CALL phase2_add_task3_column('mfg_material_issue', 'org_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_issue', 'work_order_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_issue', 'warehouse_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_issue', 'created_by', 'CHAR(36) NULL');
CALL phase2_add_task3_column('mfg_material_issue', 'is_deleted', 'TINYINT(1) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_issue', 'created_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_issue', 'updated_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_issue', 'version', 'INT NOT NULL DEFAULT 1');
CALL phase2_add_task3_column('mfg_material_issue_item', 'issue_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_issue_item', 'material_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_issue_item', 'quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_issue_item', 'returned_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_issue_item', 'unit_cost', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_issue_item', 'line_no', 'INT NOT NULL DEFAULT 1');
CALL phase2_add_task3_column('mfg_material_issue_item', 'is_deleted', 'TINYINT(1) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_issue_item', 'created_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_issue_item', 'updated_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_issue_item', 'version', 'INT NOT NULL DEFAULT 1');
CALL phase2_add_task3_column('mfg_material_return', 'org_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_return', 'work_order_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_return', 'issue_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_return', 'warehouse_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_return', 'created_by', 'CHAR(36) NULL');
CALL phase2_add_task3_column('mfg_material_return', 'is_deleted', 'TINYINT(1) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_return', 'created_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_return', 'updated_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_return', 'version', 'INT NOT NULL DEFAULT 1');
CALL phase2_add_task3_column('mfg_material_return_item', 'return_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_return_item', 'material_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_return_item', 'quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_return_item', 'unit_cost', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_return_item', 'line_no', 'INT NOT NULL DEFAULT 1');
CALL phase2_add_task3_column('mfg_material_return_item', 'is_deleted', 'TINYINT(1) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_return_item', 'created_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_return_item', 'updated_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_return_item', 'version', 'INT NOT NULL DEFAULT 1');

CALL phase2_rename_task3_column('mfg_work_report', 'reported_quantity', 'good_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_report', 'good_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_report', 'scrap_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_report', 'hours', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_report', 'report_time', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_work_report', 'created_by', 'CHAR(36) NULL');

UPDATE mfg_work_order
SET bom_snapshot = JSON_OBJECT()
WHERE bom_snapshot IS NULL;
ALTER TABLE `mfg_work_order` MODIFY COLUMN `bom_snapshot` JSON NOT NULL;
DROP PROCEDURE IF EXISTS phase2_add_task3_column;
DROP PROCEDURE IF EXISTS phase2_rename_task3_column;

-- Upgrade Task 4 subcontract fields safely when this script is re-run against
-- an existing Phase 2 database. The prior material issue table only accepted
-- work-order issues, so its work_order_id must become optional.
DROP PROCEDURE IF EXISTS phase2_add_task4_column;
DELIMITER //
CREATE PROCEDURE phase2_add_task4_column(
  IN table_name_input VARCHAR(64),
  IN column_name_input VARCHAR(64),
  IN column_definition TEXT
)
BEGIN
  DECLARE column_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO column_exists
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = table_name_input
    AND column_name = column_name_input;
  IF column_exists = 0 THEN
    SET @phase2_task4_sql = CONCAT(
      'ALTER TABLE `', table_name_input, '` ADD COLUMN `', column_name_input, '` ', column_definition
    );
    PREPARE phase2_task4_statement FROM @phase2_task4_sql;
    EXECUTE phase2_task4_statement;
    DEALLOCATE PREPARE phase2_task4_statement;
  END IF;
END//
DELIMITER ;

CALL phase2_add_task4_column('mfg_material_issue', 'subcontract_order_id', 'CHAR(36) NULL');
CALL phase2_add_task4_column('mfg_material_issue', 'source_type', 'VARCHAR(64) NULL');
CALL phase2_add_task4_column('mfg_material_issue', 'source_id', 'CHAR(36) NULL');
ALTER TABLE `mfg_material_issue` MODIFY COLUMN `work_order_id` CHAR(36) NULL;
CALL phase2_add_task4_column('mfg_subcontract_order', 'received_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task4_column('mfg_subcontract_order', 'processing_fee', 'DECIMAL(18,2) NOT NULL DEFAULT 0');
CALL phase2_add_task4_column('mfg_subcontract_order', 'source_type', 'VARCHAR(64) NULL');
CALL phase2_add_task4_column('mfg_subcontract_order', 'source_id', 'CHAR(36) NULL');
CALL phase2_add_task4_column('mfg_subcontract_order', 'created_by', 'CHAR(36) NULL');
CALL phase2_add_task4_column('mfg_subcontract_order', 'updated_by', 'CHAR(36) NULL');
CALL phase2_add_task4_column('mfg_subcontract_receipt', 'processing_fee_amount', 'DECIMAL(18,2) NOT NULL DEFAULT 0');
CALL phase2_add_task4_column('mfg_subcontract_receipt', 'source_type', 'VARCHAR(64) NOT NULL DEFAULT ''''');
CALL phase2_add_task4_column('mfg_subcontract_receipt', 'source_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task4_column('mfg_subcontract_receipt', 'created_by', 'CHAR(36) NULL');
DROP PROCEDURE IF EXISTS phase2_add_task4_column;

CREATE TABLE IF NOT EXISTS inv_zone (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
