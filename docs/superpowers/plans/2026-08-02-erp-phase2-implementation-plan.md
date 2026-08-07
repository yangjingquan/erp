# ERP 二期全量功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在一期 ERP 核心之上实现二期生产、库存增强、成本、CRM、质检、人事、OpenAPI 和经营看板的可运行业务闭环，并完成自动化自测。

**Architecture:** 沿用现有 FastAPI + SQLAlchemy 模块化单体和 Vue 3 + Pinia + Element Plus 管理端。后端按领域新增模型、schema、service、API 和测试；跨领域能力通过一期编号、审批、库存流水、操作日志和配置服务复用。库存、成本、工资和月结均由 Decimal 计算，外部事件采用本地 outbox。

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2, Pydantic, pytest, SQLite test database, MySQL 8.0, Vue 3, TypeScript, Vite, Element Plus, Pinia, Axios, ECharts, Vitest.

## Global Constraints

- 数据库地址固定为 `127.0.0.1:3306`，数据库名称 `erp`，账号 `root`，密码 `changeme_root`。
- 后端 API 固定运行在 `8085`，前端开发服务器固定运行在 `5176`。
- 后端统一返回 `{"code": 0, "msg": "操作成功", "data": {}}`。
- 所有业务单据使用 UUID 字符串主键、组织字段、审计字段、软删除和乐观锁版本号。
- 库存余额只能通过库存流水更新，不允许业务接口直接修改库存余额。
- 金额、数量、成本、薪资和月结计算使用 `Decimal`，禁止浮点计算。
- 所有高风险写操作记录操作日志并执行当前用户、组织、仓库、项目和数据权限校验。
- 重复提交、重复扫码、重复完工和重复月结必须幂等且不得产生重复流水。
- 业务状态只能通过服务层动作转换；非法状态转换返回统一业务错误。
- `database/init.sql` 必须可重复执行，并创建二期表、索引、外键、唯一约束、默认菜单、编号规则和全局参数。
- 每个新业务行为采用 TDD：先写失败测试、确认失败，再写最小实现并确认通过。
- 当前工作区没有可写 Git 元数据；实施阶段不执行提交，交付时记录文件已保留但无法提交。

## 文件结构与职责

| 文件/目录 | 职责 |
| --- | --- |
| `backend/app/models/production.py` | BOM、MPS/MRP、工单、生产领退料、报工、委外模型 |
| `backend/app/models/inventory_advanced.py` | 库区、库位、批次、成本层、呆滞规则和扫码任务模型 |
| `backend/app/models/cost.py` | 成本分摊、期间、项目和项目成本分录模型 |
| `backend/app/models/crm.py` | 线索、联系人、商机、跟进模型 |
| `backend/app/models/quality.py` | 检验方案、检验单、检验结果和质量异常模型 |
| `backend/app/models/hr.py` | 员工、考勤、薪资规则、薪资单模型 |
| `backend/app/models/platform.py` | API 客户端调用审计、事件 outbox 和看板查询所需模型 |
| `backend/app/services/*_service.py` | 各领域状态机、计算、权限、幂等和来源追踪 |
| `backend/app/api/*.py` | 各领域 REST API，保持统一响应和依赖注入 |
| `backend/tests/test_*_phase2.py` | 后端领域行为、异常、权限和集成测试 |
| `frontend/src/api/*-phase2.ts` | 二期 API 客户端函数，路径与后端路由一一对应 |
| `frontend/src/views/{production,inventory-advanced,cost,crm,quality,hr}` | 二期列表、表单、状态动作和扫码页面 |
| `database/init.sql` | 二期表结构、索引、种子菜单、编号规则、全局参数和模块开关 |

---

### Task 1: 二期基础设施、模型注册和可重复数据库初始化

**Files:**
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/startup_check.py`
- Modify: `database/init.sql`
- Create: `backend/app/models/platform.py`
- Create: `backend/app/services/event_service.py`
- Create: `backend/app/services/phase2_parameter_service.py`
- Create: `backend/tests/test_phase2_foundation.py`

**Interfaces:**
- `emit_event(db: Session, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict) -> ExtEventOutbox`
- `claim_pending_events(db: Session, limit: int = 50) -> list[ExtEventOutbox]`
- `get_phase2_parameter(db: Session, org_id: str, key: str, default: str) -> str`
- `check_schema(db: Session)` must include at least `mfg_bom`, `mfg_work_order`, `inv_location`, `inv_cost_layer`, `cost_period_close`, `crm_lead`, `qa_inspection`, `hr_employee`, and `ext_event_outbox` in the required table set.

- [ ] **Step 1: Write the failing foundation tests**

```python
def test_phase2_tables_are_required_by_schema_contract():
    status = schema_status_from_tables({"sys_user", "sales_order"})
    assert "mfg_bom" in status.missing_tables
    assert "crm_lead" in status.missing_tables

