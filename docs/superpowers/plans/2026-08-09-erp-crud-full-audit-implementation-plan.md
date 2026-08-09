# ERP Full-Page CRUD Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify every page-backed write operation end to end, repair every reproducible CRUD or business-action failure, and leave regression coverage plus a page-by-page audit report.

**Architecture:** Build a route and client-call contract layer first, then exercise core data, phase-one transactions, and phase-two operations with authenticated API integration tests. Finish with browser-based page testing against the local ERP database, using traceable temporary data and recording every route in a durable audit report.

**Tech Stack:** Vue 3, TypeScript, Axios, Vitest, FastAPI, Pydantic, SQLAlchemy, Pytest, SQLite test database, MySQL 8 local runtime.

## Global Constraints

- Cover all page-triggered create, update, delete, enable/disable, submit, approve, reject, close, settle, reconcile, report, receive, and deliver operations.
- Do not add delete behavior to audited business documents that intentionally use status transitions instead of deletion.
- Preserve all pre-existing uncommitted changes and avoid unrelated refactors.
- Browser-created records use the `CODEX-CRUD-` prefix or a directly traceable related field.
- Modify or delete only records created by this audit; never modify or delete existing business data.
- Validate backup restore contracts and safety checks without executing a real restore.
- Keep existing FastAPI, SQLAlchemy, Pydantic, Vue, Axios, and Element Plus patterns.

## Current Baseline

- Backend: `119 passed, 1 warning` from `.venv/bin/pytest -q`.
- Frontend: `10 passed` test files and `39 passed` tests from `npm test`.
- TypeScript: `npm run typecheck` exits successfully.
- The worktree already contains source and generated-asset changes; every commit in this plan must stage only the task's explicitly listed files.

---

### Task 1: Add Complete Page-Backed Write Contract Coverage

**Files:**
- Create: `backend/tests/test_page_write_route_contract.py`
- Create: `frontend/tests/crud-api-contract.test.ts`
- Modify only if a contract assertion fails: `frontend/src/api/auth.ts`
- Modify only if a contract assertion fails: `frontend/src/api/admin.ts`
- Modify only if a contract assertion fails: `frontend/src/api/master-data.ts`
- Modify only if a contract assertion fails: `frontend/src/api/config.ts`
- Modify only if a contract assertion fails: `frontend/src/api/workflow.ts`
- Modify only if a contract assertion fails: `frontend/src/api/sales.ts`
- Modify only if a contract assertion fails: `frontend/src/api/purchase.ts`
- Modify only if a contract assertion fails: `frontend/src/api/inventory.ts`
- Modify only if a contract assertion fails: `frontend/src/api/inventory-advanced.ts`
- Modify only if a contract assertion fails: `frontend/src/api/finance.ts`
- Modify only if a contract assertion fails: `frontend/src/api/production.ts`
- Modify only if a contract assertion fails: `frontend/src/api/cost.ts`
- Modify only if a contract assertion fails: `frontend/src/api/crm.ts`
- Modify only if a contract assertion fails: `frontend/src/api/quality.ts`
- Modify only if a contract assertion fails: `frontend/src/api/hr.ts`
- Modify only if a contract assertion fails: `frontend/src/api/platform.ts`
- Modify only if a contract assertion fails: `frontend/src/api/backup.ts`

**Interfaces:**
- Consumes: FastAPI `app.routes`; frontend API exports and the Axios instance from `frontend/src/api/http.ts`.
- Produces: one authoritative test for all page-backed `(HTTP method, path)` pairs and one test that records the exact Axios method, URL, body, and query configuration emitted by every frontend write helper.

- [ ] **Step 1: Write the backend route contract test**

Create a constant set containing the exact page-backed write routes. The assertion must normalize FastAPI methods to lowercase and exclude generated `HEAD` and `OPTIONS` methods.

