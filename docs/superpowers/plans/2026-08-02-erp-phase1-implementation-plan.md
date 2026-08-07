# ERP 一期核心交付 Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 在当前空工作区实现一期可运行的模块化 ERP 核心系统，包含数据库初始化、JWT/RBAC、主数据、销售采购库存闭环、基础财务联动、配置化审批、前端管理壳、备份恢复和部署文档。

**Architecture:** 使用 FastAPI 模块化单体后端和 Vue3 管理前端。后端按 api/schema/service/repository/model 分层，库存与财务通过显式业务服务和单据来源字段解耦；前端按 layout/store/view/api/component 分层。数据库使用 MySQL 8.0，所有业务单据使用 UUID 主键、可配置单据编号和状态流转。

**Tech Stack:** Vue 3, TypeScript, Vite, Element Plus, Vue Router 4, Pinia, Axios, ECharts, Python 3.11+, FastAPI, SQLAlchemy ORM, Pydantic Settings, PyJWT, bcrypt, PyMySQL, pytest, MySQL 8.0.

## Global Constraints

- 数据库地址固定为 127.0.0.1:3306，数据库名称 erp，账号 root，密码 changeme_root。
- 后端 API 固定运行在 8085，Swagger 地址为 http://127.0.0.1:8085/docs。
- 前端开发服务器固定运行在 5176。
- 后端统一返回 {"code": int, "msg": "string", "data": any}。
- 用户密码只能使用 bcrypt 哈希存储，禁止明文密码。
- 前端路由守卫和 Axios 请求拦截器必须启用，后端必须再次校验权限。
- 删除、作废、清空、恢复和数据库恢复必须二次确认。
- 库存余额只能通过库存流水更新，不允许业务接口直接修改库存余额。
- 所有高风险写操作记录操作日志，并携带当前用户、组织、部门和数据权限上下文。
- 数据库初始化必须可重复执行，并在未初始化时给出明确指引。
- 采用 TDD：每个业务行为先写失败测试、确认失败，再写最小实现。
- 在当前工作区没有可写 Git 元数据；无法提交时必须保留文件并在交付说明中记录。

---

### Task 1: 建立工程脚手架与运行配置

**Files:**
- Create: backend/requirements.txt
- Create: backend/app/main.py
- Create: backend/app/core/config.py
- Create: backend/app/core/database.py
- Create: backend/app/core/response.py
- Create: backend/app/core/exceptions.py
- Create: backend/app/middleware/request_context.py
- Create: backend/app/middleware/error_handler.py
- Create: backend/.env.example
- Create: frontend/package.json
- Create: frontend/vite.config.ts
- Create: frontend/tsconfig.json
- Create: frontend/src/main.ts
- Create: frontend/src/App.vue
- Create: frontend/.env.example
- Test: backend/tests/test_health.py

**Interfaces:**
- backend app exports FastAPI instance named app.
- get_settings() returns typed Settings with database URL, JWT settings, host, port, and CORS origins.
- get_db() yields a SQLAlchemy Session.
- ok(data, msg) and fail(code, msg, data) return the unified response shape.
- GET /api/health returns code 0 and database status.

- [ ] Step 1: Write a failing health test.

~~~python
from fastapi.testclient import TestClient
from app.main import app

def test_health_uses_unified_response_shape():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert set(response.json()) == {"code", "msg", "data"}
~~~

- [ ] Step 2: Run cd backend && pytest tests/test_health.py -q and verify it fails because the app package and route do not exist.
- [ ] Step 3: Add typed settings, SQLAlchemy engine/session factory, FastAPI app, CORS for port 5176, request ID middleware, exception handlers, and health route.
- [ ] Step 4: Run the same test and then python -m compileall app; expect the test to pass and compilation to exit 0.
- [ ] Step 5: Add minimal Vite/TypeScript startup files and verify npm run build from frontend after dependencies are installed.

---

### Task 2: Implement MySQL initialization SQL and schema version check

**Files:**
- Create: database/init.sql
- Create: backend/app/models/base.py
- Create: backend/app/models/system.py
- Create: backend/app/services/startup_check.py
- Create: backend/tests/test_schema_contract.py

**Interfaces:**
- database/init.sql creates database erp and all first-phase tables idempotently.
- check_schema(session) returns a structured health result with initialized boolean and missing tables.
- Core models expose UUID string IDs, audit fields, soft delete, status, and optimistic version fields.