def test_emit_event_is_idempotent_for_same_aggregate_and_type(client_and_session):
    _, session = client_and_session
    first = emit_event(session, "work_order.completed", "mfg_work_order", "wo-1", {"quantity": "2"})
    second = emit_event(session, "work_order.completed", "mfg_work_order", "wo-1", {"quantity": "2"})
    assert first.id == second.id
    assert session.query(ExtEventOutbox).count() == 1
```

- [ ] **Step 2: Run the tests and verify the expected failure**

Run: `cd backend && pytest tests/test_phase2_foundation.py -q`  
Expected: FAIL because the phase-2 model, event service, and schema table requirements do not exist.

- [ ] **Step 3: Implement the minimum foundation**

Register every phase-2 model module before tests call `Base.metadata.create_all`; add an `ExtEventOutbox` model with a unique constraint on `(event_type, aggregate_type, aggregate_id)`. Implement `emit_event` using an existing row lookup followed by insert, `claim_pending_events` using `pending` status and retry timestamp, and parameter lookup with the documented default. Extend `database/init.sql` with the event table, phase-2 module seeds, menu rows, number rules and parameter rows using `CREATE TABLE IF NOT EXISTS` and `ON DUPLICATE KEY UPDATE`.

- [ ] **Step 4: Run the targeted tests and schema compilation**

Run: `cd backend && pytest tests/test_phase2_foundation.py -q && python -m compileall -q app`  
Expected: all foundation tests pass and compilation exits 0.

- [ ] **Step 5: Verify SQL contract without claiming MySQL success**

Run: `rg -n "CREATE TABLE IF NOT EXISTS (mfg_|inv_(zone|location|batch|cost_layer)|cost_|crm_|qa_|hr_|ext_event_outbox)" database/init.sql`  
Expected: every planned phase-2 table appears. If Docker/MySQL is unavailable, record that as an environment limitation for the final report.

---

### Task 2: BOM、MPS 和 MRP 净需求计算

**Files:**
- Create: `backend/app/models/production.py`
- Create: `backend/app/schemas/production.py`
- Create: `backend/app/services/planning_service.py`
- Create: `backend/app/api/production.py`
- Create: `backend/tests/test_production_planning_phase2.py`
- Modify: `backend/app/main.py`
- Modify: `database/init.sql`

**Interfaces:**
- `create_bom(db, payload, context) -> MfgBom`
- `submit_bom(db, bom_id, context) -> MfgBom`
- `approve_bom(db, bom_id, context) -> MfgBom`
- `create_mps(db, payload, context) -> MfgMps`
- `run_mrp(db, mps_id, context) -> MfgMrpRun`
- `confirm_mrp_result(db, result_id, context) -> dict`

- [ ] **Step 1: Write failing tests for BOM lifecycle and MRP math**

```python
def test_approved_bom_mrp_uses_stock_and_open_orders(client_and_session):
    # finished F requires 2x component C; stock=3, open purchase=1, plan=5
    result = run_mrp_for_fixture(plan_quantity=5, bom_quantity=2, stock=3, open_purchase=1)
    assert result.net_requirement == Decimal("6")
    assert result.source_snapshot["available_stock"] == "3"

def test_bom_cannot_be_approved_with_duplicate_component_or_invalid_effective_range(client_and_session):
    response = create_invalid_bom_payload()
    assert response.status_code == 400
    assert "BOM" in response.json()["msg"]
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `cd backend && pytest tests/test_production_planning_phase2.py -q`  
Expected: FAIL because production models, API, and planning service are absent.

- [ ] **Step 3: Implement BOM models, validation, and state transitions**

Create BOM headers/items/versions and MPS/MRP headers/results with UUID, org, audit, status and source fields. Validate component quantities, duplicate component rows, effective dates, circular BOM references and required approved version. Implement `draft → submitted → approved → disabled`; reject modification/deletion when referenced by MRP or work order. Add protected routes for create, submit, approve, list and detail.

- [ ] **Step 4: Implement deterministic MRP calculation**

Snapshot plan quantity, BOM version, stock, open sales/purchase quantities and safety stock. Recursively explode the BOM, calculate `gross_requirement - available_stock - open_supply + safety_stock`, quantize quantities to six decimals, and store every result with the run ID. A second run creates a new run; confirming the same result twice returns the original source document IDs.

- [ ] **Step 5: Run targeted tests and compile**

Run: `cd backend && pytest tests/test_production_planning_phase2.py -q && python -m compileall -q app`  
Expected: BOM lifecycle, MRP net requirement, duplicate confirmation, permission and invalid-input tests pass.

---

### Task 3: 生产工单、领料、退料、报工和完工入库

**Files:**
- Modify: `backend/app/models/production.py`
- Modify: `backend/app/schemas/production.py`
- Create: `backend/app/services/production_service.py`
- Modify: `backend/app/api/production.py`
- Create: `backend/tests/test_work_order_phase2.py`
- Modify: `backend/app/services/inventory_service.py`
- Modify: `backend/app/models/inventory.py`

