-- Versioned migration: persisted views and asynchronous document exports.
-- Safe to replay on MySQL 8.0.
USE erp;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS biz_saved_view (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  owner_id CHAR(36) NOT NULL,
  name VARCHAR(128) NOT NULL,
  business_type VARCHAR(64) NULL,
  filters_json JSON NOT NULL,
  is_shared TINYINT(1) NOT NULL DEFAULT 0,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_biz_saved_view_owner_name (org_id, owner_id, name),
  KEY idx_biz_saved_view_type (business_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS biz_export_job (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  owner_id CHAR(36) NOT NULL,
  business_type VARCHAR(64) NULL,
  filters_json JSON NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  file_key VARCHAR(255) NULL,
  file_name VARCHAR(255) NULL,
  row_count INT NOT NULL DEFAULT 0,
  error_message VARCHAR(500) NULL,
  completed_at DATETIME(6) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_biz_export_job_owner_status (org_id, owner_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO sys_schema_migration (version, description)
VALUES ('008_unified_document_operations', '统一单据中心保存视图、批量命令与后台导出')
ON DUPLICATE KEY UPDATE description = VALUES(description);