- [ ] Step 1: Write a failing contract test asserting required tables include sys_user, sys_role, md_material, sales_order, purchase_order, inv_stock, fin_voucher, wf_definition, cfg_number_rule, and sys_operation_log.
- [ ] Step 2: Run the test without a configured MySQL server; verify it fails with the expected missing-schema result rather than an import error.
- [ ] Step 3: Write database/init.sql with CREATE DATABASE IF NOT EXISTS, UTF-8 settings, system/masters/sales/purchase/inventory/finance/workflow/config/log/extension tables, indexes, foreign keys, uniqueness constraints, default menus/roles, and bcrypt-hashed admin seed.
- [ ] Step 4: Implement startup_check.py so the application distinguishes connection failure from uninitialized schema and emits ERP 数据库未初始化，请先执行 database/init.sql.
- [ ] Step 5: Run mysql --host=127.0.0.1 --port=3306 --user=root --password=changeme_root < database/init.sql when MySQL is available; then run the schema contract test and query the seeded admin row to verify the password column is not the plaintext password.
- [ ] Step 6: Add .env.example values for the fixed database and ports.

---

### Task 3: Implement authentication, JWT, bcrypt and RBAC

**Files:**
- Create: backend/app/models/auth.py
- Create: backend/app/schemas/auth.py
- Create: backend/app/core/security.py
- Create: backend/app/api/auth.py
- Create: backend/app/api/dependencies.py
- Create: backend/app/services/auth_service.py
- Create: backend/tests/test_auth.py
- Create: backend/tests/test_permissions.py

**Interfaces:**
- hash_password(password: str) -> str uses bcrypt.
- verify_password(password: str, hashed: str) -> bool.
- create_access_token(user_id: str, permissions: list[str]) -> str.
- POST /api/auth/login accepts username/password and returns access_token, refresh_token, user.
- GET /api/auth/me returns current user.
- POST /api/auth/change-password validates old password and stores a new bcrypt hash.
- require_permission(permission: str) and require_data_scope(resource: str) are FastAPI dependencies.

- [ ] Step 1: Write failing tests for successful login, invalid password, bcrypt non-plaintext storage, missing token, button permission rejection, and own-department row filtering.
- [ ] Step 2: Run cd backend && pytest tests/test_auth.py tests/test_permissions.py -q; verify failures are caused by missing auth behavior.
- [ ] Step 3: Implement security helpers, login service, JWT claims, refresh token rotation, current-user dependency, RBAC tables, role/menu/permission joins, and data-scope query helpers.
- [ ] Step 4: Run the tests and confirm all auth and permission tests pass.
- [ ] Step 5: Keep authentication behavior independent from audit persistence; Task 4 will attach login success, login failure, password change, and token refresh events to the audit service.

---

### Task 4: Implement system metadata, unified logs and generic CRUD foundations

**Files:**
- Create: backend/app/models/logging.py
- Create: backend/app/schemas/common.py
- Create: backend/app/repositories/base.py
- Create: backend/app/services/audit_service.py
- Create: backend/app/api/system.py
- Create: backend/tests/test_audit_log.py
- Create: backend/tests/test_common_response.py

**Interfaces:**
- BaseRepository provides list(filters, page, page_size), get(id), create, update, soft_delete with data-scope filtering.
- write_operation_log(user, action, resource, target_id, detail) persists a JSON detail.
- All API errors use the response contract and include a request ID in server logs.
- DELETE endpoints use soft deletion and refuse deletion of referenced master records.

- [ ] Step 1: Write failing tests for the unified error response, operation log creation, and referenced-record deletion rejection.
- [ ] Step 2: Run the tests and verify they fail before the repository and log service exist.
- [ ] Step 3: Implement base repository, error types, global exception handler, audit service, and system log endpoints.
- [ ] Step 4: Run the tests and verify the response shape, status codes, and persisted audit rows.
- [ ] Step 5: Wire audit logging into every mutating service through a small service helper rather than duplicating log construction.
- [ ] Step 6: Attach login success, login failure, password change, and token refresh events to the same audit service, then rerun the authentication tests.

---

### Task 5: Implement master data and Excel import/export

**Files:**
- Create: backend/app/models/master_data.py
- Create: backend/app/schemas/master_data.py
- Create: backend/app/services/master_data_service.py
- Create: backend/app/api/master_data.py
- Create: backend/tests/test_master_data.py
- Create: frontend/src/api/master-data.ts
- Create: frontend/src/views/master-data/MaterialList.vue
- Create: frontend/src/views/master-data/CustomerList.vue
- Create: frontend/src/views/master-data/SupplierList.vue
- Create: frontend/src/views/master-data/WarehouseList.vue