**Interfaces:**
- `create_work_order(db, payload, context) -> MfgWorkOrder`
- `release_work_order(db, work_order_id, context) -> MfgWorkOrder`
- `issue_material(db, work_order_id, items, context) -> MfgMaterialIssue`
- `return_material(db, issue_id, items, context) -> MfgMaterialReturn`
- `report_work(db, work_order_id, payload, context) -> MfgReport`
- `complete_work_order(db, work_order_id, context) -> MfgWorkOrder`

- [ ] **Step 1: Write failing end-to-end production tests**

```python
def test_work_order_issue_report_complete_updates_inventory_and_is_traceable(client_and_session):
    work_order = create_released_work_order(quantity="5")
    issue = issue_material(work_order.id, [{"material_id": "component-1", "quantity": "10"}])
    report = report_work(work_order.id, {"good_quantity": "5", "scrap_quantity": "0", "hours": "3"})
    completed = complete_work_order(work_order.id)
    assert completed.status == "completed"
    assert count_transactions(source_type="mfg_material_issue", source_id=issue.id) == 1
    assert count_transactions(source_type="mfg_completion", source_id=completed.id) == 1

def test_work_order_rejects_issue_over_bom_quantity_and_double_completion():
    response = issue_material("wo-1", [{"material_id": "component-1", "quantity": "11"}])
    assert response.status_code == 400
    assert complete_work_order("completed-wo").status_code == 400
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `cd backend && pytest tests/test_work_order_phase2.py -q`  
Expected: FAIL because production document services and inventory source extensions do not exist.

- [ ] **Step 3: Implement the work-order state machine and source snapshots**

Implement `draft → released → in_progress → completed` and cancellation from `released`/`in_progress`. Snapshot the approved BOM and plan quantity at creation. Track planned, issued, returned, reported-good, reported-scrap and completed quantities; reject quantity overflow and operations outside the allowed status. Use `post_stock_transaction` for every issue, return and completion and add audit logs.

- [ ] **Step 4: Implement report and completion actions**

Require `good_quantity + scrap_quantity` to be positive and no greater than the work-order quantity. Completion requires released/in-progress status, creates an in-flow transaction for the finished material and emits `work_order.completed` exactly once. Return the existing completion result when the action is retried.

- [ ] **Step 5: Run production flow and existing inventory tests**

Run: `cd backend && pytest tests/test_work_order_phase2.py tests/test_inventory_ledger.py -q`  
Expected: all phase-2 production tests and all一期库存回归 tests pass.

---

### Task 4: 委外订单、委外发料和收货应付来源

**Files:**
- Modify: `backend/app/models/production.py`
- Modify: `backend/app/schemas/production.py`
- Modify: `backend/app/services/production_service.py`
- Modify: `backend/app/api/production.py`
- Create: `backend/tests/test_subcontract_phase2.py`
- Modify: `backend/app/services/finance_service.py`

**Interfaces:**
- `create_subcontract_order(db, payload, context) -> MfgSubcontractOrder`
- `release_subcontract_order(db, order_id, context) -> MfgSubcontractOrder`
- `issue_subcontract_material(db, order_id, items, context) -> MfgMaterialIssue`
- `receive_subcontract_order(db, order_id, payload, context) -> MfgSubcontractReceipt`

- [ ] **Step 1: Write failing委外闭环测试**

```python
def test_subcontract_issue_then_receive_creates_inventory_and_payable_source():
    order = create_subcontract_order(quantity="10", processing_fee="120")
    release_subcontract_order(order.id)
    issue_subcontract_material(order.id, [{"material_id": "raw-1", "quantity": "10"}])
    receipt = receive_subcontract_order(order.id, {"good_quantity": "10", "unit_cost": "12"})
    assert receipt.status == "completed"
    assert count_transactions(source_type="subcontract_receipt", source_id=receipt.id) == 1
    assert find_payable(source_type="subcontract_receipt", source_id=receipt.id).amount == Decimal("120")