```python
from app.main import app


PAGE_WRITE_ROUTES = {
    ("post", "/api/auth/register"),
    ("post", "/api/auth/change-password"),
    ("post", "/api/master/{resource}"),
    ("put", "/api/master/{resource}/{item_id}"),
    ("post", "/api/master/{resource}/{item_id}/status"),
    ("post", "/api/master/{resource}/import"),
    ("post", "/api/admin/departments"),
    ("post", "/api/admin/roles"),
    ("post", "/api/admin/users"),
    ("put", "/api/admin/users/{user_id}"),
    ("put", "/api/admin/users/{user_id}/password"),
    ("put", "/api/admin/users/{user_id}/roles"),
    ("post", "/api/admin/menus"),
    ("put", "/api/admin/roles/{role_id}/access"),
    ("post", "/api/admin/{resource}/{row_id}/status"),
    ("put", "/api/config/parameters/{parameter_key}"),
    ("post", "/api/config/print-templates"),
    ("put", "/api/workflow/definitions/{business_type}"),
    ("post", "/api/sales/orders"),
    ("post", "/api/sales/orders/{order_id}/submit"),
    ("post", "/api/sales/orders/{order_id}/approve"),
    ("post", "/api/sales/orders/{order_id}/create-delivery"),
    ("post", "/api/sales/quotes"),
    ("post", "/api/sales/quotes/{quote_id}/{action}"),
    ("post", "/api/sales/returns"),
    ("post", "/api/purchase/orders"),
    ("post", "/api/purchase/orders/{order_id}/submit"),
    ("post", "/api/purchase/orders/{order_id}/approve"),
    ("post", "/api/purchase/orders/{order_id}/create-receipt"),
    ("post", "/api/purchase/requests"),
    ("post", "/api/purchase/requests/{request_id}/{action}"),
    ("post", "/api/purchase/returns"),
    ("post", "/api/inventory/transfers"),
    ("post", "/api/inventory/transfers/{transfer_id}/approve"),
    ("post", "/api/inventory/transfers/{transfer_id}/complete"),
    ("post", "/api/inventory/counts"),
    ("post", "/api/inventory/counts/{count_id}/complete"),
    ("post", "/api/inventory/advanced/locations"),
    ("post", "/api/inventory/advanced/batches"),
    ("post", "/api/inventory/advanced/scan/token"),
    ("post", "/api/inventory/advanced/scan/process"),
    ("post", "/api/finance/receipts"),
    ("post", "/api/finance/payments"),
    ("post", "/api/finance/expenses"),
    ("post", "/api/finance/expenses/{expense_id}/approve"),
    ("post", "/api/finance/expenses/{expense_id}/settle"),
    ("post", "/api/finance/vouchers/{source_type}/{source_id}"),
    ("post", "/api/finance/receipts/{receipt_id}/reconcile"),
    ("post", "/api/finance/payments/{payment_id}/reconcile"),
    ("post", "/api/production/boms"),
    ("post", "/api/production/boms/{bom_id}/submit"),
    ("post", "/api/production/boms/{bom_id}/approve"),
    ("post", "/api/production/boms/{bom_id}/disable"),
    ("post", "/api/production/mps"),
    ("post", "/api/production/mps/{mps_id}/run-mrp"),
    ("post", "/api/production/work-orders"),
    ("post", "/api/production/work-orders/{work_order_id}/release"),
    ("post", "/api/production/work-orders/{work_order_id}/issue"),
    ("post", "/api/production/work-orders/{work_order_id}/reports"),
    ("post", "/api/production/work-orders/{work_order_id}/complete"),
    ("post", "/api/production/work-orders/{work_order_id}/cancel"),
    ("post", "/api/cost/allocations"),
    ("post", "/api/cost/allocations/{allocation_id}/post"),
    ("post", "/api/cost/periods/{period}/close"),
    ("post", "/api/cost/periods/{period}/reopen"),
    ("post", "/api/crm/leads"),
    ("post", "/api/crm/leads/{lead_id}/transition/{status}"),
    ("post", "/api/crm/leads/{lead_id}/convert"),
    ("post", "/api/crm/opportunities"),
    ("post", "/api/crm/opportunities/{opportunity_id}/transition/{stage}"),
    ("post", "/api/crm/opportunities/{opportunity_id}/follow-ups"),
    ("post", "/api/quality/inspections"),
    ("post", "/api/quality/inspections/{inspection_id}/submit"),
    ("post", "/api/quality/inspections/{inspection_id}/close"),
    ("post", "/api/hr/employees"),
    ("put", "/api/hr/employees/{employee_id}"),
    ("put", "/api/hr/employees/{employee_id}/password"),
    ("post", "/api/hr/employees/{employee_id}/attendance"),
    ("post", "/api/hr/payroll/{period}/calculate"),
    ("post", "/api/hr/payroll/{payroll_id}/approve"),
    ("post", "/api/hr/payroll/{payroll_id}/pay"),
    ("post", "/api/platform/api-clients"),
    ("post", "/api/platform/api-clients/{client_id}/status"),
    ("post", "/api/system/backup"),
    ("post", "/api/system/restore/validate"),
}


def test_all_page_backed_write_routes_are_registered():
    actual = {
        (method.lower(), route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
        if method not in {"HEAD", "OPTIONS"}
    }
    assert PAGE_WRITE_ROUTES <= actual
```

