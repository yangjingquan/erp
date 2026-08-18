-- Supplier quality aggregation, review, score and CAPA linkage.
USE erp;

DROP PROCEDURE IF EXISTS phase3_add_supplier_quality_column;
DELIMITER //
CREATE PROCEDURE phase3_add_supplier_quality_column(
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
    SET @supplier_quality_sql = CONCAT('ALTER TABLE `', table_name_input, '` ADD COLUMN `', column_name_input, '` ', column_definition);
    PREPARE supplier_quality_statement FROM @supplier_quality_sql;
    EXECUTE supplier_quality_statement;
    DEALLOCATE PREPARE supplier_quality_statement;
  END IF;
END//
DELIMITER ;

CALL phase3_add_supplier_quality_column('qa_supplier_quality', 'aggregation_source', "VARCHAR(32) NOT NULL DEFAULT 'purchase_inspection'");
CALL phase3_add_supplier_quality_column('qa_supplier_quality', 'review_comment', 'VARCHAR(500) NULL');
CALL phase3_add_supplier_quality_column('qa_supplier_quality', 'reviewed_by', 'CHAR(36) NULL');
CALL phase3_add_supplier_quality_column('qa_supplier_quality', 'reviewed_at', 'DATETIME(6) NULL');
CALL phase3_add_supplier_quality_column('qa_supplier_quality', 'capa_required', 'TINYINT(1) NOT NULL DEFAULT 0');
CALL phase3_add_supplier_quality_column('qa_supplier_quality', 'capa_status', "VARCHAR(32) NOT NULL DEFAULT 'not_required'");
CALL phase3_add_supplier_quality_column('qa_supplier_quality', 'capa_nonconformance_id', 'CHAR(36) NULL');
CALL phase3_add_supplier_quality_column('qa_supplier_quality', 'capa_trigger_reason', 'VARCHAR(500) NULL');
CALL phase3_add_supplier_quality_column('qa_nonconformance', 'supplier_quality_id', 'CHAR(36) NULL');
CALL phase3_add_supplier_quality_column('qa_nonconformance', 'supplier_id', 'CHAR(36) NULL');
CALL phase3_add_supplier_quality_column('qa_nonconformance', 'supplier_period', 'VARCHAR(7) NULL');
DROP PROCEDURE IF EXISTS phase3_add_supplier_quality_column;

ALTER TABLE qa_nonconformance MODIFY COLUMN inspection_id CHAR(36) NULL;

DROP PROCEDURE IF EXISTS phase3_add_supplier_quality_index;
DELIMITER //
CREATE PROCEDURE phase3_add_supplier_quality_index()
BEGIN
  DECLARE index_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO index_exists
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'qa_nonconformance'
    AND index_name = 'idx_qa_nonconformance_supplier_quality';
  IF index_exists = 0 THEN
    ALTER TABLE qa_nonconformance ADD KEY idx_qa_nonconformance_supplier_quality (org_id, supplier_quality_id, status);
  END IF;
END//
DELIMITER ;
CALL phase3_add_supplier_quality_index();
DROP PROCEDURE IF EXISTS phase3_add_supplier_quality_index;

INSERT INTO sys_schema_migration (version, description)
VALUES ('016_supplier_quality_closed_loop', '供应商质量自动汇总、审核、绩效联动与 CAPA 触发')
ON DUPLICATE KEY UPDATE description = VALUES(description);