```

- [ ] **Step 2: Run the test and verify RED**

Run: `cd backend && pytest tests/test_subcontract_phase2.py -q`  
Expected: FAIL because subcontract models and transitions do not exist.

- [ ] **Step 3: Implement委外 state, material issue, receipt, and payable source**

Use `draft → released → partially_received/completed → cancelled`; validate supplier, material, quantity and processing fee. Repeated release, issue, receipt and payable generation return the existing result. Link issue/receipt/finance rows with `source_type` and `source_id`.

- [ ] **Step 4: Run targeted regression**

Run: `cd backend && pytest tests/test_subcontract_phase2.py tests/test_finance_flow.py -q`  
Expected:委外测试和一期财务测试通过。

---

### Task 5: 库位、批次、FIFO 成本层、呆滞库存和多仓隔离

**Files:**
- Create: `backend/app/models/inventory_advanced.py`
- Create: `backend/app/schemas/inventory_advanced.py`
- Create: `backend/app/services/inventory_advanced_service.py`
- Create: `backend/app/api/inventory_advanced.py`
- Create: `backend/tests/test_inventory_advanced_phase2.py`
- Modify: `backend/app/services/inventory_service.py`
- Modify: `backend/app/models/inventory.py`
- Modify: `backend/app/main.py`
- Modify: `database/init.sql`

**Interfaces:**
- `create_location(db, warehouse_id, zone_id, payload, context) -> InvLocation`
- `create_batch(db, material_id, payload, context) -> InvBatch`
- `post_fifo_inbound(db, source_type, source_id, warehouse_id, location_id, material_id, batch_id, quantity, unit_cost, context) -> list[InvCostLayer]`
- `post_fifo_outbound(db, source_type, source_id, warehouse_id, location_id, material_id, batch_id, quantity, context) -> list[dict]`
- `list_slow_moving(db, context, as_of) -> list[dict]`
- `assert_warehouse_access(context, warehouse_id) -> None`

- [ ] **Step 1: Write failing FIFO and isolation tests**

```python
def test_fifo_outbound_consumes_oldest_layers_and_records_source_layer():
    post_fifo_inbound("receipt", "r1", "wh-1", "loc-1", "m-1", "b-1", "3", "10")
    post_fifo_inbound("receipt", "r2", "wh-1", "loc-1", "m-1", "b-2", "4", "12")
    consumed = post_fifo_outbound("delivery", "d1", "wh-1", "loc-1", "m-1", None, "5")
    assert [(row["quantity"], row["unit_cost"]) for row in consumed] == [("3", "10"), ("2", "12")]

def test_user_cannot_read_or_move_stock_in_unassigned_warehouse():
    assert stock_request("wh-2", user="dept-user").status_code == 403
```

- [ ] **Step 2: Run tests to verify RED**

Run: `cd backend && pytest tests/test_inventory_advanced_phase2.py -q`  
Expected: FAIL because location, batch, cost-layer and warehouse access services are absent.

- [ ] **Step 3: Implement location, batch, stock extension, and FIFO layer allocation**

Add unique `(warehouse_id, code)` location validation, batch expiry/status, and cost layers with `remaining_quantity`. Extend inventory transaction serialization with location, batch and consumed layer IDs. Inbound creates one layer; outbound locks available layers, consumes in `created_at` order, rejects insufficient quantity and emits immutable consumption rows.

- [ ] **Step 4: Implement slow-moving snapshots and warehouse access checks**

Add rules by organization/material/warehouse and compute days since last inbound/outbound without mutating stock. Apply `assert_warehouse_access` to all advanced inventory list and write endpoints, including production and scan calls.

- [ ] **Step 5: Run FIFO,一期库存 and compile tests**

Run: `cd backend && pytest tests/test_inventory_advanced_phase2.py tests/test_inventory_ledger.py -q && python -m compileall -q app`  
Expected: FIFO ordering, insufficient stock, batch/location trace, slow-moving thresholds, multi-warehouse isolation and一期库存 tests pass.

---

### Task 6: 移动 H5 扫码和盘点增强

**Files:**
- Modify: `backend/app/models/inventory_advanced.py`
- Modify: `backend/app/schemas/inventory_advanced.py`
- Modify: `backend/app/services/inventory_advanced_service.py`
- Modify: `backend/app/api/inventory_advanced.py`
- Create: `backend/tests/test_scan_phase2.py`
- Create: `frontend/src/api/inventory-advanced.ts`
- Create: `frontend/src/views/inventory-advanced/Scan.vue`
- Create: `frontend/tests/phase2-scan-page.test.ts`

**Interfaces:**
- `create_scan_token(db, context) -> str`
- `process_scan(db, token, scan_id, action, document_id, payload) -> dict`
- `list_scan_tasks(db, context) -> list[dict]`

- [ ] **Step 1: Write failing idempotent scan tests and page contract**

```python
def test_same_scan_id_returns_same_result_without_duplicate_transaction():
    token = create_scan_token(admin_context)
    first = process_scan(token, "scan-1", "receive", "receipt-1", {"quantity": "2"})
    second = process_scan(token, "scan-1", "receive", "receipt-1", {"quantity": "2"})
    assert first == second
    assert transaction_count(source_type="scan", source_id="scan-1") == 1