- [ ] **Step 2: Run the route contract test and inspect missing pairs**

Run: `.venv/bin/pytest tests/test_page_write_route_contract.py -q`

Expected: PASS, or a precise set difference identifying a missing/misregistered route.

- [ ] **Step 3: Write the frontend API contract test**

Mock `http.get/post/put/delete`, call every exported write helper with stable identifiers, and assert exact calls. Use table-driven assertions for uniform APIs and direct assertions for special argument shapes.

```typescript
import { beforeEach, describe, expect, it, vi } from "vitest";

const http = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}));
vi.mock("../src/api/http", () => ({ http }));

beforeEach(() => vi.clearAllMocks());

it("sends advanced inventory relation ids in query params", async () => {
  const { createBatch, createLocation } = await import("../src/api/inventory-advanced");
  createLocation("warehouse-1", { code: "CODEX-CRUD-L1", name: "测试库位" });
  createBatch("material-1", { batch_no: "CODEX-CRUD-B1" });
  expect(http.post).toHaveBeenNthCalledWith(
    1,
    "/inventory/advanced/locations",
    { code: "CODEX-CRUD-L1", name: "测试库位" },
    { params: { warehouse_id: "warehouse-1" } },
  );
  expect(http.post).toHaveBeenNthCalledWith(
    2,
    "/inventory/advanced/batches",
    { batch_no: "CODEX-CRUD-B1" },
    { params: { material_id: "material-1" } },
  );
});
```

The same file must directly invoke every page-used write export from the interfaces listed in this task. Backup assertions stop at `validateRestore`; they do not call `restoreBackup`.

- [ ] **Step 4: Run the frontend contract test and correct only proven mismatches**

Run: `npm test -- crud-api-contract.test.ts`

Expected: FAIL only for exact method/path/body/query mismatches; after the smallest API-helper correction, PASS.

- [ ] **Step 5: Run both contract suites together**

Run: `.venv/bin/pytest tests/test_page_write_route_contract.py -q`

Run: `npm test -- crud-api-contract.test.ts`

Expected: both PASS.

- [ ] **Step 6: Commit only Task 1 files**

```bash
git add backend/tests/test_page_write_route_contract.py frontend/tests/crud-api-contract.test.ts frontend/src/api
git commit -m "test: cover all page write contracts"
```

### Task 2: Verify Core Master Data, Administration, and Settings Writes

**Files:**
- Create: `backend/tests/test_page_crud_core.py`
- Create: `frontend/tests/core-crud-pages.test.ts`
- Modify when a test proves a defect: `backend/app/api/master_data.py`
- Modify when a test proves a defect: `backend/app/services/master_data_service.py`
- Modify when a test proves a defect: `backend/app/api/admin.py`
- Modify when a test proves a defect: `backend/app/services/admin_service.py`
- Modify when a test proves a defect: `backend/app/api/config.py`
- Modify when a test proves a defect: `backend/app/services/configuration_service.py`
- Modify when a test proves a defect: `backend/app/api/workflow.py`
- Modify when a test proves a defect: `backend/app/services/workflow_service.py`
- Modify when a test proves a defect: `frontend/src/views/master-data/MasterDataPage.vue`
- Modify when a test proves a defect: `frontend/src/views/system/AdminBasics.vue`
- Modify when a test proves a defect: `frontend/src/views/system/UserManagement.vue`
- Modify when a test proves a defect: `frontend/src/views/settings/GlobalParameters.vue`
- Modify when a test proves a defect: `frontend/src/views/settings/PrintTemplates.vue`
- Modify when a test proves a defect: `frontend/src/views/settings/WorkflowConfig.vue`
- Modify when a test proves a defect: `frontend/src/views/settings/ApiClientList.vue`

