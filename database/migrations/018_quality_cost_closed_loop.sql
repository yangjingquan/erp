-- Quality-cost source traceability and automatic-event fields.
USE erp;

DROP PROCEDURE IF EXISTS phase5_add_quality_cost_columns;
DELIMITER //
CREATE PROCEDURE phase5_add_quality_cost_columns()
BEGIN
  DECLARE source_type_exists INT DEFAULT 0;
  DECLARE status_exists INT DEFAULT 0;
  DECLARE auto_generated_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO source_type_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_quality_cost' AND column_name = 'source_type';
  SELECT COUNT(*) INTO status_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_quality_cost' AND column_name = 'status';
  SELECT COUNT(*) INTO auto_generated_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_quality_cost' AND column_name = 'auto_generated';
  IF source_type_exists = 0 THEN
    ALTER TABLE qa_quality_cost ADD COLUMN source_type VARCHAR(64) NULL;
  END IF;
  IF status_exists = 0 THEN
    ALTER TABLE qa_quality_cost ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'estimated';
  END IF;
  IF auto_generated_exists = 0 THEN
    ALTER TABLE qa_quality_cost ADD COLUMN auto_generated TINYINT(1) NOT NULL DEFAULT 0;
  END IF;
END//
DELIMITER ;
CALL phase5_add_quality_cost_columns();
DROP PROCEDURE IF EXISTS phase5_add_quality_cost_columns;

UPDATE qa_quality_cost SET status = 'confirmed' WHERE auto_generated = 0 AND status = 'estimated';

INSERT INTO sys_schema_migration (version, description)
VALUES ('018_quality_cost_closed_loop', '质量成本来源追溯与自动归集')
ON DUPLICATE KEY UPDATE description = VALUES(description);
