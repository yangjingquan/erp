# ERP 二期全量功能设计

日期：2026-08-02  
范围：一期核心系统之上的二期生产、库存增强、成本、CRM、质检、人事、平台增强  
状态：设计已确认，待实施计划

## 1. 目标与边界

二期在一期 FastAPI + SQLAlchemy 模块化单体和 Vue 3 管理端上补齐可运行的业务闭环。每个模块都必须有后端模型、服务、API、权限、初始化 SQL、前端页面和自动化测试；不只提供空表或页面占位。

二期包含：

- 生产：物料清单 BOM、主生产计划 MPS、物料需求计划 MRP、生产工单、领料、退料、完工入库、报工、委外。
- 库存与成本：库区/库位、批次和 FIFO 成本层、呆滞库存、移动 H5 扫码接口、成本分摊、月结、项目成本、多仓隔离。
- 业务扩展：CRM 线索、客户联系人、商机、跟进；来料/过程/成品质检和质量异常；员工、考勤、薪资核算。
- 平台增强：API 客户端与 scope 鉴权、业务事件出站、经营看板增强、全局参数驱动的业务配置。

三期能力（集团组织、APS/MES/WMS/SRM 对接、BI、OCR、AI 预警、低代码表单）只复用二期事件和扩展注册能力，不在本期实现其完整业务。

## 2. 设计原则

- 沿用一期统一响应 `{"code": 0, "msg": "操作成功", "data": {}}`、UUID 字符串主键、审计字段、软删除、版本号和 `org_id` 隔离。
- 业务状态只能通过服务层动作改变；API 不直接改余额、成本、审核状态或结算状态。
- 所有库存变化都产生不可变库存流水，并通过来源类型和来源 ID 追踪到生产、委外、销售或采购单据。
- 金额和数量使用 `Decimal`；成本、FIFO、薪资和月结计算禁止使用浮点数。
- 单据动作必须幂等。重复提交、重复扫码、重复完工和重复月结都返回明确业务错误，不产生重复流水。
- 后端执行权限、组织、仓库和项目范围校验；前端隐藏按钮只作为体验优化。
- 新增能力优先复用一期编号规则、审批流、操作日志、字段配置和打印模板，不在业务模块内重复实现。

## 3. 总体架构

继续使用模块化单体，新增以下边界：

```text
backend/app/
  models/production.py, inventory_advanced.py, cost.py, crm.py, quality.py, hr.py, platform.py
  schemas/production.py, inventory_advanced.py, cost.py, crm.py, quality.py, hr.py, platform.py
  services/production_service.py, planning_service.py, inventory_advanced_service.py
           cost_service.py, crm_service.py, quality_service.py, hr_service.py
           openapi_service.py, dashboard_service.py
  api/production.py, inventory_advanced.py, cost.py, crm.py, quality.py, hr.py, platform.py
frontend/src/views/production, inventory-advanced, cost, crm, quality, hr, settings
```

共享服务接口：

- `next_doc_no(db, rule_key, org_id, document_date)`：沿用一期编号规则。
- `post_stock_transaction(...)`：扩展批次、库位、来源和成本层参数，仍是唯一库存变更入口。
- `start_workflow(...)`：用于工单、质检异常、费用和薪资审批等需要审批的单据。
- `write_operation_log(...)`：记录高风险动作、API 调用、月结和恢复操作。
- `emit_event(db, event_type, aggregate_type, aggregate_id, payload)`：写入 `ext_event_outbox`，不在事务内直接调用外部系统。

## 4. 生产域

### 4.1 BOM

新增 `mfg_bom`、`mfg_bom_item`、`mfg_bom_version`。BOM 头包含成品物料、版本、状态、生效日期、损耗率和组织；明细包含组件物料、数量、替代组、工序序号和损耗率。只有已审核且在生效日期范围内的版本可用于 MRP 和工单。

状态：`draft → submitted → approved → disabled`。已被计划或工单引用的版本不能物理删除或修改关键明细。

### 4.2 MPS/MRP

新增 `mfg_mps`、`mfg_mps_item`、`mfg_mrp_run`、`mfg_mrp_result`。MPS 记录计划期间、成品、计划数量和来源；MRP 根据有效 BOM、现有可用库存、已下订单、在制量和安全库存计算净需求，并输出建议生产订单或采购申请。

MRP 计算必须记录输入快照、运行时间和结果版本。重复运行不会覆盖历史运行；用户确认结果后才生成工单或采购申请，生成动作使用来源字段幂等。

### 4.3 工单、领料、报工和完工

