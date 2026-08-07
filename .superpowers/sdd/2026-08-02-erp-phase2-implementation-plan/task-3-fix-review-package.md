# Task 3 fix review snapshot
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

---

## Review Fixes: Schema Bootstrap and Service Validation

Date: 2026-08-02

### Findings addressed

- Replaced the minimal `mfg_work_order` fresh-bootstrap definition with all SQLAlchemy-mapped Task 3 columns: warehouse, BOM, plan date, report/completion quantities, BOM snapshot, source link, and user audit fields.
- Added fresh MySQL definitions for `mfg_material_issue`, `mfg_material_issue_item`, `mfg_material_return`, and `mfg_material_return_item`, including their matching audit columns and indexes.
- Updated `mfg_work_order_material` with returned quantity and line number, and updated `mfg_work_report` to use good/scrap/hours/creator fields matching `MfgReport`.
- Added repeatable guarded MySQL procedures for Task 3 column additions and legacy `mfg_work_report.reported_quantity -> good_quantity` migration. Existing work-order BOM snapshots are populated with `JSON_OBJECT()` before the column is made non-null.
- Added direct service validation in `report_work` so negative good or scrap quantities are rejected even when Pydantic is bypassed.
- Added public API coverage for cross-organization, unknown, and incomplete source references.

### TDD evidence for review fixes

Initial focused RED command, run from `backend`:

```bash
./.venv/bin/python -m pytest tests/test_work_order_phase2.py -q
```

Result: `3 failed, 5 passed, 1 warning in 1.56s`.

- Both direct-service negative payload cases failed because `report_work` accepted them without raising `AppError`.
- The bootstrap contract failed because `mfg_work_order.warehouse_id` was absent from the fresh SQL definition.

An additional RED check was added for guarded audit-column upgrades on all material issue/return tables:

```bash
./.venv/bin/python -m pytest tests/test_work_order_phase2.py::test_sql_contains_complete_repeatable_work_order_schema_upgrade -q
```

Result: `1 failed, 1 warning in 0.03s`; the generic upgrade calls for `is_deleted` were absent.

After the service guard and SQL changes, the focused green run was:

```bash
./.venv/bin/python -m pytest tests/test_work_order_phase2.py -q
```

Result: `8 passed, 1 warning in 1.51s`.

### Final verification for review fixes

All commands were run from `backend` using `./.venv/bin/python`:

```bash
./.venv/bin/python -m pytest tests/test_work_order_phase2.py -q
```

Result: `8 passed, 1 warning in 1.51s`.

```bash
./.venv/bin/python -m pytest -q
```

Result: `75 passed, 1 warning in 11.65s`.

```bash
./.venv/bin/python -m compileall -q app
```

Result: exit code `0`; no output.

### Review-fix changed files

- `database/init.sql`
- `backend/app/services/production_service.py`
- `backend/tests/test_work_order_phase2.py`
- `.superpowers/sdd/2026-08-02-erp-phase2-implementation-plan/task-3-report.md`

### Remaining concern

The repeatable MySQL SQL is contract-tested from the bootstrap file, but this workspace has no configured MySQL instance for executing the full bootstrap against an actual MySQL server. The final Python suite and compilation are green; the only pytest warning remains the pre-existing TestClient deprecation warning.
## Production service
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
    if good_quantity < 0 or scrap_quantity < 0:
        raise AppError("合格数量和报废数量不能为负数", code=400)
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
## Task tests
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppError
from app.core.security import create_access_token
from app.models.configuration import CfgNumberRule
from app.models.inventory import InvStock, InvStockTransaction
from app.models.logging import SysOperationLog
from app.models.master_data import MdMaterial, MdWarehouse
from app.models.platform import ExtEventOutbox
from app.models.production import MfgMps
from app.models.system import SysUser
from app.services.auth_service import UserContext
from app.services.production_service import report_work


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


def service_context(session):
    return UserContext(user=session.get(SysUser, "user-1"), permissions={"*"})


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


@pytest.mark.parametrize(
    "payload",
    [
        SimpleNamespace(good_quantity=Decimal("-1"), scrap_quantity=Decimal("2"), hours=Decimal("1")),
        SimpleNamespace(good_quantity=Decimal("2"), scrap_quantity=Decimal("-1"), hours=Decimal("1")),
    ],
)
def test_report_work_rejects_negative_quantities_without_pydantic(client_and_session, payload):
    """Removing service validation lets non-HTTP callers create invalid report totals."""
    client, session = client_and_session
    seed_work_order_data(session)
    create_approved_bom(client)
    work_order = create_released_work_order(client)

    with pytest.raises(AppError) as error:
        report_work(session, work_order["id"], payload, service_context(session))

    assert error.value.code == 400