**Interfaces:**
- MasterDataService supports material, customer, supplier, warehouse, unit, and tax rate CRUD.
- POST /api/master/{resource}/import accepts an XLSX upload and returns created_count, skipped_count, and errors.
- GET /api/master/{resource}/export returns an XLSX stream.
- Duplicate checks use business code and normalized name.
- List endpoints apply current-user row scope.

- [ ] Step 1: Write failing tests for duplicate material code, normalized duplicate customer name, valid import rows, invalid import row reporting, and export headers.
- [ ] Step 2: Run cd backend && pytest tests/test_master_data.py -q and verify the expected failures.
- [ ] Step 3: Implement models, validation schemas, Excel parsing with openpyxl, duplicate checks, transaction rollback for invalid rows, and export generation.
- [ ] Step 4: Run tests and verify import/export and duplicate behavior.
- [ ] Step 5: Implement Element Plus master data tables with search, pagination, modal form, import/export buttons, and dangerous-operation confirmation.

---

### Task 6: Implement configuration services, numbering, fields, workflows and printable templates

**Files:**
- Create: backend/app/models/configuration.py
- Create: backend/app/models/workflow.py
- Create: backend/app/schemas/configuration.py
- Create: backend/app/services/number_rule_service.py
- Create: backend/app/services/field_config_service.py
- Create: backend/app/services/workflow_service.py
- Create: backend/app/services/print_template_service.py
- Create: backend/app/api/config.py
- Create: backend/app/api/workflow.py
- Create: backend/tests/test_configuration.py
- Create: backend/tests/test_workflow.py

**Interfaces:**
- next_doc_no(rule_key, org_id, date) -> str is concurrency-safe and honors prefix/date/sequence reset.
- get_field_definition(business_type, field_key, user) returns visibility, required, readonly, and permission metadata.
- start_workflow(business_type, business_id, user) -> workflow_instance_id.
- approve_task(task_id, user, comment) and reject_task(task_id, user, comment) enforce current-node approver.
- render_print_template(template_id, document) -> printable HTML.

- [ ] Step 1: Write failing tests for number sequence uniqueness, field permission hiding, approval node transition, rejection return, and printable HTML output.
- [ ] Step 2: Run the targeted tests and confirm they fail before implementation.
- [ ] Step 3: Implement configuration models, transactional sequence allocation, workflow node transitions, approver resolution, and template rendering.
- [ ] Step 4: Run tests and verify concurrent number requests do not duplicate doc_no.
- [ ] Step 5: Add configuration and workflow pages to the frontend with ordered node controls, explicit save, and preview actions.

---

### Task 7: Implement sales and purchase document services

**Files:**
- Create: backend/app/models/sales.py
- Create: backend/app/models/purchase.py
- Create: backend/app/schemas/sales.py
- Create: backend/app/schemas/purchase.py
- Create: backend/app/services/sales_service.py
- Create: backend/app/services/purchase_service.py
- Create: backend/app/api/sales.py
- Create: backend/app/api/purchase.py
- Create: backend/tests/test_sales_flow.py
- Create: backend/tests/test_purchase_flow.py

**Interfaces:**
- create_sales_order(payload, user) -> SalesOrder.
- submit_sales_order(order_id, user) -> SalesOrder.
- approve_sales_order(order_id, user) -> SalesOrder.
- create_delivery_from_order(order_id, user) -> SalesDelivery.
- create_sales_return(payload, user) -> SalesReturn.
- create_purchase_request, create_purchase_order, approve_purchase_order, create_receipt_from_order, and create_purchase_return provide equivalent purchase behavior.
- Document status transitions reject illegal transitions with a business error.

- [ ] Step 1: Write failing integration tests for sales order draft → submit → approve → delivery, return rejection after completion, purchase order → receipt, and row-level owner visibility.
- [ ] Step 2: Run the tests and verify they fail because document services are absent.
- [ ] Step 3: Implement header/detail models, source mapping, status machine, validation for customer/supplier/material/warehouse, configured doc_no generation, and workflow hooks.
- [ ] Step 4: Run both flow test files and verify valid transitions create downstream documents while invalid transitions are rejected.
- [ ] Step 5: Add sales and purchase list/detail/form views with copy-fill, line item editing, submit/approve/reject actions, export and print actions.

---

### Task 8: Implement inventory ledger, transfer, count and safety warnings