```

Frontend test reads `Scan.vue` and asserts it contains `createScanToken`, `processScan`, `scan_id`, and an error message path.

- [ ] **Step 2: Run tests to verify RED**

Run: `cd backend && pytest tests/test_scan_phase2.py -q`; then `cd ../frontend && npm test -- phase2-scan-page.test.ts`  
Expected: both fail because scan API/client/page do not exist.

- [ ] **Step 3: Implement short-lived scan token and action validation**

Bind token to user, organization, warehouse scope and expiration from `scan.token.ttl` parameter. Validate `scan_id` uniqueness, action-specific document status, batch/location and quantity, then call the same inventory service used by desktop APIs. Store and return the original result for retries; reject expired token, wrong warehouse and duplicate document completion.

- [ ] **Step 4: Implement responsive scan page and API client**

Add API functions for token creation, task listing and processing; add a mobile-friendly page with action select, document ID, batch/location, quantity, `scan_id`, loading state and `ElMessage.error`. Do not add a native app dependency.

- [ ] **Step 5: Run targeted tests and frontend typecheck**

Run: `cd backend && pytest tests/test_scan_phase2.py -q && cd ../frontend && npm test -- phase2-scan-page.test.ts && npm run typecheck`  
Expected: all pass.

---

### Task 7: 成本分摊、项目成本和月结

**Files:**
- Create: `backend/app/models/cost.py`
- Create: `backend/app/schemas/cost.py`
- Create: `backend/app/services/cost_service.py`
- Create: `backend/app/api/cost.py`
- Create: `backend/tests/test_cost_phase2.py`
- Modify: `backend/app/services/inventory_advanced_service.py`
- Modify: `backend/app/main.py`
- Modify: `database/init.sql`

**Interfaces:**
- `create_allocation(db, payload, context) -> CostAllocation`
- `post_allocation(db, allocation_id, context) -> CostAllocation`
- `calculate_project_cost(db, project_id, period, context) -> dict`
- `close_period(db, org_id, period, context) -> CostPeriodClose`
- `reopen_period(db, org_id, period, context) -> CostPeriodClose`
- `assert_period_open(db, org_id, business_date) -> None`

- [ ] **Step 1: Write failing cost and period-lock tests**

```python
def test_allocation_by_quantity_preserves_total_and_project_cost():
    allocation = create_allocation({"amount": "100", "basis": "quantity", "items": [{"project_id": "p1", "quantity": "1"}, {"project_id": "p2", "quantity": "3"}]})
    posted = post_allocation(allocation.id)
    assert project_entry("p1").amount == Decimal("25.00")
    assert project_entry("p2").amount == Decimal("75.00")
    assert sum_project_entries(allocation.id) == Decimal("100.00")

def test_close_period_rejects_negative_stock_and_locks_new_cost_events():
    assert close_period("2026-08", with_negative_stock=True).status_code == 400
    close_period("2026-08")
    assert create_allocation_for_date("2026-08-02").status_code == 400
```

- [ ] **Step 2: Run tests to verify RED**

Run: `cd backend && pytest tests/test_cost_phase2.py -q`  
Expected: FAIL because cost models and period services are absent.

- [ ] **Step 3: Implement Decimal allocation and project entries**

Support `quantity`, `amount` and `hours` bases; quantize to cents, assign rounding remainder to the final item, reject zero total basis and preserve allocation source rows. Create project entries with source type/id and include production material, subcontract, labor and expense sources.

- [ ] **Step 4: Implement period close/reopen guards**

Before close, query incomplete production/receipt/delivery documents, negative stock, unposted allocations and unapproved vouchers. Mark period `closed` atomically and call `assert_period_open` from all cost-affecting services. Reopen only with explicit permission and operation log; store close/reopen user and time.

- [ ] **Step 5: Run cost and regression tests**

Run: `cd backend && pytest tests/test_cost_phase2.py tests/test_finance_flow.py tests/test_inventory_advanced_phase2.py -q`  
Expected: all cost, finance and advanced inventory tests pass.

---

### Task 8: CRM 线索、联系人、商机和跟进

**Files:**
- Create: `backend/app/models/crm.py`
- Create: `backend/app/schemas/crm.py`
- Create: `backend/app/services/crm_service.py`
- Create: `backend/app/api/crm.py`
- Create: `backend/tests/test_crm_phase2.py`
- Create: `frontend/src/api/crm.ts`
- Create: `frontend/src/views/crm/LeadList.vue`
- Create: `frontend/src/views/crm/OpportunityList.vue`
- Create: `frontend/tests/crm-phase2.test.ts`
- Modify: `backend/app/main.py`
- Modify: `database/init.sql`

**Interfaces:**
- `create_lead(db, payload, context) -> CrmLead`
- `transition_lead(db, lead_id, status, context) -> CrmLead`
- `convert_lead(db, lead_id, context) -> dict`
- `create_opportunity(db, payload, context) -> CrmOpportunity`
- `transition_opportunity(db, opportunity_id, stage, context) -> CrmOpportunity`
- `add_follow_up(db, opportunity_id, payload, context) -> CrmFollowUp`

- [ ] **Step 1: Write failing CRM behavior and page tests**

```python
def test_lead_conversion_is_idempotent_and_creates_customer_contact_opportunity():
    lead = create_lead({"name": "Acme", "phone": "13800000000"})
    first = convert_lead(lead.id)
    second = convert_lead(lead.id)
    assert first == second
    assert count_customers(name="Acme") == 1
    assert count_contacts(phone="13800000000") == 1