新增 `mfg_work_order`、`mfg_work_order_item`、`mfg_material_issue`、`mfg_material_return`、`mfg_report`。工单来源可以是 MRP、MPS 或手工创建，保存 BOM 版本快照、计划数量、实际数量、仓库、项目和状态。

工单状态：`draft → released → in_progress → completed`，异常时可 `released/in_progress → cancelled`。领料从原料仓出库，退料入库，完工入成品仓；每个动作均写库存流水并关联工单，数量不能超过允许数量。报工记录员工/班组、工序、合格数、不合格数、工时和报工时间，合格数与不合格数之和不能超过工单数量。

### 4.4 委外

新增 `mfg_subcontract_order`、`mfg_subcontract_item`、`mfg_subcontract_receipt`。委外订单记录供应商、加工物料、发料数量、加工费和交期；委外发料减少委外/原料库存，收货增加成品库存，并自动生成应付来源和成本分摊来源。

## 5. 库存与成本域

### 5.1 库位、批次和 FIFO

新增 `inv_zone`、`inv_location`、`inv_batch`、`inv_cost_layer`，并扩展 `inv_stock`、`inv_stock_transaction` 增加 `location_id`、`batch_id`、`unit_cost`、`remaining_quantity`。仓库可配置库区和库位；批次在入库、生产完工或采购入库时建立。

入库创建成本层，出库按入库时间升序消耗成本层；出库数量不足时拒绝操作。退货和冲销必须回写来源成本，盘点差异按当前成本生成调整层。任何成本层消耗都保存来源层 ID，保证可审计。

### 5.2 呆滞库存与扫码

新增 `inv_slow_moving_rule`、`inv_slow_moving_snapshot`。按组织、物料、仓库配置无出入库天数和数量阈值，每次查询或定时服务生成可追踪快照，不直接修改库存。

新增扫码 API：登录后通过短期 token 访问扫码任务，支持收货、发料、退料、盘点四类动作。服务端校验 token、仓库、批次、库位和单据状态；同一 `scan_id` 重复提交返回原结果，不重复扣减库存。前端提供移动端响应式页面，不引入原生 App。

### 5.3 多仓隔离

仓库、库位、批次和库存查询均绑定组织及数据范围。用户只能访问授权仓库；生产、销售、采购和扫码动作的仓库必须在当前用户可用仓库集合内。跨仓调拨沿用一期调拨状态机并增加批次、库位和成本层明细。

### 5.4 成本分摊、月结和项目成本

新增 `cost_allocation`、`cost_allocation_item`、`cost_period_close`、`cost_project`、`cost_project_entry`。成本分摊支持按数量、金额或工时比例分配委外费、制造费用和其他费用；分摊结果写项目成本或工单成本来源。

月结按组织和期间执行：先校验未完成单据、负库存、未分摊费用和未审核凭证，再固化 FIFO 与分摊结果，将期间标记为 `closed`。关闭期间禁止新增或修改影响成本的业务，只能通过反结账权限解锁并记录日志。项目成本汇总生产耗用、委外、人工、费用分摊和收入来源。

## 6. CRM、质检和人事域

### 6.1 CRM

新增 `crm_lead`、`crm_contact`、`crm_opportunity`、`crm_follow_up`、`crm_activity`。线索状态为 `new → contacted → qualified → converted/lost`；商机状态包含阶段、预计金额、预计成交日、负责人和客户来源。转化动作幂等创建客户、联系人和商机，跟进记录必须保留负责人、时间、方式和下一步。

CRM 数据按负责人、部门和组织执行行级权限；商机赢单可生成销售报价或订单来源，但不绕过一期销售审批。

### 6.2 质检

新增 `qa_plan`、`qa_plan_item`、`qa_inspection`、`qa_inspection_item`、`qa_nonconformity`。质检方案定义物料、检验类型、指标、标准值、上下限和抽检规则；来料、过程和成品检验分别关联采购入库、生产工单和完工入库。

检验状态为 `draft → submitted → passed/failed → closed`。不合格结果必须生成质量异常，可选择返工、让步接收或报废，并通过来源字段关联库存处理和工单处理。

### 6.3 人事

新增 `hr_employee`、`hr_attendance`、`hr_salary_rule`、`hr_payroll`、`hr_payroll_item`。员工记录部门、岗位、入离职状态和薪资档案；考勤支持签到、签退、请假和异常标记；薪资按固定工资、考勤扣款、津贴和个税规则计算，生成期间薪资单。