**Files:**
- Create: backend/app/models/inventory.py
- Create: backend/app/schemas/inventory.py
- Create: backend/app/services/inventory_service.py
- Create: backend/app/api/inventory.py
- Create: backend/tests/test_inventory_ledger.py
- Create: frontend/src/views/inventory/StockList.vue
- Create: frontend/src/views/inventory/TransactionList.vue
- Create: frontend/src/views/inventory/TransferList.vue
- Create: frontend/src/views/inventory/CountList.vue

**Interfaces:**
- post_stock_transaction(source_type, source_id, warehouse_id, material_id, quantity, direction, user) updates ledger and balance atomically.
- create_transfer(payload, user), approve_transfer(id, user), complete_transfer(id, user).
- create_count(payload, user), complete_count(id, user) generates count adjustment transactions.
- list_stock(filters, user) applies warehouse and row data scope.
- list_safety_warnings(user) returns below-minimum stock.

- [ ] Step 1: Write failing tests for outbound insufficient stock, inbound balance increase, transfer net zero, count adjustment, ledger immutability, and safety warning threshold.
- [ ] Step 2: Run the tests and confirm failures.
- [ ] Step 3: Implement inventory transactions with row locks, decimal arithmetic, transaction source uniqueness, balance updates, transfer and count state machines.
- [ ] Step 4: Run inventory tests and verify every balance change has a corresponding ledger row.
- [ ] Step 5: Implement inventory tables, warning badge, transfer/count forms, and dangerous-operation confirmations.

---

### Task 9: Implement receivables, payables and automatic vouchers

**Files:**
- Create: backend/app/models/finance.py
- Create: backend/app/schemas/finance.py
- Create: backend/app/services/finance_service.py
- Create: backend/app/services/voucher_service.py
- Create: backend/app/api/finance.py
- Create: backend/tests/test_finance_flow.py

**Interfaces:**
- create_receivable_from_sales_delivery(delivery_id, user) -> Receivable.
- create_payable_from_purchase_receipt(receipt_id, user) -> Payable.
- create_receipt(payload, user) and reconcile_receivable(receipt_id, receivable_id, amount, user).
- create_payment(payload, user) and reconcile_payable(payment_id, payable_id, amount, user).
- create_expense(payload, user) -> Expense.
- generate_voucher(source_type, source_id, user) -> Voucher.
- Voucher entries use debit/credit balance validation and source uniqueness.

- [ ] Step 1: Write failing tests for sales receivable generation, purchase payable generation, partial reconciliation, over-reconciliation rejection, expense approval/settlement, voucher debit-credit equality, and source voucher idempotency.
- [ ] Step 2: Run the tests and verify failures.
- [ ] Step 3: Implement finance models, decimal amount validation, reconciliation allocation, expense flow, fixed asset registration, and voucher generation from document type mappings.
- [ ] Step 4: Run finance tests and verify balances, partial allocations, and automatic vouchers.
- [ ] Step 5: Add finance pages for receivables, payables, receipts, payments, expenses, fixed assets, and vouchers.

---

### Task 10: Implement frontend shell, routing, permissions and themes

**Files:**
- Create: frontend/src/router/index.ts
- Create: frontend/src/stores/auth.ts
- Create: frontend/src/stores/app.ts
- Create: frontend/src/stores/permission.ts
- Create: frontend/src/api/http.ts
- Create: frontend/src/layouts/AdminLayout.vue
- Create: frontend/src/views/Login.vue
- Create: frontend/src/views/Dashboard.vue
- Create: frontend/src/components/PermissionButton.vue
- Create: frontend/src/components/ConfirmDialog.vue
- Create: frontend/src/components/ThemeToggle.vue
- Create: frontend/src/styles/theme.css
- Create: frontend/tests/router-guard.test.ts

**Interfaces:**
- http client uses baseURL http://127.0.0.1:8085/api and attaches access token.
- auth store exposes login, logout, refresh, changePassword, and currentUser.
- permission store exposes menuTree, hasPermission, and loadMenus.
- router guard redirects unauthenticated users to /login and unauthorized users to /403.
- app store toggles sidebar and theme.
- ConfirmDialog requires explicit confirmation before destructive callbacks.

- [ ] Step 1: Write failing router guard tests for unauthenticated redirect and authenticated menu access.
- [ ] Step 2: Run cd frontend && npm test -- router-guard.test.ts and verify failure before implementation.
- [ ] Step 3: Implement Axios interceptors, stores, route metadata, guard, admin layout, login form, theme variables, dark-mode ECharts palette, and confirmation component.
- [ ] Step 4: Run the route tests and npm run build; verify both pass.
- [ ] Step 5: Add menu rendering from backend permissions and verify a hidden button cannot be triggered through UI state alone because the backend also rejects it.

