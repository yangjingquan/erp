# ERP 一期核心交付设计

日期：2026-08-02  
范围：一期核心 ERP；二期、三期按顺序开发  
状态：设计已确认，待文字审阅后进入实施计划

## 1. 目标与范围

本项目从空目录开始，构建一套可私有化部署的企业级 ERP。采用模块化单体架构，先完成一期可启动、可登录、可配置、可演示、可扩展的核心系统，再按顺序开发二期业务和三期技术基座。

一期包含：

- 登录、JWT、bcrypt、菜单/按钮/行级 RBAC、个人中心。
- 部门、角色、用户、菜单、物料、客户、供应商、仓库、计量单位、税率等主数据。
- 销售报价、销售订单、销售出库、销售退货、应收及收款核销。
- 采购申请、采购订单、采购入库、采购退货、应付及付款核销。
- 库存出入库、调拨、盘点、库存台账、安全库存预警。
- 应收应付、收付款、费用报销、简易固定资产、业务单据自动生成财务凭证。
- 审批流、字段配置、编号规则、打印模板、Excel 导入导出、全局检索。
- 操作日志、登录日志、Swagger、SQL 备份恢复、主题切换、Dashboard。
- 生产、CRM、质检、人事、OpenAPI、移动扫码、BI、OCR、AI 预警和集团组织的扩展基座，不在一期虚构完整业务实现。

## 2. 技术栈与端口

前端：Vue 3 + TypeScript、Vite、Element Plus、Vue Router 4、Pinia、Axios、ECharts。前端开发端口固定为 5176。

后端：Python 3.11+、FastAPI、SQLAlchemy ORM、Pydantic Settings、PyJWT、bcrypt、PyMySQL、pytest + FastAPI TestClient。后端 API 端口固定为 8085，Swagger 地址为 http://127.0.0.1:8085/docs。

数据库固定配置：

~~~text
host: 127.0.0.1
port: 3306
database: erp
user: root
password: changeme_root
~~~

## 3. 总体架构

~~~text
Vue3 + Vite
  ├─ Layout / Router / Pinia / Axios
  ├─ 权限菜单与按钮指令
  ├─ 主数据、供应链、库存、财务、配置页面
  └─ ECharts 经营看板

FastAPI
  ├─ API 路由层
  ├─ Service 业务服务层
  ├─ Repository / SQLAlchemy 数据访问层
  ├─ 权限、日志、异常、中间件
  └─ 字段、审批、编号规则引擎

MySQL 8.0
  ├─ 用户权限与组织
  ├─ 主数据
  ├─ 销售、采购、库存
  ├─ 应收应付与会计凭证
  ├─ 审批、日志、配置
  └─ 二三期扩展基座
~~~

采用模块化单体而不是微服务，以降低本地部署、调试、事务一致性和一期交付成本。每个业务域在代码层拥有独立的路由、schema、service、repository 和模型边界，未来可按实际负载拆分服务。

## 4. 核心业务数据流

~~~text
销售订单 → 销售出库 → 库存减少 → 应收形成 → 收款核销 → 自动凭证
采购订单 → 采购入库 → 库存增加 → 应付形成 → 付款核销 → 自动凭证
库存调拨 → 调出/调入流水 → 库存台账更新
库存盘点 → 盘盈/盘亏单 → 库存调整 → 自动凭证
费用报销 → 审批 → 付款 → 费用凭证
~~~

库存余额禁止直接修改，所有余额变动必须由合法业务单据生成库存流水，再更新 inv_stock。财务凭证由业务单据服务自动生成，保留凭证审核、修改和期间控制接口。

所有业务单据统一包含 id UUID 全局业务主键、doc_no 配置化单据编号、status 单据状态、org_id / department_id / owner_id、创建修改审计字段、version 乐观锁版本号和 source_type / source_id 上下游来源追踪字段。

## 5. 数据库模型

核心表分组：

| 分组 | 主要表 |
|---|---|
| 组织权限 | sys_org、sys_department、sys_user、sys_role、sys_menu、sys_permission、关联表 |
| 主数据 | md_material、md_customer、md_supplier、md_warehouse、md_unit、md_tax_rate |
| 销售 | sales_quote、sales_quote_item、sales_order、sales_order_item、sales_delivery、sales_return、sales_receivable |
| 采购 | purchase_request、purchase_order、purchase_order_item、purchase_receipt、purchase_return、purchase_payable |
| 库存 | inv_stock、inv_stock_transaction、inv_transfer、inv_count、inv_warning |
| 财务 | fin_receipt、fin_payment、fin_expense、fin_asset、fin_voucher、fin_voucher_entry |
| 工作流 | wf_definition、wf_node、wf_instance、wf_task、wf_action_log |
| 配置 | cfg_field_definition、cfg_number_rule、cfg_print_template、cfg_global_parameter |
| 运维 | sys_operation_log、sys_login_log、sys_backup_record、sys_api_client |
| 二三期基座 | ext_module_registry、ext_openapi_endpoint、ext_event_outbox、ext_ai_alert_rule |

数据一致性规则：

- 业务表使用 UUID 字符串主键，避免模块间 ID 冲突。
- 单据号由编号规则服务生成，支持前缀、日期、流水号长度和重置周期。
- 物料编码、客户编码、供应商编码、仓库编码等建立唯一约束。
- 业务数据软删除；已被引用的数据禁止物理删除。
- 明细表使用外键、数量精度和金额精度约束。
- 库存流水记录出入库、调拨、盘盈和盘亏。
- 上下游单据使用 source_type/source_id 与明细映射追踪。
- 行级权限由 data_scope_type 和 data_scope_value 实现：本人、本部门、本部门及下级、指定组织、全部。
- 成本毛利字段由后端字段权限控制，前端字段隐藏只作为体验优化。
- 可配置扩展字段使用 JSON，核心业务字段保持结构化列以支持查询、统计和索引。