**Interfaces:**
- Consumes: authenticated `TestClient`, unified `{code, data, msg}` response contract, core page API helpers.
- Produces: integration coverage for all six master resources, four admin resources, user edit/password/roles, role access, global parameters, print templates, workflow definitions, and API-client status.

- [ ] **Step 1: Add table-driven master-data create/update/status coverage**

```python
import pytest
from app.core.security import create_access_token


@pytest.mark.parametrize(
    ("resource", "payload", "changed_name"),
    [
        ("materials", {"code": "CODEX-CRUD-MAT", "name": "测试物料"}, "测试物料-修改"),
        ("customers", {"code": "CODEX-CRUD-CUS", "name": "测试客户"}, "测试客户-修改"),
        ("suppliers", {"code": "CODEX-CRUD-SUP", "name": "测试供应商"}, "测试供应商-修改"),
        ("warehouses", {"code": "CODEX-CRUD-WH", "name": "测试仓库"}, "测试仓库-修改"),
        ("units", {"code": "CODEX-CRUD-U", "name": "测试单位"}, "测试单位-修改"),
        ("tax-rates", {"code": "CODEX-CRUD-TAX", "name": "测试税率", "rate": 0.13}, "测试税率-修改"),
    ],
)
def test_master_page_create_update_and_deactivate(client_and_session, resource, payload, changed_name):
    client, _ = client_and_session
    headers = {"Authorization": f"Bearer {create_access_token('user-1', ['master:manage'])}"}
    created = client.post(f"/api/master/{resource}", json=payload, headers=headers).json()
    assert created["code"] == 0
    item_id = created["data"]["id"]
    updated = client.put(f"/api/master/{resource}/{item_id}", json={**payload, "name": changed_name}, headers=headers).json()
    assert updated["code"] == 0
    inactive = client.post(f"/api/master/{resource}/{item_id}/status", json={"status": "inactive"}, headers=headers).json()
    assert inactive["code"] == 0
```

- [ ] **Step 2: Add authenticated tests for admin and settings write sequences**

Create department, role, user, and menu records; update the user profile, password, roles, role access, and each resource status. Save and reload a global parameter, print template, and workflow definition. Create and deactivate one API client. Every assertion checks both `code == 0` and the reloaded value.

- [ ] **Step 3: Run the core integration tests to expose backend failures**

Run: `.venv/bin/pytest tests/test_page_crud_core.py -q`

Expected: each failure points to one route, schema, service transaction, or response field.

- [ ] **Step 4: Add frontend source tests for submit locking, backend messages, and reloads**

The source test must assert that every save handler uses `try/finally`, displays `response.data.msg` when `code !== 0`, closes dialogs only on success, and awaits its list reload. Use the existing source-oriented Vitest pattern from `frontend/tests/business-pages.test.ts`.

- [ ] **Step 5: Apply minimal core fixes and rerun both focused suites**

Run: `.venv/bin/pytest tests/test_page_crud_core.py tests/test_master_data.py tests/test_admin.py tests/test_configuration.py tests/test_workflow.py -q`

Run: `npm test -- core-crud-pages.test.ts master-data-api.test.ts system-settings-api.test.ts system-settings-pages.test.ts`

Expected: PASS.

- [ ] **Step 6: Commit only core CRUD files**

```bash
git add backend/tests/test_page_crud_core.py frontend/tests/core-crud-pages.test.ts backend/app/api/master_data.py backend/app/services/master_data_service.py backend/app/api/admin.py backend/app/services/admin_service.py backend/app/api/config.py backend/app/services/configuration_service.py backend/app/api/workflow.py backend/app/services/workflow_service.py frontend/src/views/master-data/MasterDataPage.vue frontend/src/views/system/AdminBasics.vue frontend/src/views/system/UserManagement.vue frontend/src/views/settings/GlobalParameters.vue frontend/src/views/settings/PrintTemplates.vue frontend/src/views/settings/WorkflowConfig.vue frontend/src/views/settings/ApiClientList.vue
git commit -m "fix: repair core page write operations"
```