```

Frontend source tests assert the two pages call `listLeads`/`convertLead` and `listOpportunities`/`addFollowUp`, and display `ElMessage.error` on failure.

- [ ] **Step 2: Run tests to verify RED**

Run: `cd backend && pytest tests/test_crm_phase2.py -q`; then `cd ../frontend && npm test -- crm-phase2.test.ts`  
Expected: FAIL because CRM routes, services, clients and pages are absent.

- [ ] **Step 3: Implement CRM models and state transitions**

Add org/owner/department scope fields and unique lead number. Enforce `new → contacted → qualified → converted/lost`, opportunity stage changes, required loss reason, and owner scope. Conversion creates or reuses customer/contact/opportunity and logs source links; won opportunity exposes a source action to一期 sales quote/order without bypassing approval.

- [ ] **Step 4: Implement API clients and Element Plus pages**

Add list/filter/create/transition/convert/follow-up APIs and two pages with pagination, status action confirmation, owner display, and error/loading states. Register CRM routes and menu metadata.

- [ ] **Step 5: Run CRM tests and typecheck**

Run: `cd backend && pytest tests/test_crm_phase2.py -q && cd ../frontend && npm test -- crm-phase2.test.ts && npm run typecheck`  
Expected: all pass.

---

### Task 9: 质检方案、来料/过程/成品检验和质量异常

**Files:**
- Create: `backend/app/models/quality.py`
- Create: `backend/app/schemas/quality.py`
- Create: `backend/app/services/quality_service.py`
- Create: `backend/app/api/quality.py`
- Create: `backend/tests/test_quality_phase2.py`
- Create: `frontend/src/api/quality.ts`
- Create: `frontend/src/views/quality/InspectionList.vue`
- Create: `frontend/tests/quality-phase2.test.ts`
- Modify: `backend/app/main.py`
- Modify: `database/init.sql`

**Interfaces:**
- `create_quality_plan(db, payload, context) -> QaPlan`
- `create_inspection(db, inspection_type, source_type, source_id, context) -> QaInspection`
- `submit_inspection(db, inspection_id, results, context) -> QaInspection`
- `close_inspection(db, inspection_id, disposition, context) -> QaInspection`
- `create_nonconformity(db, inspection_id, payload, context) -> QaNonconformity`

- [ ] **Step 1: Write failing inspection and exception tests**

```python
def test_failed_receipt_inspection_creates_nonconformity_and_cannot_close_without_disposition():
    inspection = create_inspection("incoming", "purchase_receipt", "receipt-1")
    submitted = submit_inspection(inspection.id, [{"item": "appearance", "value": "fail"}])
    assert submitted.status == "failed"
    assert find_nonconformity(inspection.id) is not None
    assert close_inspection(inspection.id, None).status_code == 400
    assert close_inspection(inspection.id, "rework").status == "closed"
```

Frontend source tests assert `InspectionList.vue` exposes inspection type, result submission, disposition, confirmation and error handling.

- [ ] **Step 2: Run tests to verify RED**

Run: `cd backend && pytest tests/test_quality_phase2.py -q`; then `cd ../frontend && npm test -- quality-phase2.test.ts`  
Expected: FAIL because quality models and routes are absent.

- [ ] **Step 3: Implement quality plan and inspection validation**

Store plan item snapshot on inspection, validate numeric bounds and required results, and implement `draft → submitted → passed/failed → closed`. Failed results create exactly one exception; close requires `rework`, `accept`, or `scrap` disposition and emits a source event for downstream inventory/production handling.

- [ ] **Step 4: Implement quality API and page**

Expose plan CRUD, inspection create/list/submit/close and exception list/actions. Add a table with source document, inspection type, result, exception and disposition actions.

- [ ] **Step 5: Run quality regression**

Run: `cd backend && pytest tests/test_quality_phase2.py tests/test_work_order_phase2.py -q && cd ../frontend && npm test -- quality-phase2.test.ts`  
Expected: quality and production source-link tests pass.

---

### Task 10: 员工、考勤和薪资核算

**Files:**
- Create: `backend/app/models/hr.py`
- Create: `backend/app/schemas/hr.py`
- Create: `backend/app/services/hr_service.py`
- Create: `backend/app/api/hr.py`
- Create: `backend/tests/test_hr_phase2.py`
- Create: `frontend/src/api/hr.ts`
- Create: `frontend/src/views/hr/EmployeeList.vue`
- Create: `frontend/src/views/hr/PayrollList.vue`
- Create: `frontend/tests/hr-phase2.test.ts`
- Modify: `backend/app/main.py`
- Modify: `database/init.sql`

**Interfaces:**
- `create_employee(db, payload, context) -> HrEmployee`
- `record_attendance(db, employee_id, payload, context) -> HrAttendance`
- `calculate_payroll(db, period, context) -> HrPayroll`
- `approve_payroll(db, payroll_id, context) -> HrPayroll`
- `pay_payroll(db, payroll_id, context) -> HrPayroll`

- [ ] **Step 1: Write failing salary and approval tests**

```python
def test_payroll_uses_decimal_rules_and_recalculates_only_before_approval():
    payroll = calculate_payroll("2026-08", employee={"base": "1000.00", "allowance": "100.10", "absence_days": "1"})
    assert payroll.total_amount == Decimal("1050.10")
    approve_payroll(payroll.id)
    assert calculate_payroll(payroll.period).status_code == 400
    assert pay_payroll(payroll.id).status == "paid"
