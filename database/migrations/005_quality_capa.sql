-- Versioned migration: quality NCR/CAPA closed loop.
-- Safe to replay on MySQL 8.0.
USE erp;

CREATE TABLE IF NOT EXISTS sys_schema_migration (
  version VARCHAR(64) PRIMARY KEY,
  description VARCHAR(255) NOT NULL,
  applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS qa_nonconformance (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  inspection_id CHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'open',
  description VARCHAR(500) NOT NULL,
  severity VARCHAR(32) NOT NULL DEFAULT 'major',
  disposition VARCHAR(32) NULL,
  owner_id CHAR(36) NULL,
  due_date DATE NULL,
  root_cause VARCHAR(1000) NULL,
  closure_evidence VARCHAR(1000) NULL,
  closed_at DATETIME(6) NULL,
  closed_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_qa_nonconformance_inspection (org_id, inspection_id),
  KEY idx_qa_nonconformance_owner_due (org_id, owner_id, due_date, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Some development databases were created from the previous ORM typo. Copy
-- those rows into the canonical table without dropping the legacy table.
SET @legacy_quality_exists = (
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema = DATABASE() AND table_name = 'qa_nonconformity'
);
SET @legacy_quality_sql = IF(
  @legacy_quality_exists > 0,
  'INSERT IGNORE INTO qa_nonconformance (id, org_id, inspection_id, status, description, is_deleted, created_at, updated_at, version) SELECT id, org_id, inspection_id, status, COALESCE(description, ''历史不合格记录''), is_deleted, created_at, updated_at, version FROM qa_nonconformity',
  'SELECT 1'
);
PREPARE legacy_quality_statement FROM @legacy_quality_sql;
EXECUTE legacy_quality_statement;
DEALLOCATE PREPARE legacy_quality_statement;

DROP PROCEDURE IF EXISTS phase2_add_quality_capa_column;
DELIMITER //
CREATE PROCEDURE phase2_add_quality_capa_column(
  IN column_name_input VARCHAR(64),
  IN column_definition TEXT
)
BEGIN
  DECLARE column_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO column_exists
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'qa_nonconformance'
    AND column_name = column_name_input;
  IF column_exists = 0 THEN
    SET @quality_capa_sql = CONCAT(
      'ALTER TABLE `qa_nonconformance` ADD COLUMN `', column_name_input, '` ', column_definition
    );
    PREPARE quality_capa_statement FROM @quality_capa_sql;
    EXECUTE quality_capa_statement;
    DEALLOCATE PREPARE quality_capa_statement;
  END IF;
END//
DELIMITER ;

CALL phase2_add_quality_capa_column('severity', 'VARCHAR(32) NOT NULL DEFAULT ''major''');
CALL phase2_add_quality_capa_column('disposition', 'VARCHAR(32) NULL');
CALL phase2_add_quality_capa_column('owner_id', 'CHAR(36) NULL');
CALL phase2_add_quality_capa_column('due_date', 'DATE NULL');
CALL phase2_add_quality_capa_column('root_cause', 'VARCHAR(1000) NULL');
CALL phase2_add_quality_capa_column('closure_evidence', 'VARCHAR(1000) NULL');
CALL phase2_add_quality_capa_column('closed_at', 'DATETIME(6) NULL');
CALL phase2_add_quality_capa_column('closed_by', 'CHAR(36) NULL');
DROP PROCEDURE IF EXISTS phase2_add_quality_capa_column;

DROP PROCEDURE IF EXISTS phase2_add_quality_capa_index;
DELIMITER //
CREATE PROCEDURE phase2_add_quality_capa_index(
  IN index_name_input VARCHAR(64),
  IN index_definition TEXT
)
BEGIN
  DECLARE index_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO index_exists
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'qa_nonconformance'
    AND index_name = index_name_input;
  IF index_exists = 0 THEN
    SET @quality_capa_index_sql = CONCAT(
      'ALTER TABLE `qa_nonconformance` ADD ', index_definition
    );
    PREPARE quality_capa_index_statement FROM @quality_capa_index_sql;
    EXECUTE quality_capa_index_statement;
    DEALLOCATE PREPARE quality_capa_index_statement;
  END IF;
END//
DELIMITER ;

CALL phase2_add_quality_capa_index('uk_qa_nonconformance_inspection', 'UNIQUE KEY uk_qa_nonconformance_inspection (org_id, inspection_id)');
CALL phase2_add_quality_capa_index('idx_qa_nonconformance_owner_due', 'KEY idx_qa_nonconformance_owner_due (org_id, owner_id, due_date, status)');
DROP PROCEDURE IF EXISTS phase2_add_quality_capa_index;

CREATE TABLE IF NOT EXISTS qa_capa_action (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  nonconformance_id CHAR(36) NOT NULL,
  action_type VARCHAR(32) NOT NULL,
  description VARCHAR(500) NOT NULL,
  owner_id CHAR(36) NOT NULL,
  due_date DATE NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'open',
  completion_evidence VARCHAR(1000) NULL,
  completed_at DATETIME(6) NULL,
  completed_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_qa_capa_nonconformance (org_id, nonconformance_id, status),
  KEY idx_qa_capa_owner_due (org_id, owner_id, due_date, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO sys_menu (id, parent_id, code, name, path, component, menu_type, sort_order)
SELECT
  '10000000-0000-0000-0000-000000000015', id,
  'page:quality:nonconformances:view', '不合格与 CAPA',
  '/quality/nonconformances', 'NonconformanceList', 'menu', 2
FROM sys_menu WHERE code = 'quality:view'
ON DUPLICATE KEY UPDATE
  name = VALUES(name), path = VALUES(path), component = VALUES(component), sort_order = VALUES(sort_order);

INSERT INTO sys_role_menu (role_id, menu_id)
SELECT '00000000-0000-0000-0000-000000000003', id
FROM sys_menu WHERE code = 'page:quality:nonconformances:view'
ON DUPLICATE KEY UPDATE role_id = VALUES(role_id);

INSERT INTO sys_schema_migration (version, description)
VALUES ('005_quality_capa', '质量不合格、纠正预防措施、证据与关闭校验闭环')
ON DUPLICATE KEY UPDATE description = VALUES(description);