database/init.sql 自动创建 erp 数据库、核心表、索引、外键、默认配置、菜单、超级管理员角色和超级管理员账号。默认账号为 admin，初始密码为 Admin@123；密码仅写入 bcrypt 哈希，README 要求首次登录后修改密码。

后端启动前执行数据库健康检查：连接 127.0.0.1:3306/erp，检查核心表和 schema 版本；数据库不存在或未初始化时输出 ERP 数据库未初始化，请先执行 database/init.sql，校验通过后再启动 API。

## 6. 后端 API 与鉴权

后端目录按业务域拆分：

~~~text
backend/app/
├── main.py
├── core/
├── middleware/
├── models/
├── schemas/
├── repositories/
├── services/
├── api/
│   ├── auth.py
│   ├── system.py
│   ├── master_data.py
│   ├── sales.py
│   ├── purchase.py
│   ├── inventory.py
│   ├── finance.py
│   ├── workflow.py
│   └── config.py
└── sql/init.sql
~~~

统一响应：

~~~json
{"code": 0, "msg": "操作成功", "data": {}}
~~~

核心接口包括登录、当前用户、修改密码、主数据 CRUD、销售/采购单据及状态动作、库存流水/调拨/盘点、收付款/费用、审批定义和任务、全局检索、Dashboard、备份恢复。

鉴权流程：登录校验 bcrypt 密码并返回短期 access token 与 refresh token；Axios 自动携带 Bearer token；FastAPI 解析用户、角色、菜单和数据权限；路由守卫拦截未登录或无菜单权限页面；权限指令控制按钮显示；后端再次校验写操作和敏感字段；Token 失效时清理 Pinia 状态并跳转登录页。

统一开启 CORS，仅允许 http://127.0.0.1:5176 和 http://localhost:5176。

## 7. 配置化机制

- cfg_field_definition：字段显示、必填、只读、权限、排序。
- cfg_number_rule：单据前缀、日期格式、流水号长度和重置周期。
- wf_definition/wf_node：审批节点、审批人来源、条件表达式、回退规则。
- cfg_print_template：标题、字段、明细、合计、页脚。

业务服务统一调用配置服务，不将审批节点、编号格式和表单字段硬编码在页面或单据服务中。

## 8. 前端布局与页面

~~~text
frontend/src/
├── api/
├── assets/
├── components/
│   ├── AppTable.vue
│   ├── AppForm.vue
│   ├── PermissionButton.vue
│   ├── ConfirmDialog.vue
│   └── ThemeToggle.vue
├── layouts/AdminLayout.vue
├── router/
├── stores/
├── views/
│   ├── Login.vue
│   ├── Dashboard.vue
│   ├── system/
│   ├── master-data/
│   ├── sales/
│   ├── purchase/
│   ├── inventory/
│   ├── finance/
│   ├── workflow/
│   └── settings/
└── styles/
~~~

登录页独立布局；登录后使用左侧可收起导航、右侧主内容区和顶部工具栏。Element Plus 通过 CSS 变量适配浅色/暗黑主题，ECharts 通过主题适配器自动切换配色。列表统一支持筛选、分页、批量操作、导入、导出和打印。删除、作废、清空和恢复统一使用二次确认组件。

## 9. 阶段顺序

一期按以下顺序实现：

1. 工程脚手架、数据库连接、初始化 SQL、统一响应和异常。
2. 登录、JWT、bcrypt、RBAC、菜单、按钮和行级权限。
3. 主数据与 Excel 导入导出。
4. 销售、采购、库存单据及库存台账闭环。
5. 应收应付、收付款、费用报销、固定资产和自动凭证。
6. 审批流、编号规则、字段配置、打印模板。
7. Dashboard、全局检索、操作日志、备份恢复、主题和 README。
8. 一期端到端验证和交付检查。

二期顺序：生产 BOM/MPS/MRP、生产工单与报工、委外、库位/FIFO/呆滞库存、移动 H5 扫码、成本分摊/月结/项目成本、CRM/质检/人事、多仓隔离、OpenAPI、经营看板和全局参数。

三期只搭建集团组织、APS/MES/WMS/SRM 对接层、BI、OCR、AI 预警和低代码表单引擎基座。

## 10. 测试、验收与交付

后端使用 pytest + FastAPI TestClient 覆盖认证、权限、单据状态、库存余额、财务凭证、重复数据和异常响应；前端执行 TypeScript 类型检查、Vite 构建、Pinia store 和路由守卫测试；数据库执行初始化脚本并校验表、索引、外键、唯一约束和超级管理员。

集成测试覆盖销售“订单 → 出库 → 库存减少 → 应收 → 收款核销 → 凭证”和采购对应链路。手工验收覆盖登录、主题、侧栏、权限、高危确认、Excel、打印及备份恢复。完成声明前执行完整验证命令，并记录本地 MySQL 未运行等环境限制。

最终交付：

~~~text
backend/
frontend/
database/init.sql
README.md
docs/
requirements.txt
package.json
.env.example
~~~

README 包含环境要求、数据库配置、SQL 初始化、前后端启动顺序、端口 8085/5176、默认管理员、首次登录、权限配置、备份恢复和故障排查。

