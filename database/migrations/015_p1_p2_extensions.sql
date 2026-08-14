-- P1/P2 extension domains: PLM, SRM, project cost, EAM/service, CRM 360,
-- tax/invoice, intercompany, low-code, metrics and explainable AI alerts.
-- The application runtime also creates these non-destructive tables for a
-- rolling deployment where this migration has not yet been applied.
USE erp;
SET NAMES utf8mb4;

-- Keep this migration idempotent.  SQLAlchemy models are the canonical column
-- contract; the runtime guard creates the same tables when needed.
INSERT INTO sys_schema_migration (version, description)
VALUES ('015_p1_p2_extensions', 'P1/P2 PLM、供应商、项目、EAM、服务、合规与平台扩展')
ON DUPLICATE KEY UPDATE description = VALUES(description);
