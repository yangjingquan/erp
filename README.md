# ERP 管理系统

基于 Vue 3 + Vite + Element Plus + Vue Router 4 + Pinia + ECharts，以及 Python FastAPI + SQLAlchemy ORM + MySQL 8.0 的私有化企业 ERP 一期核心工程。

当前实现顺序为：一期核心 → 二期生产/CRM/质检/人事 → 三期高级功能底座。当前工作区已完成一期可运行主链路和二、三期扩展表基座。

## 1. 环境要求

- macOS/Linux/Windows 均可部署。
- Python 3.11 或更高版本。
- Node.js 20 或更高版本，npm 10 或更高版本。
- Docker Desktop，以及本地 MySQL 8.0 容器 `shop-mysql`，监听 127.0.0.1:3306。
- 不要求宿主机安装 mysql/mysqldump 客户端，初始化、备份和恢复均通过容器执行。

## 2. 固定配置

~~~text
数据库地址：127.0.0.1:3306
数据库名称：erp
数据库账号：root
数据库密码：changeme_root
后端端口：8085
前端端口：5176
~~~

生产环境请修改 backend/.env.example 中的 JWT_SECRET_KEY，并复制为 backend/.env。数据库账号密码也可以通过 DATABASE_URL 修改，但默认配置与 database/init.sql 保持一致。

## 3. 初始化数据库

确认 Docker 容器已启动后执行：

~~~bash
docker start shop-mysql 2>/dev/null || true
docker exec -i shop-mysql mysql --user=root --password=changeme_root --default-character-set=utf8mb4 < database/init.sql
~~~

脚本会自动创建 erp 数据库、一期业务表、配置表、日志表和二三期扩展基座，并写入默认权限与编号规则。脚本可重复执行。

已有数据库不需要重跑完整初始化脚本，可按顺序执行版本化迁移：

~~~bash
docker exec -i shop-mysql mysql --user=root --password=changeme_root --default-character-set=utf8mb4 < database/migrations/001_platform_workbench.sql
docker exec -i shop-mysql mysql --user=root --password=changeme_root --default-character-set=utf8mb4 < database/migrations/002_document_department_scope.sql
docker exec -i shop-mysql mysql --user=root --password=changeme_root --default-character-set=utf8mb4 < database/migrations/003_event_outbox_compatibility.sql
~~~

前三份迁移可直接重复执行。系统业务时区默认为 `Asia/Shanghai`，MySQL 会话固定为 `+08:00`。仅当已确认旧库所有 `DATETIME` 都是 UTC 并完成备份后，才执行 `database/migrations/004_local_timezone.sql`；它会且只会一次性将历史时间平移 8 小时，不能用于混合存储了 UTC 和本地时间的数据库。业务附件存储在 `backend/var/attachments`，数据库保存受组织权限保护的元数据与文件键。

默认超级管理员：

~~~text
用户名：admin
密码：Admin@123
~~~

密码只以 bcrypt 哈希存储。首次登录后请立即修改密码。

如果数据库未初始化，后端日志会输出：

~~~text
ERP 数据库未初始化，请先执行 database/init.sql
~~~

## 4. 启动后端

~~~bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8085 --reload
~~~

接口文档：http://127.0.0.1:8085/docs

健康检查：http://127.0.0.1:8085/api/health

启动时会检查 MySQL 连接和核心 schema。数据库暂时不可用时 API 进程仍能启动，但会在日志中给出明确提示；业务请求需要数据库可用。

## 5. 启动前端

~~~bash
cd frontend
npm install
cp .env.example .env
npm run dev
~~~

打开 http://127.0.0.1:5176。

前端通过 Axios 自动向 API 请求添加 JWT；Token 失效后清理本地登录状态并返回登录页。开发代理将 /api 转发到 8085。

## 6. 一期功能

