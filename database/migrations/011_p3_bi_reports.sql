-- P3: BI 报表定义、运行记录和 CSV 导出基础能力
USE erp;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS biz_report_definition (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  report_key VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  description VARCHAR(500) NOT NULL DEFAULT '',
  parameters_json JSON NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  owner_id CHAR(36) NOT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_biz_report_definition_org_key (org_id, report_key),
  KEY idx_biz_report_definition_org_status (org_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS biz_report_run (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  report_definition_id VARCHAR(64) NOT NULL,
  report_key VARCHAR(64) NOT NULL,
  requested_by CHAR(36) NOT NULL,
  parameters_json JSON NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'completed',
  result_json JSON NOT NULL,
  error_message VARCHAR(500) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY idx_biz_report_run_org_created (org_id, created_at),
  KEY idx_biz_report_run_report (org_id, report_key, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO sys_menu (id, parent_id, code, name, path, component, menu_type, sort_order)
SELECT '10000000-0000-0000-0000-000000000022', id, 'page:analytics:reports:view', 'BI 报表中心', '/analytics/reports', 'ReportCenter', 'menu', 6
FROM sys_menu WHERE code = 'config:view'
ON DUPLICATE KEY UPDATE name = VALUES(name), path = VALUES(path), component = VALUES(component), sort_order = VALUES(sort_order);

INSERT INTO sys_schema_migration (version, description)
VALUES ('011_p3_bi_reports', 'P3 BI 报表定义、运行记录与导出基础能力')
ON DUPLICATE KEY UPDATE description = VALUES(description);
