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