### Task 3: Verify Sales, Purchase, Inventory, and Finance Write Flows

**Files:**
- Create: `backend/tests/test_page_crud_phase1.py`
- Create: `frontend/tests/phase1-crud-pages.test.ts`
- Modify when proven: `backend/app/api/sales.py`, `backend/app/services/sales_service.py`
- Modify when proven: `backend/app/api/purchase.py`, `backend/app/services/purchase_service.py`
- Modify when proven: `backend/app/api/inventory.py`, `backend/app/services/inventory_service.py`
- Modify when proven: `backend/app/api/finance.py`, `backend/app/services/finance_service.py`
- Modify when proven: `frontend/src/views/sales/SalesOrderList.vue`, `frontend/src/views/DocumentExtensionPage.vue`
- Modify when proven: `frontend/src/views/purchase/PurchaseOrderList.vue`
- Modify when proven: `frontend/src/views/inventory/TransferList.vue`, `frontend/src/views/inventory/CountList.vue`
- Modify when proven: `frontend/src/views/finance/ReceivableList.vue`, `frontend/src/views/finance/PayableList.vue`, `frontend/src/views/finance/ExpenseList.vue`, `frontend/src/views/finance/VoucherList.vue`

**Interfaces:**
- Consumes: phase-one number rules and seed entities; existing sales, purchase, inventory, and finance service state machines.
- Produces: one API-level page flow covering order/quote/return/request creation, inventory transfer/count, receipt/payment/expense, reconciliation, settlement, and voucher creation.

- [ ] **Step 1: Seed deterministic phase-one references with `CODEX-CRUD-` codes**

Use SQLAlchemy models in the test fixture to create customer, supplier, material, two warehouses, starting stock, and required `CfgNumberRule` rows. Keep IDs deterministic so payload assertions are readable.

- [ ] **Step 2: Write one legal state-flow test per writable page**

Test exact page sequences: sales order create/submit/approve/delivery; sales quote create/submit/approve; sales return create; purchase order create/submit/approve/receipt; purchase request create/submit/approve; purchase return create; transfer create/approve/complete; count create/complete; receipt/payment create and reconcile; expense create/approve/settle; voucher generation.

- [ ] **Step 3: Write invalid-transition and missing-reference tests**

Repeat submit/approve/complete calls and pass unknown related IDs. Assert a non-zero business `code`, a non-empty `msg`, and no partial stock or finance mutation.

- [ ] **Step 4: Run focused backend tests and apply transaction-safe fixes**

Run: `.venv/bin/pytest tests/test_page_crud_phase1.py tests/test_sales_flow.py tests/test_purchase_flow.py tests/test_inventory_ledger.py tests/test_finance_flow.py tests/test_business_extensions.py -q`

Expected: PASS after route/schema/service fixes preserve existing state rules.

- [ ] **Step 5: Test page payload construction and refresh behavior**

Use mocked master-option IDs and assert the page sends selected IDs rather than display labels, numeric values as numbers, and item arrays without empty draft rows. Assert failed actions preserve the dialog and successful actions reload the list.

- [ ] **Step 6: Run focused frontend tests**

Run: `npm test -- phase1-crud-pages.test.ts business-api.test.ts business-pages.test.ts navigation-dropdowns.test.ts`

Expected: PASS.

- [ ] **Step 7: Commit only phase-one flow files**

```bash
git add backend/tests/test_page_crud_phase1.py frontend/tests/phase1-crud-pages.test.ts backend/app/api/sales.py backend/app/services/sales_service.py backend/app/api/purchase.py backend/app/services/purchase_service.py backend/app/api/inventory.py backend/app/services/inventory_service.py backend/app/api/finance.py backend/app/services/finance_service.py frontend/src/views/sales frontend/src/views/purchase frontend/src/views/inventory frontend/src/views/finance frontend/src/views/DocumentExtensionPage.vue
git commit -m "fix: repair phase one page write flows"
```

