-- Versioned migration: bring legacy event-outbox tables in line with the ORM model.
USE erp;

SET @column_exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = 'erp' AND table_name = 'ext_event_outbox' AND column_name = 'org_id'
);
SET @migration_sql = IF(
  @column_exists = 0,
  'ALTER TABLE ext_event_outbox ADD COLUMN org_id CHAR(36) NULL AFTER id',
  'SELECT 1'
);
PREPARE migration_statement FROM @migration_sql;
EXECUTE migration_statement;
DEALLOCATE PREPARE migration_statement;

SET @column_exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = 'erp' AND table_name = 'ext_event_outbox' AND column_name = 'claim_token'
);
SET @migration_sql = IF(
  @column_exists = 0,
  'ALTER TABLE ext_event_outbox ADD COLUMN claim_token CHAR(36) NULL AFTER next_retry_at',
  'SELECT 1'
);
PREPARE migration_statement FROM @migration_sql;
EXECUTE migration_statement;
DEALLOCATE PREPARE migration_statement;

SET @column_exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = 'erp' AND table_name = 'ext_event_outbox' AND column_name = 'is_deleted'
);
SET @migration_sql = IF(
  @column_exists = 0,
  'ALTER TABLE ext_event_outbox ADD COLUMN is_deleted TINYINT(1) NOT NULL DEFAULT 0 AFTER claim_token',
  'SELECT 1'
);
PREPARE migration_statement FROM @migration_sql;
EXECUTE migration_statement;
DEALLOCATE PREPARE migration_statement;

SET @column_exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = 'erp' AND table_name = 'ext_event_outbox' AND column_name = 'updated_at'
);
SET @migration_sql = IF(
  @column_exists = 0,
  'ALTER TABLE ext_event_outbox ADD COLUMN updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) AFTER created_at',
  'SELECT 1'
);
PREPARE migration_statement FROM @migration_sql;
EXECUTE migration_statement;
DEALLOCATE PREPARE migration_statement;

SET @column_exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = 'erp' AND table_name = 'ext_event_outbox' AND column_name = 'version'
);
SET @migration_sql = IF(
  @column_exists = 0,
  'ALTER TABLE ext_event_outbox ADD COLUMN version INT NOT NULL DEFAULT 1 AFTER updated_at',
  'SELECT 1'
);
PREPARE migration_statement FROM @migration_sql;
EXECUTE migration_statement;
DEALLOCATE PREPARE migration_statement;

SET @index_exists = (
  SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema = 'erp' AND table_name = 'ext_event_outbox' AND index_name = 'idx_ext_event_outbox_org_id'
);
SET @migration_sql = IF(
  @index_exists = 0,
  'ALTER TABLE ext_event_outbox ADD INDEX idx_ext_event_outbox_org_id (org_id)',
  'SELECT 1'
);
PREPARE migration_statement FROM @migration_sql;
EXECUTE migration_statement;
DEALLOCATE PREPARE migration_statement;

SET @index_exists = (
  SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema = 'erp' AND table_name = 'ext_event_outbox' AND index_name = 'idx_ext_event_outbox_claim_token'
);
SET @migration_sql = IF(
  @index_exists = 0,
  'ALTER TABLE ext_event_outbox ADD INDEX idx_ext_event_outbox_claim_token (claim_token)',
  'SELECT 1'
);
PREPARE migration_statement FROM @migration_sql;
EXECUTE migration_statement;
DEALLOCATE PREPARE migration_statement;

SET @index_exists = (
  SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema = 'erp' AND table_name = 'ext_event_outbox' AND index_name = 'idx_ext_event_outbox_status_retry'
);
SET @migration_sql = IF(
  @index_exists = 0,
  'ALTER TABLE ext_event_outbox ADD INDEX idx_ext_event_outbox_status_retry (status, next_retry_at)',
  'SELECT 1'
);
PREPARE migration_statement FROM @migration_sql;
EXECUTE migration_statement;
DEALLOCATE PREPARE migration_statement;

INSERT INTO sys_schema_migration (version, description)
VALUES ('003_event_outbox_compatibility', '旧版事件发件箱字段兼容')
ON DUPLICATE KEY UPDATE description = VALUES(description);
