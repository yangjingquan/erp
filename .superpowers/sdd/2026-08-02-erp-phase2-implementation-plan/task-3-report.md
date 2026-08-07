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