### Task 4: Verify Production, Advanced Inventory, Cost, CRM, Quality, and HR Writes

**Files:**
- Create: `backend/tests/test_page_crud_phase2.py`
- Create: `frontend/tests/phase2-crud-pages.test.ts`
- Modify when proven: `backend/app/api/production.py`, `backend/app/services/production_service.py`, `backend/app/services/planning_service.py`
- Modify when proven: `backend/app/api/inventory_advanced.py`, `backend/app/services/inventory_advanced_service.py`
- Modify when proven: `backend/app/api/cost.py`, `backend/app/services/cost_service.py`
- Modify when proven: `backend/app/api/crm.py`, `backend/app/services/crm_service.py`
- Modify when proven: `backend/app/api/quality.py`, `backend/app/services/quality_service.py`
- Modify when proven: `backend/app/api/hr.py`, `backend/app/services/hr_service.py`
- Modify when proven: all Vue files under `frontend/src/views/production`, `frontend/src/views/inventory-advanced`, `frontend/src/views/cost`, `frontend/src/views/crm`, `frontend/src/views/quality`, and `frontend/src/views/hr`.

**Interfaces:**
- Consumes: phase-two permissions, seeded master references, production and inventory state machines.
- Produces: API and page-source regression coverage for every phase-two write action visible in the router.

- [ ] **Step 1: Write phase-two API page flows**

Cover BOM create/submit/approve/disable; MPS create and MRP run; work-order create/release/issue/report/complete/cancel; location and batch create; scan token/process; cost allocation create/post and period close/reopen; CRM lead and opportunity create/transitions/convert/follow-up; quality inspection create/submit/close; employee create/update/password/attendance; payroll calculate/approve/pay.

- [ ] **Step 2: Assert relationship placement and types**

Explicitly test `warehouse_id` and `material_id` query parameters on location/batch endpoints, `scan_id` idempotency, ISO date strings, decimal-compatible numeric payloads, and non-empty status-transition path segments.

- [ ] **Step 3: Run focused backend phase-two coverage**

Run: `.venv/bin/pytest tests/test_page_crud_phase2.py tests/test_production_planning_phase2.py tests/test_work_order_phase2.py tests/test_inventory_advanced_phase2.py tests/test_scan_phase2.py tests/test_cost_phase2.py tests/test_phase2_people_quality.py -q`

Expected: PASS after minimal fixes.

- [ ] **Step 4: Add page-source tests for action availability and refresh**

Assert every action button is gated by the matching current status, payload validation runs before the request, backend errors remain visible, and successful writes await `load()` before clearing loading state.

- [ ] **Step 5: Run focused frontend phase-two coverage**

Run: `npm test -- phase2-crud-pages.test.ts crm-phase2.test.ts phase2-scan-page.test.ts business-pages.test.ts`

Expected: PASS.

- [ ] **Step 6: Commit only phase-two flow files**

```bash
git add backend/tests/test_page_crud_phase2.py frontend/tests/phase2-crud-pages.test.ts backend/app/api/production.py backend/app/services/production_service.py backend/app/services/planning_service.py backend/app/api/inventory_advanced.py backend/app/services/inventory_advanced_service.py backend/app/api/cost.py backend/app/services/cost_service.py backend/app/api/crm.py backend/app/services/crm_service.py backend/app/api/quality.py backend/app/services/quality_service.py backend/app/api/hr.py backend/app/services/hr_service.py frontend/src/views/production frontend/src/views/inventory-advanced frontend/src/views/cost frontend/src/views/crm frontend/src/views/quality frontend/src/views/hr
git commit -m "fix: repair phase two page write flows"
```

### Task 5: Run Browser-Based Full Page Audit Against Local ERP

**Files:**
- Create: `docs/crud-audit-report.md`
- Modify: only source and focused test files associated with a reproduced browser failure.

**Interfaces:**
- Consumes: local frontend at `http://127.0.0.1:5176`, backend at `http://127.0.0.1:8085`, administrator login, approved `CODEX-CRUD-` data rule.
- Produces: a row for every routed page containing page path, visible write operations, API requests exercised, result, defect/fix reference, and temporary-data disposition.

