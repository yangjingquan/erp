-- Versioned migration: SPC out-of-control exception closed loop.
-- Safe to replay on MySQL 8.0.
USE erp;

CREATE TABLE IF NOT EXISTS qa_spc_exception (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  spc_record_id CHAR(36) NOT NULL,
  nonconformance_id CHAR(36) NULL,
  material_id CHAR(36) NOT NULL,
  metric VARCHAR(128) NOT NULL,
  control_status VARCHAR(32) NOT NULL DEFAULT 'out_of_control',
  status VARCHAR(32) NOT NULL DEFAULT 'pending_review',
  owner_id CHAR(36) NULL,
  due_date DATE NULL,
  containment_action VARCHAR(1000) NULL,
  root_cause VARCHAR(1000) NULL,
  closure_evidence VARCHAR(1000) NULL,
  retest_record_id CHAR(36) NULL,
  closed_at DATETIME(6) NULL,
  closed_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_qa_spc_exception_scope (org_id, status, created_at),
  KEY idx_qa_spc_exception_record (org_id, spc_record_id),
  KEY idx_qa_spc_exception_owner (org_id, owner_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP PROCEDURE IF EXISTS phase_spc_add_column;
DELIMITER //
CREATE PROCEDURE phase_spc_add_column(
  IN column_name_input VARCHAR(64),
  IN column_definition TEXT
)
BEGIN
  DECLARE column_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO column_exists
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'qa_spc_record'
    AND column_name = column_name_input;
  IF column_exists = 0 THEN
    SET @spc_sql = CONCAT('ALTER TABLE qa_spc_record ADD COLUMN ', column_name_input, ' ', column_definition);
    PREPARE spc_statement FROM @spc_sql;
    EXECUTE spc_statement;
    DEALLOCATE PREPARE spc_statement;
  END IF;
END//
DELIMITER ;

CALL phase_spc_add_column('parent_record_id', 'CHAR(36) NULL');
CALL phase_spc_add_column('exception_id', 'CHAR(36) NULL');
DROP PROCEDURE IF EXISTS phase_spc_add_column;