薪资计算采用 Decimal 和可审计规则快照。薪资单状态为 `draft → calculated → approved → paid`；审批前可重算，审批后只能通过冲销或反审核流程调整，禁止直接覆盖历史结果。

## 7. 平台增强

### 7.1 OpenAPI 与事件

扩展 `sys_api_client`、`ext_openapi_endpoint`、`ext_event_outbox`。API 客户端密钥只保存 bcrypt/安全哈希，访问 token 绑定客户端、组织、scope、过期时间和请求 ID。每次调用记录接口、状态码、耗时、客户端和资源 ID；禁用客户端立即拒绝请求。

事件在本地事务中写入 outbox，事件状态为 `pending → processing → delivered/failed`，失败记录重试次数和下次时间。二期只实现可靠落库和查询，不连接外部三期系统。

### 7.2 经营看板

扩展看板接口返回生产达成率、工单状态、库存周转/FIFO、呆滞库存、应收应付、CRM 商机、质检合格率、人事出勤和项目成本。所有指标注明统计期间、组织、数据来源和更新时间；无数据返回零值和空列表，不返回虚构预测。

前端 Dashboard 使用 ECharts，支持组织/仓库/期间筛选、主题切换和权限字段隐藏。

### 7.3 全局参数

使用一期 `cfg_global_parameter` 保存 MRP 缓冲天数、呆滞天数、薪资期间、扫码 token 有效期、月结规则和看板默认期间。服务端读取参数并提供默认值；变更记录操作日志，关键参数修改需要权限。

## 8. API 与前端

后端新增路由前缀：

```text
/api/production/boms
/api/production/mps
/api/production/mrp-runs
/api/production/work-orders
/api/production/subcontract-orders
/api/inventory-advanced/locations
/api/inventory-advanced/batches
/api/inventory-advanced/scan
/api/cost/allocations
/api/cost/periods
/api/cost/projects
/api/crm/leads
/api/crm/opportunities
/api/quality/plans
/api/quality/inspections
/api/hr/employees
/api/hr/attendance
/api/hr/payroll
/api/platform/api-clients
/api/platform/events
/api/dashboard/phase2
```

列表接口统一支持组织、状态、期间和分页筛选；写接口返回可继续调用的单据 ID、状态、来源和审计信息。前端新增菜单、列表、详情/编辑、状态动作、导入导出或扫码页面；高风险动作全部使用既有确认组件。

## 9. 数据库与迁移

`database/init.sql` 保持可重复执行，新增二期表、索引、外键、唯一约束、默认编号规则、参数和模块菜单。关键唯一约束包括 BOM 同组织物料版本、扫码 ID、成本期间、API 客户端 key、CRM 线索编号和工资期间。

模型测试使用 SQLite 内存库；真实 MySQL 验收检查 SQL 可执行性、表、索引、外键、唯一约束和种子数据。若真实 MySQL 或 Docker 不可用，必须在报告中区分环境阻塞与代码测试结果。

## 10. 测试验收

后端按 TDD 为每个服务先写失败测试，再实现最小行为。最低覆盖：

- BOM 审核、MRP 净需求、工单领料/退料/报工/完工和委外收货闭环。
- FIFO 成本层消耗、批次/库位追踪、重复扫码、库存不足、呆滞快照、多仓隔离。
- 成本分摊、项目成本、月结前置校验、期间锁定和反结账审计。
- CRM 转化幂等、商机状态、质检抽检/不合格异常、人事薪资重算与审批。
- OpenAPI scope、失效客户端、事件 outbox 重试和看板指标来源。
- 重复操作、非法状态、越权访问、组织/仓库/项目隔离、统一错误响应。

前端执行 Vitest、TypeScript 类型检查和 Vite 构建；至少覆盖二期路由守卫、API 客户端、生产/库存/CRM/质检/人事页面渲染和高危确认。

交付前执行：

```bash
cd backend && pytest -q && python -m compileall -q app
cd frontend && npm test && npm run typecheck && npm run build
```

并记录真实 MySQL 初始化/契约检查结果、不可用的外部环境和未纳入二期的三期能力。

## 11. 实施顺序

1. 共享二期基础：模型注册、参数、扩展字段、事件 outbox、仓库权限和编号规则扩展。
2. 生产域：BOM → MPS/MRP → 工单 → 领料/报工/完工 → 委外。
3. 库存与成本：库位/批次/FIFO → 扫码/呆滞 → 成本分摊/月结/项目成本 → 多仓。
4. CRM、质检、人事三个业务扩展域。
5. OpenAPI、事件查询、经营看板增强和前端菜单收口。
6. 完整后端、前端、SQL 和真实环境验收。
