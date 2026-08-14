-- P1: inventory reservation/traceability and quality plan support.
USE erp;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS inv_reservation (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, source_type VARCHAR(64) NOT NULL,
  source_id CHAR(36) NOT NULL, material_id CHAR(36) NOT NULL, warehouse_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL, released_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'reserved', note VARCHAR(255) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_inv_reservation_source_line (org_id, source_type, source_id, material_id, warehouse_id),
  KEY idx_inv_reservation_material (org_id, material_id, warehouse_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_trace_event (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, material_id CHAR(36) NOT NULL, batch_id CHAR(36) NULL,
  transaction_id CHAR(36) NULL, source_type VARCHAR(64) NOT NULL, source_id CHAR(36) NOT NULL,
  direction VARCHAR(16) NOT NULL, quantity DECIMAL(18,6) NOT NULL, warehouse_id CHAR(36) NOT NULL,
  location_id CHAR(36) NULL, event_time DATE NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY idx_inv_trace_material (org_id, material_id, batch_id), KEY idx_inv_trace_source (org_id, source_type, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS qa_defect_catalog (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, code VARCHAR(64) NOT NULL, name VARCHAR(128) NOT NULL,
  severity VARCHAR(32) NOT NULL DEFAULT 'major', status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_qa_defect_code (org_id, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO sys_menu (id, parent_id, code, name, path, component, menu_type, sort_order)
SELECT '10000000-0000-0000-0000-000000000019', id, 'page:inventory:control-center:view', '库存控制中心', '/inventory/control-center', 'ControlCenter', 'menu', 8
FROM sys_menu WHERE code = 'inventory:view'
ON DUPLICATE KEY UPDATE name = VALUES(name), path = VALUES(path), component = VALUES(component);

SET @sql = (SELECT IF(COUNT(*) = 0, 'ALTER TABLE qa_inspection ADD COLUMN plan_id CHAR(36) NULL', 'SELECT 1') FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_inspection' AND column_name = 'plan_id');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(COUNT(*) = 0, 'ALTER TABLE qa_inspection ADD COLUMN sample_size INT NULL', 'SELECT 1') FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_inspection' AND column_name = 'sample_size');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

INSERT INTO sys_schema_migration (version, description)
VALUES ('009_p1_control_loops', 'P1 库存预留追溯与质量计划基础能力')
ON DUPLICATE KEY UPDATE description = VALUES(description);