```

Frontend source tests assert employee and payroll pages call the matching APIs, show status transitions, and use confirmation before pay.

- [ ] **Step 2: Run tests to verify RED**

Run: `cd backend && pytest tests/test_hr_phase2.py -q`; then `cd ../frontend && npm test -- hr-phase2.test.ts`  
Expected: FAIL because HR models, services, routes and pages are absent.

- [ ] **Step 3: Implement employee, attendance and salary rules**

Store employee employment status and organization/departments; reject attendance for inactive employees and duplicate sign-in/out for the same day. Snapshot salary rules and Decimal inputs on payroll calculation, produce itemized deductions/allowances, and enforce `draft → calculated → approved → paid` with workflow/permission checks.

- [ ] **Step 4: Implement HR API and pages**

Add employee CRUD/status, attendance record/list, salary rule configuration, payroll calculate/list/approve/pay endpoints and pages. Hide salary fields unless permission `hr:salary:view` is present; backend still rejects unauthorized salary reads/writes.

- [ ] **Step 5: Run HR tests and frontend validation**

Run: `cd backend && pytest tests/test_hr_phase2.py -q && cd ../frontend && npm test -- hr-phase2.test.ts && npm run typecheck`  
Expected: all pass.

---

### Task 11: OpenAPI 客户端、scope、事件 outbox 查询和经营看板增强

**Files:**
- Modify: `backend/app/models/platform.py`
- Create: `backend/app/schemas/platform.py`
- Create: `backend/app/services/openapi_service.py`
- Modify: `backend/app/services/event_service.py`
- Modify: `backend/app/services/dashboard_service.py`
- Create: `backend/app/api/platform.py`
- Modify: `backend/app/api/dashboard.py`
- Create: `backend/tests/test_platform_phase2.py`
- Create: `backend/tests/test_dashboard_phase2.py`
- Create: `frontend/src/api/platform.ts`
- Modify: `frontend/src/api/dashboard.ts`
- Modify: `frontend/src/views/Dashboard.vue`
- Create: `frontend/src/views/settings/ApiClientList.vue`
- Create: `frontend/tests/platform-dashboard-phase2.test.ts`
- Modify: `backend/app/main.py`
- Modify: `database/init.sql`

**Interfaces:**
- `create_api_client(db, payload, context) -> tuple[SysApiClient, str]`
- `issue_api_token(db, client_key, client_secret, scope) -> str`
- `authorize_api_token(db, token, required_scope) -> ApiClientContext`
- `list_events(db, context, status: str | None = None) -> list[dict]`
- `dashboard_phase2(db, context, period: str, warehouse_id: str | None = None) -> dict`

- [ ] **Step 1: Write failing scope, outbox and metric-source tests**

```python
def test_disabled_api_client_and_missing_scope_are_rejected():
    client, secret = create_api_client({"scopes": ["crm:read"]})
    token = issue_api_token(client.client_key, secret, "crm:read")
    assert authorize_api_token(token, "finance:read").status_code == 403
    disable_api_client(client.id)
    assert authorize_api_token(token, "crm:read").status_code == 401

def test_dashboard_returns_source_and_update_metadata():
    data = dashboard_phase2(period="2026-08")
    assert {"production", "inventory", "crm", "quality", "hr", "project_cost"} <= data.keys()
    assert "source" in data["production"]
    assert "updated_at" in data["production"]
```

Frontend source tests assert `Dashboard.vue` contains the phase-2 metric keys and `ApiClientList.vue` uses create/disable confirmation.

- [ ] **Step 2: Run tests to verify RED**

Run: `cd backend && pytest tests/test_platform_phase2.py tests/test_dashboard_phase2.py -q`; then `cd ../frontend && npm test -- platform-dashboard-phase2.test.ts`  
Expected: FAIL because the platform services, endpoints, metric aggregation and pages are incomplete.

- [ ] **Step 3: Implement secure API clients and audit**

Hash client secrets with bcrypt, issue short-lived JWTs bound to client/org/scopes, reject expired/disabled clients, and record request ID, endpoint, status, duration and resource ID. Add client list/create/disable endpoints with permission checks; never return the stored secret hash.

- [ ] **Step 4: Implement outbox claiming and dashboard aggregation**

Expose pending/failed event queries and retry action with retry count update. Add dashboard aggregations from actual production, FIFO, slow-moving, finance, CRM, quality, HR and project-cost tables; return zero/empty values for no data and include period, org, source and update timestamp.

- [ ] **Step 5: Implement frontend dashboard and client page**

Add phase-2 API functions, dashboard filters, ECharts cards/charts using the existing theme adapter, and API-client management with confirmation before disable. Keep salary/cost series behind field permissions.

- [ ] **Step 6: Run platform tests and compile**

Run: `cd backend && pytest tests/test_platform_phase2.py tests/test_dashboard_phase2.py -q && python -m compileall -q app && cd ../frontend && npm test -- platform-dashboard-phase2.test.ts && npm run typecheck`  
Expected: all pass.

---

### Task 12: 二期前端菜单、共享页面状态和全量集成测试

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/stores/permission.ts`
- Modify: `frontend/src/layouts/AdminLayout.vue`
- Create: `frontend/src/api/production.ts`
- Create: `frontend/src/api/cost.ts`
- Create: `frontend/src/api/inventory-advanced.ts`
- Create: `frontend/src/api/quality.ts`
- Create: `frontend/src/api/hr.ts`
- Create: `frontend/src/views/production/BomList.vue`
- Create: `frontend/src/views/production/MrpRunList.vue`
- Create: `frontend/src/views/production/WorkOrderList.vue`
- Create: `frontend/src/views/inventory-advanced/LocationList.vue`
- Create: `frontend/src/views/inventory-advanced/BatchList.vue`
- Create: `frontend/src/views/cost/AllocationList.vue`
- Create: `frontend/src/views/cost/PeriodClose.vue`
- Create: `frontend/src/views/quality/InspectionList.vue`
- Create: `frontend/src/views/hr/EmployeeList.vue`
- Create: `frontend/tests/phase2-routes.test.ts`
- Create: `frontend/tests/phase2-api-contract.test.ts`
- Create: `backend/tests/test_phase2_e2e.py`

