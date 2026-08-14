-- P0 完整闭环：计划控制塔、BOM/工艺增强、银行自动对账与关账清单
USE erp;
SET NAMES utf8mb4;

ALTER TABLE mfg_bom_item ADD COLUMN IF NOT EXISTS scrap_rate DECIMAL(8,4) NOT NULL DEFAULT 0;
ALTER TABLE mfg_bom_item ADD COLUMN IF NOT EXISTS issue_operation_id CHAR(36) NULL;
ALTER TABLE mfg_bom_item ADD COLUMN IF NOT EXISTS is_phantom TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE mfg_routing_operation ADD COLUMN IF NOT EXISTS quality_plan_id CHAR(36) NULL;
ALTER TABLE mfg_routing_operation ADD COLUMN IF NOT EXISTS equipment_requirement VARCHAR(255) NULL;
ALTER TABLE mfg_work_order_exception ADD COLUMN IF NOT EXISTS severity VARCHAR(16) NOT NULL DEFAULT 'medium';
ALTER TABLE mfg_work_order_exception ADD COLUMN IF NOT EXISTS owner_id CHAR(36) NULL;
ALTER TABLE mfg_work_order_exception ADD COLUMN IF NOT EXISTS due_at DATETIME NULL;
ALTER TABLE mfg_work_order_exception ADD COLUMN IF NOT EXISTS source_event CHAR(36) NULL;

CREATE TABLE IF NOT EXISTS mfg_demand_line (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, material_id CHAR(36) NOT NULL, warehouse_id CHAR(36) NULL,
  demand_date DATE NOT NULL, quantity DECIMAL(18,6) NOT NULL, source_type VARCHAR(64) NOT NULL, source_id CHAR(36) NOT NULL,
  source_line_id CHAR(36) NULL, status VARCHAR(32) NOT NULL DEFAULT 'open', created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY idx_mfg_demand_scope (org_id, demand_date, material_id), KEY idx_mfg_demand_source (org_id, source_type, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_plan_run (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, run_no VARCHAR(64) NOT NULL, plan_from DATE NOT NULL, plan_to DATE NOT NULL,
  warehouse_id CHAR(36) NULL, status VARCHAR(32) NOT NULL DEFAULT 'completed', algorithm_version VARCHAR(32) NOT NULL DEFAULT 'rules-v1',
  input_snapshot JSON NOT NULL, output_snapshot JSON NOT NULL, created_by CHAR(36) NULL, confirmed_at DATETIME NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_mfg_plan_run_no (org_id, run_no), KEY idx_mfg_plan_run_scope (org_id, plan_from, plan_to)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_planned_order (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, run_id CHAR(36) NOT NULL, order_type VARCHAR(32) NOT NULL, material_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NULL, due_date DATE NOT NULL, quantity DECIMAL(18,6) NOT NULL, status VARCHAR(32) NOT NULL DEFAULT 'pending',
  source_snapshot JSON NOT NULL, formal_document_type VARCHAR(64) NULL, formal_document_id CHAR(36) NULL, confirmed_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_mfg_planned_order_run FOREIGN KEY (run_id) REFERENCES mfg_plan_run(id), KEY idx_mfg_planned_order_status (org_id, status, due_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_plan_exception (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, run_id CHAR(36) NOT NULL, material_id CHAR(36) NULL, exception_type VARCHAR(64) NOT NULL,
  severity VARCHAR(16) NOT NULL DEFAULT 'warning', due_date DATE NULL, impact_quantity DECIMAL(18,6) NOT NULL DEFAULT 0, details JSON NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'open', owner_id CHAR(36) NULL, resolution VARCHAR(500) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_mfg_plan_exception_run FOREIGN KEY (run_id) REFERENCES mfg_plan_run(id), KEY idx_mfg_plan_exception_scope (org_id, status, severity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_execution_event (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, work_order_id CHAR(36) NOT NULL, operation_id CHAR(36) NULL, execution_key VARCHAR(128) NOT NULL,
  good_quantity DECIMAL(18,6) NOT NULL DEFAULT 0, scrap_quantity DECIMAL(18,6) NOT NULL DEFAULT 0, hours DECIMAL(18,6) NOT NULL DEFAULT 0,
  report_id CHAR(36) NULL, created_by CHAR(36) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_mfg_execution_event_key (org_id, execution_key), KEY idx_mfg_execution_event_order (org_id, work_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_bank_statement (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, statement_no VARCHAR(64) NOT NULL, bank_account_id CHAR(36) NOT NULL,
  statement_date DATE NOT NULL, opening_balance DECIMAL(18,2) NOT NULL DEFAULT 0, closing_balance DECIMAL(18,2) NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'draft', source_file VARCHAR(255) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_fin_bank_statement_no (org_id, statement_no), KEY idx_fin_bank_statement_account (org_id, bank_account_id, statement_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_bank_statement_line (
  id CHAR(36) PRIMARY KEY, statement_id CHAR(36) NOT NULL, line_no INT NOT NULL, transaction_date DATE NOT NULL, amount DECIMAL(18,2) NOT NULL,
  direction VARCHAR(8) NOT NULL, counterparty VARCHAR(128) NULL, reference_no VARCHAR(128) NULL, matched_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'unmatched', note VARCHAR(255) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_fin_bank_statement_line_statement FOREIGN KEY (statement_id) REFERENCES fin_bank_statement(id), UNIQUE KEY uk_fin_bank_statement_line_no (statement_id, line_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_reconciliation_match (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, statement_line_id CHAR(36) NOT NULL, source_type VARCHAR(64) NOT NULL, source_id CHAR(36) NOT NULL,
  matched_amount DECIMAL(18,2) NOT NULL, match_type VARCHAR(32) NOT NULL DEFAULT 'rule', override_reason VARCHAR(255) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_fin_reconciliation_match_line FOREIGN KEY (statement_line_id) REFERENCES fin_bank_statement_line(id), KEY idx_fin_reconciliation_match_source (org_id, source_type, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_period_close_checklist (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, period CHAR(7) NOT NULL, item_code VARCHAR(64) NOT NULL, item_name VARCHAR(128) NOT NULL,
  owner_id CHAR(36) NULL, blocking TINYINT(1) NOT NULL DEFAULT 1, status VARCHAR(32) NOT NULL DEFAULT 'pending', evidence VARCHAR(500) NULL,
  completed_at DATETIME NULL, completed_by CHAR(36) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_fin_period_checklist_item (org_id, period, item_code), KEY idx_fin_period_checklist_scope (org_id, period, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO sys_schema_migration (version, description)
VALUES ('014_p0_completion', 'P0 计划控制塔、BOM/工艺增强、银行对账和关账清单')
ON DUPLICATE KEY UPDATE description = VALUES(description);
