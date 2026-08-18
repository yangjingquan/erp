-- Persist the source rows used by automatic supplier-quality aggregation.
USE erp;

DROP PROCEDURE IF EXISTS phase4_add_supplier_quality_snapshot;
DELIMITER //
CREATE PROCEDURE phase4_add_supplier_quality_snapshot()
BEGIN
  DECLARE column_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO column_exists
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'qa_supplier_quality'
    AND column_name = 'source_snapshot_json';
  IF column_exists = 0 THEN
    ALTER TABLE qa_supplier_quality ADD COLUMN source_snapshot_json JSON NULL;
  END IF;
END//
DELIMITER ;
CALL phase4_add_supplier_quality_snapshot();
DROP PROCEDURE IF EXISTS phase4_add_supplier_quality_snapshot;

INSERT INTO sys_schema_migration (version, description)
VALUES ('017_supplier_quality_source_snapshot', '供应商质量自动汇总来源快照')
ON DUPLICATE KEY UPDATE description = VALUES(description);