def test_work_order_source_link_rejects_cross_org_unknown_and_incomplete_references(client_and_session):
    """Weak source validation permits a work order to point at foreign or nonexistent planning records."""
    client, session = client_and_session
    seed_work_order_data(session)
    create_approved_bom(client)
    session.add(
        MfgMps(
            id="mps-other-org",
            org_id="org-2",
            doc_no="MPS-OTHER-ORG",
            material_id="finished-1",
            warehouse_id="warehouse-1",
            plan_date=date(2026, 8, 2),
            plan_quantity=Decimal("5"),
        )
    )
    session.commit()
    payload = {
        "material_id": "finished-1",
        "warehouse_id": "warehouse-1",
        "quantity": "5",
        "plan_date": "2026-08-02",
        "source_type": "mfg_mps",
    }

    cross_org = client.post(
        "/api/production/work-orders", json={**payload, "source_id": "mps-other-org"}, headers=headers()
    )
    unknown = client.post(
        "/api/production/work-orders", json={**payload, "source_id": "mps-missing"}, headers=headers()
    )
    incomplete = client.post("/api/production/work-orders", json=payload, headers=headers())

    assert cross_org.json()["code"] == 404
    assert unknown.json()["code"] == 404
    assert incomplete.json()["code"] == 400


def test_sql_contains_complete_repeatable_work_order_schema_upgrade():
    """Dropping Task 3 bootstrap columns or guarded upgrades breaks existing MySQL installations."""
    sql = (Path(__file__).parents[2] / "database" / "init.sql").read_text(encoding="utf-8").lower()

    expected_columns = {
        "mfg_work_order": (
            "warehouse_id char(36) not null",
            "bom_id char(36) not null",
            "plan_date date not null",
            "reported_good_quantity decimal(18,6) not null default 0",
            "reported_scrap_quantity decimal(18,6) not null default 0",
            "completed_quantity decimal(18,6) not null default 0",
            "bom_snapshot json not null",
            "source_type varchar(64) null",
            "source_id char(36) null",
            "created_by char(36) null",
            "updated_by char(36) null",
        ),
        "mfg_work_order_material": (
            "returned_quantity decimal(18,6) not null default 0",
            "line_no int not null default 1",
        ),
        "mfg_material_issue": ("work_order_id char(36) not null", "warehouse_id char(36) not null"),
        "mfg_material_issue_item": ("issue_id char(36) not null", "returned_quantity decimal(18,6) not null default 0"),
        "mfg_material_return": ("issue_id char(36) not null", "warehouse_id char(36) not null"),
        "mfg_material_return_item": ("return_id char(36) not null", "unit_cost decimal(18,6) not null default 0"),
        "mfg_work_report": (
            "good_quantity decimal(18,6) not null default 0",
            "scrap_quantity decimal(18,6) not null default 0",
            "hours decimal(18,6) not null default 0",
            "created_by char(36) null",
        ),
    }
    for table_name, columns in expected_columns.items():
        definition = sql.split(f"create table if not exists {table_name}", 1)[1].split("engine=", 1)[0]
        for column in columns:
            assert column in definition, f"{table_name}.{column}"

    assert "create procedure phase2_add_task3_column" in sql
    assert "call phase2_add_task3_column('mfg_work_order', 'warehouse_id'" in sql
    assert "call phase2_add_task3_column('mfg_work_report', 'scrap_quantity'" in sql
    for table_name in (
        "mfg_material_issue",
        "mfg_material_issue_item",
        "mfg_material_return",
        "mfg_material_return_item",
    ):
        assert f"call phase2_add_task3_column('{table_name}', 'is_deleted'" in sql
## SQL
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
  warehouse_id CHAR(36) NOT NULL,
  bom_id CHAR(36) NOT NULL,
  plan_date DATE NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  reported_good_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  reported_scrap_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  completed_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  bom_snapshot JSON NOT NULL,
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  created_by CHAR(36) NULL,
  updated_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_work_order_doc_no (org_id, doc_no),
  KEY idx_mfg_work_order_material (org_id, material_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_work_order_material (
  id CHAR(36) PRIMARY KEY,
  work_order_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  required_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  issued_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  returned_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  line_no INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_work_order_material_order (work_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_material_issue (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  work_order_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_material_issue_order (work_order_id),
  KEY idx_mfg_material_issue_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_material_issue_item (
  id CHAR(36) PRIMARY KEY,
  issue_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  returned_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  unit_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
  line_no INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_material_issue_item_issue (issue_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_material_return (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  work_order_id CHAR(36) NOT NULL,
  issue_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_material_return_order (work_order_id),
  KEY idx_mfg_material_return_issue (issue_id),
  KEY idx_mfg_material_return_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_material_return_item (
  id CHAR(36) PRIMARY KEY,
  return_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
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