- 登录、JWT、bcrypt、菜单/按钮/行级数据权限、个人中心改密。
- 部门、角色、用户、菜单、物料、客户、供应商、仓库、单位、税率。
- Excel 主数据导入导出和重复编码/名称校验。
- 销售报价基础表、销售订单、出库、退货、应收和收款核销。
- 采购申请基础表、采购订单、入库、退货、应付和付款核销。
- 库存流水、调拨、盘点、安全库存预警；库存余额不允许直接修改。
- 费用报销、简易固定资产、业务单据自动生成财务凭证。
- 配置化编号规则、字段定义、审批流、打印模板和全局参数。
- 统一单据工作台：后端分页筛选、状态统计、动态状态动作、上下游关联、流程时间线、评论和真实附件。
- 销售订单可在同一工作台追踪出库、库存事务、应收、收款核销和会计凭证；顶部通知中心支持未读与业务跳转。
- 前端写请求自动携带 `Idempotency-Key`，后端保存 24 小时幂等响应；错误响应提供 `message`、`field_errors` 和 `trace_id`。
- Dashboard、全局关键词检索、操作日志、登录日志、备份恢复。
- 浅色/暗黑主题、侧栏收起、Element Plus 自适应界面和 ECharts 看板。

销售报价、采购申请、销售/采购退货已提供独立列表、创建和审批操作；权限设置页支持部门、角色、用户、菜单的列表、新增和启停用，并支持部门和角色修改。

销售完整业务链路：

~~~text
销售订单 → 审核 → 销售出库 → 库存减少 → 应收形成 → 收款核销 → 自动凭证
~~~

采购完整业务链路：

~~~text
采购订单 → 审核 → 采购入库 → 库存增加 → 应付形成 → 付款核销 → 自动凭证
~~~

## 7. 备份与恢复

备份使用 `shop-mysql` 容器，并输出到宿主机文件：

~~~bash
mkdir -p backend/var/backups
docker exec shop-mysql mysqldump --user=root --password=changeme_root --single-transaction --routines --triggers --databases erp > backend/var/backups/erp-$(date +%Y%m%d%H%M%S).sql
~~~

恢复必须经过二次确认，并使用有效 .sql 文件：

~~~bash
docker exec -i shop-mysql mysql --user=root --password=changeme_root erp < backend/var/backups/erp-YYYYMMDDHHMMSS.sql
~~~

管理端备份/恢复入口会调用后端安全校验。恢复会覆盖当前数据库，执行前应确认备份文件、目标环境和当前业务是否已停止。

## 8. 测试与验证

后端：

~~~bash
cd backend
source .venv/bin/activate
pytest -q
python -m compileall -q app
~~~

前端：

~~~bash
cd frontend
npm test
npm run typecheck
npm run build
~~~

测试覆盖认证、部门/个人数据范围、主数据重复校验和 Excel、编号规则、审批节点、销售/采购状态流及报价/采购申请、库存台账、应收应付、自动凭证、单据全链路追溯、附件/评论/通知、写接口幂等、Dashboard、搜索、备份恢复和一期端到端链路。

## 9. 目录结构

~~~text
backend/
  app/
    api/             FastAPI 路由
    core/            配置、数据库、安全、统一响应
    models/          SQLAlchemy ORM 模型
    schemas/         Pydantic 请求模型
    services/        业务服务与状态流
    repositories/    通用数据访问
    middleware/      请求上下文和异常处理
  tests/
  requirements.txt
frontend/
  src/
    api/             Axios API
    components/      通用组件
    layouts/         管理布局
    router/          Vue Router 守卫
    stores/          Pinia 状态
    views/           业务页面
database/init.sql   MySQL 初始化脚本
docs/               设计和实施计划
~~~

## 10. 二期与三期

二期按顺序开发生产 BOM/MPS/MRP、生产工单、报工、委外、库位/FIFO、呆滞库存、移动 H5 扫码、成本分摊/月结/项目成本、CRM、质检、人事、多仓隔离、OpenAPI 和经营看板增强。

三期只搭建集团多组织、APS/MES/WMS/SRM 对接层、BI 框架、OCR 发票识别、AI 预警和低代码表单引擎底座。

## 11. 当前验证状态

当前环境已使用 Docker `shop-mysql`（MySQL 8.0.46）完成真实数据库初始化、ORM 字段契约检查、列表接口回归和 SQL 备份验证。自动化业务测试仍使用 SQLite 内存数据库，以保持测试快速、可重复；启动后端时会额外检查真实 MySQL 连通性和核心 schema。
