-- Versioned migration: general ledger foundation and production actual cost.
-- Safe to replay on MySQL 8.0.
USE erp;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS sys_schema_migration (
  version VARCHAR(64) PRIMARY KEY,
  description VARCHAR(255) NOT NULL,
  applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_account (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  account_type VARCHAR(32) NOT NULL,
  balance_direction VARCHAR(8) NOT NULL,
  parent_id CHAR(36) NULL,
  allow_posting TINYINT(1) NOT NULL DEFAULT 1,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_fin_account_org_code (org_id, code),
  KEY idx_fin_account_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_accounting_dimension (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  dimension_type VARCHAR(32) NOT NULL,
  required TINYINT(1) NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_fin_dimension_org_code (org_id, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_fiscal_period (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  period VARCHAR(7) NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'open',
  closed_at DATETIME(6) NULL,
  closed_by CHAR(36) NULL,
  reopened_at DATETIME(6) NULL,
  reopened_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_fin_fiscal_period_org (org_id, period)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_bank_account (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  name VARCHAR(128) NOT NULL,
  bank_name VARCHAR(128) NOT NULL,
  account_no VARCHAR(64) NOT NULL,
  currency VARCHAR(8) NOT NULL DEFAULT 'CNY',
  ledger_account_id CHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_fin_bank_account_org_no (org_id, account_no),
  KEY idx_fin_bank_account_ledger (ledger_account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_asset_depreciation (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  asset_id CHAR(36) NOT NULL,
  period VARCHAR(7) NOT NULL,
  amount DECIMAL(18,2) NOT NULL,
  voucher_id CHAR(36) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'posted',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_fin_asset_depreciation_period (asset_id, period),
  KEY idx_fin_asset_depreciation_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_work_order_cost (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  work_order_id CHAR(36) NOT NULL,
  material_cost DECIMAL(18,2) NOT NULL DEFAULT 0,
  labor_cost DECIMAL(18,2) NOT NULL DEFAULT 0,
  overhead_cost DECIMAL(18,2) NOT NULL DEFAULT 0,
  subcontract_cost DECIMAL(18,2) NOT NULL DEFAULT 0,
  scrap_cost DECIMAL(18,2) NOT NULL DEFAULT 0,
  total_cost DECIMAL(18,2) NOT NULL DEFAULT 0,
  actual_unit_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
  standard_cost DECIMAL(18,2) NOT NULL DEFAULT 0,
  variance_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  voucher_id CHAR(36) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'calculated',
  cost_detail_json JSON NOT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_work_order_cost_order (org_id, work_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP PROCEDURE IF EXISTS phase3_add_ledger_column;
DELIMITER //
CREATE PROCEDURE phase3_add_ledger_column(IN table_name_input VARCHAR(64), IN column_name_input VARCHAR(64), IN column_definition TEXT)
BEGIN
  DECLARE column_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = table_name_input AND column_name = column_name_input;
  IF column_exists = 0 THEN
    SET @phase3_ledger_sql = CONCAT('ALTER TABLE `', table_name_input, '` ADD COLUMN `', column_name_input, '` ', column_definition);
    PREPARE phase3_ledger_statement FROM @phase3_ledger_sql;
    EXECUTE phase3_ledger_statement;
    DEALLOCATE PREPARE phase3_ledger_statement;
  END IF;
END//
DELIMITER ;

CALL phase3_add_ledger_column('fin_asset', 'useful_life_months', 'INT NOT NULL DEFAULT 60');
CALL phase3_add_ledger_column('fin_asset', 'residual_rate', 'DECIMAL(8,4) NOT NULL DEFAULT 0');
CALL phase3_add_ledger_column('fin_asset', 'depreciation_method', 'VARCHAR(32) NOT NULL DEFAULT ''straight_line''');
CALL phase3_add_ledger_column('fin_asset', 'depreciation_account_code', 'VARCHAR(64) NOT NULL DEFAULT ''1602''');
CALL phase3_add_ledger_column('fin_asset', 'expense_account_code', 'VARCHAR(64) NOT NULL DEFAULT ''6602''');
CALL phase3_add_ledger_column('fin_asset', 'last_depreciation_period', 'VARCHAR(7) NULL');
CALL phase3_add_ledger_column('fin_voucher', 'posted_at', 'DATETIME(6) NULL');
CALL phase3_add_ledger_column('fin_voucher', 'posted_by', 'CHAR(36) NULL');
CALL phase3_add_ledger_column('fin_voucher', 'reversed_from_id', 'CHAR(36) NULL');
CALL phase3_add_ledger_column('fin_voucher', 'reversal_voucher_id', 'CHAR(36) NULL');
CALL phase3_add_ledger_column('fin_voucher_entry', 'account_id', 'CHAR(36) NULL');
CALL phase3_add_ledger_column('fin_voucher_entry', 'dimensions_json', 'JSON NULL');
CALL phase3_add_ledger_column('mfg_work_center', 'labor_rate', 'DECIMAL(18,2) NOT NULL DEFAULT 0');
CALL phase3_add_ledger_column('mfg_work_center', 'overhead_rate', 'DECIMAL(18,2) NOT NULL DEFAULT 0');
DROP PROCEDURE IF EXISTS phase3_add_ledger_column;

UPDATE fin_voucher_entry SET dimensions_json = JSON_OBJECT() WHERE dimensions_json IS NULL;
ALTER TABLE fin_voucher_entry MODIFY COLUMN dimensions_json JSON NOT NULL;

DROP PROCEDURE IF EXISTS phase3_fix_fin_voucher_source_index;
DELIMITER //
CREATE PROCEDURE phase3_fix_fin_voucher_source_index()
BEGIN
  DECLARE indexed_columns VARCHAR(255) DEFAULT NULL;
  SELECT GROUP_CONCAT(column_name ORDER BY seq_in_index) INTO indexed_columns
  FROM information_schema.statistics
  WHERE table_schema = DATABASE() AND table_name = 'fin_voucher' AND index_name = 'uk_fin_voucher_source';
  IF indexed_columns IS NOT NULL AND indexed_columns <> 'org_id,source_type,source_id' THEN
    ALTER TABLE fin_voucher DROP INDEX uk_fin_voucher_source;
    SET indexed_columns = NULL;
  END IF;
  IF indexed_columns IS NULL THEN
    ALTER TABLE fin_voucher ADD UNIQUE KEY uk_fin_voucher_source (org_id, source_type, source_id);
  END IF;
END//
DELIMITER ;
CALL phase3_fix_fin_voucher_source_index();
DROP PROCEDURE IF EXISTS phase3_fix_fin_voucher_source_index;

INSERT INTO sys_menu (id, parent_id, code, name, path, component, menu_type, sort_order)
SELECT '10000000-0000-0000-0000-000000000017', id, 'page:finance:foundation:view', '总账基础', '/finance/foundation', 'FinanceFoundation', 'menu', 6
FROM sys_menu WHERE code = 'finance:view'
ON DUPLICATE KEY UPDATE name = VALUES(name), path = VALUES(path), component = VALUES(component), sort_order = VALUES(sort_order);

INSERT INTO sys_menu (id, parent_id, code, name, path, component, menu_type, sort_order)
SELECT '10000000-0000-0000-0000-000000000018', NULL, 'page:documents:workspace:view', '业务单据中心', '/documents', 'UnifiedDocumentCenter', 'menu', 80
FROM sys_menu WHERE code = 'dashboard:view'
ON DUPLICATE KEY UPDATE name = VALUES(name), path = VALUES(path), component = VALUES(component), sort_order = VALUES(sort_order);

INSERT INTO sys_role_menu (role_id, menu_id)
SELECT '00000000-0000-0000-0000-000000000003', id FROM sys_menu
WHERE code IN ('page:finance:foundation:view', 'page:documents:workspace:view')
ON DUPLICATE KEY UPDATE role_id = VALUES(role_id);

INSERT INTO sys_schema_migration (version, description)
VALUES ('007_finance_ledger_production_cost', '总账基础、凭证记账冲销、固定资产折旧与生产实际成本')
ON DUPLICATE KEY UPDATE description = VALUES(description);