---

### Task 11: Implement dashboard, global search, backup/restore and system settings

**Files:**
- Create: backend/app/services/dashboard_service.py
- Create: backend/app/services/search_service.py
- Create: backend/app/services/backup_service.py
- Create: backend/app/api/dashboard.py
- Create: backend/app/api/search.py
- Create: backend/app/api/backup.py
- Create: backend/tests/test_dashboard_search_backup.py
- Create: frontend/src/views/system/OperationLog.vue
- Create: frontend/src/views/system/BackupRestore.vue
- Create: frontend/src/views/settings/GlobalParameters.vue
- Create: frontend/src/views/settings/PrintTemplates.vue

**Interfaces:**
- GET /api/dashboard/overview returns scoped sales, purchase, inventory, receivable, payable and warning metrics.
- GET /api/search?q=... returns scoped records across master data and document numbers.
- POST /api/system/backup invokes mysqldump with an explicit database target and records a backup row.
- POST /api/system/restore requires a second confirmation token, validates a backup file, and records restore audit data.
- GET/PUT /api/system/parameters manages global parameters.

- [ ] Step 1: Write failing tests for scoped dashboard totals, keyword search across resource types, backup command target validation, restore confirmation requirement, and audit rows.
- [ ] Step 2: Run the tests and verify expected failures.
- [ ] Step 3: Implement scoped aggregations, search adapters, safe explicit mysqldump/mysql subprocess invocation, file validation, and audit logging.
- [ ] Step 4: Run tests and verify no backup/restore command can target an unresolved broad path or database.
- [ ] Step 5: Add ECharts dashboard cards and charts, logs, backup/restore, global parameters and print template pages.

---

### Task 12: Finish README, environment checks and end-to-end verification

**Files:**
- Create: README.md
- Create: backend/pytest.ini
- Create: frontend/eslint.config.js
- Create: backend/tests/test_e2e_phase1.py
- Create: frontend/tests/smoke-build.test.ts
- Modify: backend/app/main.py
- Modify: frontend/package.json

**Interfaces:**
- README documents installation, fixed ports, database initialization, default admin, startup order, backup/restore, and troubleshooting.
- Phase-one E2E test proves sales and purchase flows reach inventory and finance.
- CI-like local commands are copyable and use no unresolved environment variables.

- [ ] Step 1: Write the E2E test for sales order → delivery → stock decrease → receivable → receipt reconciliation → voucher, and the equivalent purchase flow.
- [ ] Step 2: Run the E2E test with a clean initialized MySQL schema and verify any failure is a real missing business behavior.
- [ ] Step 3: Implement the minimal missing integration wiring, seed data, and frontend smoke build configuration.
- [ ] Step 4: Run the complete verification set.

~~~text
cd backend
python -m compileall app
pytest -q

cd ../frontend
npm run typecheck
npm run build
~~~

- [ ] Step 5: Run a manual smoke check against local services on ports 8085 and 5176: login, menu loading, one master record, one sales flow, one purchase flow, theme switch, permission rejection, export, print preview, backup prompt.
- [ ] Step 6: Record the final file tree, verification output, and any environment limitation such as MySQL not running. If Git metadata becomes writable, create a commit for the phase-one delivery; otherwise leave the working tree files intact and state that the commit could not be created.

## Plan self-review

Coverage mapping:

- Fixed database and initialization SQL: Task 2.
- Backend connectivity and uninitialized guidance: Tasks 1-2.
- JWT, bcrypt, three-level RBAC, route guard, Axios token and expiry: Tasks 3 and 10.
- Unified response, CORS, Swagger, exceptions and logs: Tasks 1 and 4.
- Configuration-first fields, workflow, numbering and printing: Task 6.
- Master data and import/export: Task 5.
- Sales, purchase, inventory and ledger closure: Tasks 7-8.
- Receivables, payables, payments, expenses, assets and vouchers: Task 9.
- Dashboard, search, backup/restore and global settings: Task 11.
- README, ports, verification and deliverables: Task 12.
- Phase-two and phase-three base tables and extension points: Task 2, with full work deferred to subsequent plans.

No placeholder implementation step is used. Every task identifies files, interfaces, a failing test, a failure command, implementation work and a verification command.
