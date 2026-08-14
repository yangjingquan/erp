-- P0：WMS 作业、生产执行、财务计划控制与可靠事件处理
USE erp;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS inv_pick_wave (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, wave_no VARCHAR(64) NOT NULL,
  warehouse_id CHAR(36) NOT NULL, status VARCHAR(32) NOT NULL DEFAULT 'draft', priority INT NOT NULL DEFAULT 50,
  assigned_to CHAR(36) NULL, released_at DATETIME NULL, completed_at DATETIME NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_inv_pick_wave_no (org_id, wave_no), KEY idx_inv_pick_wave_scope (org_id, warehouse_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_warehouse_task (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, task_no VARCHAR(64) NOT NULL, task_type VARCHAR(32) NOT NULL,
  source_type VARCHAR(64) NULL, source_id CHAR(36) NULL, warehouse_id CHAR(36) NOT NULL, location_id CHAR(36) NULL,
  material_id CHAR(36) NULL, batch_id CHAR(36) NULL, planned_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  completed_quantity DECIMAL(18,6) NOT NULL DEFAULT 0, assigned_to CHAR(36) NULL, wave_id CHAR(36) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'ready', priority INT NOT NULL DEFAULT 50, exception_reason VARCHAR(500) NULL,
  completed_at DATETIME NULL, completed_by CHAR(36) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_inv_warehouse_task_no (org_id, task_no), KEY idx_inv_warehouse_task_scope (org_id, warehouse_id, status),
  KEY idx_inv_warehouse_task_wave (wave_id), CONSTRAINT fk_inv_task_wave FOREIGN KEY (wave_id) REFERENCES inv_pick_wave(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_work_order_schedule (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, work_order_id CHAR(36) NOT NULL, operation_id CHAR(36) NULL,
  work_center_id CHAR(36) NOT NULL, schedule_date DATE NOT NULL, scheduled_hours DECIMAL(18,6) NOT NULL,
  actual_hours DECIMAL(18,6) NOT NULL DEFAULT 0, status VARCHAR(32) NOT NULL DEFAULT 'planned', created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_mfg_work_order_schedule_operation (org_id, work_order_id, operation_id), KEY idx_mfg_schedule_capacity (org_id, work_center_id, schedule_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_alternate_material (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, work_order_id CHAR(36) NOT NULL, material_id CHAR(36) NOT NULL,
  alternate_material_id CHAR(36) NOT NULL, conversion_rate DECIMAL(18,6) NOT NULL DEFAULT 1, status VARCHAR(32) NOT NULL DEFAULT 'approved',
  reason VARCHAR(255) NULL, approved_by CHAR(36) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_mfg_alternate_material (org_id, work_order_id, material_id, alternate_material_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_work_order_exception (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, work_order_id CHAR(36) NOT NULL, exception_type VARCHAR(64) NOT NULL,
  description VARCHAR(500) NOT NULL, status VARCHAR(32) NOT NULL DEFAULT 'open', occurred_at DATETIME NOT NULL,
  reported_by CHAR(36) NULL, resolved_at DATETIME NULL, resolved_by CHAR(36) NULL, resolution VARCHAR(500) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY idx_mfg_exception_order_status (org_id, work_order_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_budget (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, budget_period CHAR(7) NOT NULL, account_code VARCHAR(64) NOT NULL,
  department_id CHAR(36) NULL, budget_amount DECIMAL(18,2) NOT NULL, actual_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'draft', note VARCHAR(255) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_fin_budget_scope (org_id, budget_period, account_code, department_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_cash_forecast (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, forecast_date DATE NOT NULL, inflow_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  outflow_amount DECIMAL(18,2) NOT NULL DEFAULT 0, net_amount DECIMAL(18,2) NOT NULL DEFAULT 0, source VARCHAR(64) NOT NULL DEFAULT 'manual',
  status VARCHAR(32) NOT NULL DEFAULT 'draft', note VARCHAR(255) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_fin_cash_forecast_day (org_id, forecast_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_reconciliation_statement (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, statement_no VARCHAR(64) NOT NULL, statement_type VARCHAR(8) NOT NULL,
  party_id CHAR(36) NOT NULL, period CHAR(7) NOT NULL, statement_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  reconciled_amount DECIMAL(18,2) NOT NULL DEFAULT 0, status VARCHAR(32) NOT NULL DEFAULT 'draft', note VARCHAR(255) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), UNIQUE KEY uk_fin_reconciliation_statement_no (org_id, statement_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO sys_schema_migration (version, description)
VALUES ('012_p0_execution_controls', 'P0 WMS、生产执行、财务控制与事件可靠性')
ON DUPLICATE KEY UPDATE description = VALUES(description);
