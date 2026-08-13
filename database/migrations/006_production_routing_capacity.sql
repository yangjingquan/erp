-- Versioned migration: production routing, work-center capacity and readiness loop.
-- Safe to replay on MySQL 8.0.
USE erp;

CREATE TABLE IF NOT EXISTS sys_schema_migration (
  version VARCHAR(64) PRIMARY KEY,
  description VARCHAR(255) NOT NULL,
  applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_work_center (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  code VARCHAR(32) NOT NULL,
  name VARCHAR(128) NOT NULL,
  daily_capacity_hours DECIMAL(18,6) NOT NULL DEFAULT 8,
  efficiency_rate DECIMAL(8,4) NOT NULL DEFAULT 1,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_by CHAR(36) NULL,
  updated_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_work_center_code (org_id, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_capacity_calendar (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  work_center_id CHAR(36) NOT NULL,
  capacity_date DATE NOT NULL,
  available_hours DECIMAL(18,6) NOT NULL,
  note VARCHAR(255) NULL,
  created_by CHAR(36) NULL,
  updated_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_capacity_calendar_day (org_id, work_center_id, capacity_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP PROCEDURE IF EXISTS phase2_add_production_resource_column;
DELIMITER //
CREATE PROCEDURE phase2_add_production_resource_column(
  IN table_name_input VARCHAR(64),
  IN column_name_input VARCHAR(64),
  IN column_definition TEXT
)
BEGIN
  DECLARE column_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO column_exists
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = table_name_input
    AND column_name = column_name_input;
  IF column_exists = 0 THEN
    SET @production_resource_sql = CONCAT(
      'ALTER TABLE `', table_name_input, '` ADD COLUMN `', column_name_input, '` ', column_definition
    );
    PREPARE production_resource_statement FROM @production_resource_sql;
    EXECUTE production_resource_statement;
    DEALLOCATE PREPARE production_resource_statement;
  END IF;
END//
DELIMITER ;

CALL phase2_add_production_resource_column('mfg_routing', 'bom_id', 'CHAR(36) NULL');
CALL phase2_add_production_resource_column('mfg_routing', 'routing_version', 'VARCHAR(32) NOT NULL DEFAULT ''1.0''');
CALL phase2_add_production_resource_column('mfg_routing', 'effective_from', 'DATE NULL');
CALL phase2_add_production_resource_column('mfg_routing', 'effective_to', 'DATE NULL');
CALL phase2_add_production_resource_column('mfg_routing', 'created_by', 'CHAR(36) NULL');
CALL phase2_add_production_resource_column('mfg_routing', 'updated_by', 'CHAR(36) NULL');
CALL phase2_add_production_resource_column('mfg_routing_operation', 'work_center_id', 'CHAR(36) NULL');
CALL phase2_add_production_resource_column('mfg_routing_operation', 'setup_hours', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_production_resource_column('mfg_routing_operation', 'run_hours_per_unit', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_production_resource_column('mfg_work_order', 'routing_id', 'CHAR(36) NULL');
CALL phase2_add_production_resource_column('mfg_work_order', 'routing_snapshot', 'JSON NULL');
CALL phase2_add_production_resource_column('mfg_work_report', 'operation_id', 'CHAR(36) NULL');
CALL phase2_add_production_resource_column('mfg_work_report', 'operation_name', 'VARCHAR(128) NULL');
DROP PROCEDURE IF EXISTS phase2_add_production_resource_column;

UPDATE mfg_work_order SET routing_snapshot = JSON_OBJECT() WHERE routing_snapshot IS NULL;
ALTER TABLE mfg_work_order MODIFY COLUMN routing_snapshot JSON NOT NULL;

DROP PROCEDURE IF EXISTS phase2_add_production_resource_index;
DELIMITER //
CREATE PROCEDURE phase2_add_production_resource_index(
  IN table_name_input VARCHAR(64),
  IN index_name_input VARCHAR(64),
  IN index_definition TEXT
)
BEGIN
  DECLARE index_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO index_exists
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = table_name_input
    AND index_name = index_name_input;
  IF index_exists = 0 THEN
    SET @production_resource_index_sql = CONCAT(
      'ALTER TABLE `', table_name_input, '` ADD ', index_definition
    );
    PREPARE production_resource_index_statement FROM @production_resource_index_sql;
    EXECUTE production_resource_index_statement;
    DEALLOCATE PREPARE production_resource_index_statement;
  END IF;
END//
DELIMITER ;

CALL phase2_add_production_resource_index('mfg_routing', 'uk_mfg_routing_bom_version', 'UNIQUE KEY uk_mfg_routing_bom_version (org_id, bom_id, routing_version)');
CALL phase2_add_production_resource_index('mfg_routing_operation', 'idx_mfg_routing_operation_center', 'KEY idx_mfg_routing_operation_center (work_center_id)');
CALL phase2_add_production_resource_index('mfg_routing_operation', 'uk_mfg_routing_operation_line', 'UNIQUE KEY uk_mfg_routing_operation_line (routing_id, line_no)');
CALL phase2_add_production_resource_index('mfg_work_report', 'idx_mfg_work_report_operation', 'KEY idx_mfg_work_report_operation (operation_id)');
DROP PROCEDURE IF EXISTS phase2_add_production_resource_index;

INSERT INTO sys_menu (id, parent_id, code, name, path, component, menu_type, sort_order)
SELECT
  '10000000-0000-0000-0000-000000000016', id,
  'page:production:resources:view', '工艺与产能',
  '/production/resources', 'ProductionResources', 'menu', 4
FROM sys_menu WHERE code = 'production:view'
ON DUPLICATE KEY UPDATE
  name = VALUES(name), path = VALUES(path), component = VALUES(component), sort_order = VALUES(sort_order);

INSERT INTO sys_role_menu (role_id, menu_id)
SELECT '00000000-0000-0000-0000-000000000003', id
FROM sys_menu WHERE code = 'page:production:resources:view'
ON DUPLICATE KEY UPDATE role_id = VALUES(role_id);

INSERT INTO sys_schema_migration (version, description)
VALUES ('006_production_routing_capacity', '工艺路线、工作中心、产能日历、齐套检查与工序报工闭环')
ON DUPLICATE KEY UPDATE description = VALUES(description);