- [ ] **Step 1: Start or verify backend and frontend services**

Run health and page checks without changing data:

```bash
curl -fsS http://127.0.0.1:8085/api/health
curl -fsS http://127.0.0.1:5176/login
```

- [ ] **Step 2: Create the audit report with all router paths**

Use this exact header and one row for each route in `frontend/src/router/index.ts`:

```markdown
| 页面 | 写操作 | 接口 | 结果 | 修复/说明 | 临时数据 |
|---|---|---|---|---|---|
```

Mark Dashboard, inventory stock/transactions, operation logs, and other truly read-only pages as `只读设计`; do not add write actions to them.

- [ ] **Step 3: Exercise core pages in the browser**

Log in, visit every master-data, administration, profile, and settings page, and exercise all visible write controls with unique `CODEX-CRUD-<module>-<timestamp>` values. Capture request failures and visible error messages before changing code.

- [ ] **Step 4: Exercise phase-one pages in dependency order**

Create master references first, then test sales, purchase, inventory, and finance actions in legal status order. Confirm the list visibly reloads after each successful action and invalid actions show a useful message.

- [ ] **Step 5: Exercise phase-two pages in dependency order**

Test CRM, production, advanced inventory, cost, quality, HR, and platform pages using only audit-created references. Do not force state transitions that violate the existing business workflow.

- [ ] **Step 6: Reproduce every browser failure in an automated test before fixing it**

Place the regression in the matching Task 1-4 test file, run it to observe failure, apply the smallest source patch, rerun to pass, then repeat the browser action.

- [ ] **Step 7: Validate backup/restore UI without restore execution**

Create a backup only if the current page and environment expose the safe backup action. For restore, test empty path, invalid path, wrong confirmation word, and validation success when a known audit backup exists; do not click the final destructive restore confirmation.

- [ ] **Step 8: Clean up only deletable audit records and finish the report**

Delete or deactivate only audit-created records through supported UI/API operations. For audited documents without delete semantics, record their identifiers and status under `临时数据`.

- [ ] **Step 9: Commit the audit report and any browser-derived fixes**

```bash
git add docs/crud-audit-report.md backend/tests frontend/tests backend/app frontend/src
git commit -m "fix: resolve browser-discovered CRUD failures"
```

Before committing, inspect `git diff --cached --name-only` and unstage every file not tied to a recorded browser defect.

### Task 6: Full Regression and Requirement Verification

**Files:**
- Modify: `docs/crud-audit-report.md` only if verification reveals an inaccurate result.

**Interfaces:**
- Consumes: all fixes and tests from Tasks 1-5.
- Produces: fresh evidence for backend tests, frontend tests, type safety, production build, page audit completeness, and preserved unrelated changes.

- [ ] **Step 1: Run all backend verification**

Run: `.venv/bin/pytest -q`

Expected: all tests pass with zero failures.

Run: `.venv/bin/python -m compileall -q app`

Expected: exit code 0.

- [ ] **Step 2: Run all frontend verification**

Run: `npm test`

Expected: all test files and tests pass with zero failures.

Run: `npm run typecheck`

Expected: exit code 0.

Run: `npm run build`

Expected: exit code 0.

- [ ] **Step 3: Verify report completeness against router paths**

Extract quoted `path:` entries from `frontend/src/router/index.ts` and compare them with `docs/crud-audit-report.md`. Every routed page must have exactly one report row or an explicit redirect note.

- [ ] **Step 4: Verify data and worktree safety**

Confirm the report contains no modified/deleted pre-existing record, no real restore execution, and an explicit disposition for every retained `CODEX-CRUD-` business document. Review `git status --short` and `git diff` to ensure unrelated pre-existing changes were not reverted or absorbed.

- [ ] **Step 5: Perform final requirement review**

Check every requirement in `docs/superpowers/specs/2026-08-09-erp-crud-full-audit-design.md` against the report and test evidence. Correct any unsupported report claim before completion.

- [ ] **Step 6: Commit final report corrections only when needed**

```bash
git add docs/crud-audit-report.md
git commit -m "docs: finalize CRUD audit results"
```
