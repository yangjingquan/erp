-- Versioned migration: enforce department/own data scope in the document index.
USE erp;

SET @department_column_exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = 'erp' AND table_name = 'biz_document' AND column_name = 'department_id'
);
SET @department_column_sql = IF(
  @department_column_exists = 0,
  'ALTER TABLE biz_document ADD COLUMN department_id CHAR(36) NULL AFTER owner_id, ADD INDEX idx_biz_document_department (department_id)',
  'SELECT 1'
);
PREPARE document_scope_statement FROM @department_column_sql;
EXECUTE document_scope_statement;
DEALLOCATE PREPARE document_scope_statement;

INSERT INTO sys_schema_migration (version, description)
VALUES ('002_document_department_scope', '单据索引部门数据范围')
ON DUPLICATE KEY UPDATE description = VALUES(description);