**Interfaces:**
- Router metadata uses `permission: string` for every phase-2 route and the existing guard redirects unauthorized users to `/403`.
- Each API module exports `list`, `create`, and lifecycle functions whose endpoint paths match Tasks 2–11.
- `run_phase2_e2e(session) -> dict` returns IDs for BOM, MRP, work order, FIFO consumption, project cost, CRM conversion, inspection and payroll.

- [ ] **Step 1: Write failing route/API contract and end-to-end tests**

```python
def test_phase2_business_chain_has_all_expected_source_links(client_and_session):
    result = run_phase2_e2e(client_and_session)
    assert result["work_order"]["source_type"] == "mrp_result"
    assert result["completion"]["source_type"] == "mfg_work_order"
    assert result["project_cost"]["source_type"] in {"mfg_material_issue", "subcontract_receipt"}
    assert result["crm_conversion"]["customer_id"]
    assert result["inspection"]["source_id"] == result["completion"]["id"]
```

Frontend tests assert every phase-2 route is present and each destructive action uses `ConfirmDialog` or `ElMessageBox.confirm`.

- [ ] **Step 2: Run tests to verify RED**

Run: `cd backend && pytest tests/test_phase2_e2e.py -q`; then `cd ../frontend && npm test -- phase2-routes.test.ts phase2-api-contract.test.ts`  
Expected: FAIL because the cross-domain fixture and full route/menu registration are incomplete.

- [ ] **Step 3: Implement route/menu registration and shared API clients**

Register all documented `/api/phase2` route modules and add front-end routes for production, advanced inventory, cost, CRM, quality, HR, scan and API clients. Use existing auth/permission stores and lazy page imports. Add list/filter/pagination loading and error handling in pages without duplicating backend business rules.

- [ ] **Step 4: Implement the SQLite phase-2 end-to-end fixture**

Create one deterministic fixture using the existing `client_and_session` pattern. Seed materials, customer, supplier, warehouse, user permissions, BOM, stock layers and approved parameter rows; call the public service/API actions in order and assert every downstream source link, balance, status and idempotency result.

- [ ] **Step 5: Run full backend and frontend checks**

Run:

```bash
cd backend
pytest -q
python -m compileall -q app
cd ../frontend
npm test
npm run typecheck
npm run build
```

Expected: all existing一期 tests plus all二期 tests pass, TypeScript emits no errors, and Vite build exits 0.

- [ ] **Step 6: Perform SQL/MySQL acceptance checks**

When Docker/MySQL is available, run:

```bash
docker exec -i shop-mysql mysql --user=root --password=changeme_root --default-character-set=utf8mb4 < database/init.sql
docker exec shop-mysql mysql --user=root --password=changeme_root erp -e "SHOW TABLES;"
```

Then call `/api/health`, verify schema status, inspect required indexes/foreign keys and exercise one production-to-cost flow against MySQL. If Docker is unavailable, report the exact permission or connection error and retain the successful SQLite/test/build evidence separately.

## Self-review checklist

- [ ] BOM/MPS/MRP、工单、报工、委外由 Tasks 2–4 覆盖。
- [ ] 库位/FIFO/批次、呆滞、扫码、多仓由 Tasks 5–6 覆盖。
- [ ] 成本分摊、月结、项目成本由 Task 7 覆盖。
- [ ] CRM、质检、人事由 Tasks 8–10 覆盖。
- [ ] OpenAPI、事件 outbox、经营看板、全局参数由 Tasks 1 和 11 覆盖。
- [ ] 数据库初始化、权限、前端页面、路由、TypeScript、构建和完整回归由 Tasks 1 和 12 覆盖。
- [ ] 每个业务任务都有失败测试、RED 命令、最小实现边界和 GREEN 命令。
- [ ] 计划没有占位式任务描述，所有跨任务接口都已在对应任务的 Interfaces 区域定义。
