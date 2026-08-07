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
