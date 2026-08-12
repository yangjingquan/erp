-- Versioned migration: unified document workbench and collaboration platform.
-- Safe to replay on MySQL 8.0.
USE erp;

CREATE TABLE IF NOT EXISTS sys_schema_migration (
  version VARCHAR(64) PRIMARY KEY,
  description VARCHAR(255) NOT NULL,
  applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS biz_document (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  business_type VARCHAR(64) NOT NULL,
  business_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  title VARCHAR(255) NOT NULL,
  status VARCHAR(32) NOT NULL,
  document_date DATE NULL,
  owner_id CHAR(36) NULL,
  party_type VARCHAR(32) NULL,
  party_id CHAR(36) NULL,
  party_name VARCHAR(128) NULL,
  amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  summary_json JSON NOT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_biz_document_object (org_id, business_type, business_id),
  KEY idx_biz_document_query (org_id, business_type, status, document_date),
  KEY idx_biz_document_doc_no (doc_no),
  KEY idx_biz_document_owner (owner_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS biz_document_relation (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  from_type VARCHAR(64) NOT NULL,
  from_id CHAR(36) NOT NULL,
  to_type VARCHAR(64) NOT NULL,
  to_id CHAR(36) NOT NULL,
  relation_type VARCHAR(32) NOT NULL,
  quantity DECIMAL(18,6) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_biz_document_relation (org_id, from_type, from_id, to_type, to_id, relation_type),
  KEY idx_biz_relation_from (org_id, from_type, from_id),
  KEY idx_biz_relation_to (org_id, to_type, to_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS biz_attachment (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  object_type VARCHAR(64) NOT NULL,
  object_id CHAR(36) NOT NULL,
  file_key VARCHAR(255) NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  content_type VARCHAR(128) NOT NULL,
  size_bytes BIGINT NOT NULL,
  visibility VARCHAR(32) NOT NULL DEFAULT 'internal',
  uploaded_by CHAR(36) NOT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_biz_attachment_file_key (file_key),
  KEY idx_biz_attachment_object (org_id, object_type, object_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS biz_comment (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  object_type VARCHAR(64) NOT NULL,
  object_id CHAR(36) NOT NULL,
  author_id CHAR(36) NOT NULL,
  author_name VARCHAR(128) NOT NULL,
  content TEXT NOT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_biz_comment_object (org_id, object_type, object_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sys_notification (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  recipient_id CHAR(36) NOT NULL,
  notification_type VARCHAR(32) NOT NULL,
  severity VARCHAR(16) NOT NULL DEFAULT 'info',
  title VARCHAR(128) NOT NULL,
  content VARCHAR(500) NOT NULL,
  object_type VARCHAR(64) NULL,
  object_id CHAR(36) NULL,
  action_url VARCHAR(500) NULL,
  read_at DATETIME(6) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_sys_notification_recipient (org_id, recipient_id, read_at, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sys_idempotency_record (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NULL,
  user_id CHAR(36) NOT NULL,
  idempotency_key VARCHAR(128) NOT NULL,
  method VARCHAR(16) NOT NULL,
  path VARCHAR(500) NOT NULL,
  request_hash VARCHAR(64) NOT NULL,
  response_status INT NOT NULL,
  response_json JSON NOT NULL,
  created_at DATETIME(6) NOT NULL,
  expires_at DATETIME(6) NOT NULL,
  UNIQUE KEY uk_sys_idempotency_request (user_id, idempotency_key, method, path(255)),
  KEY idx_sys_idempotency_expiry (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO sys_schema_migration (version, description)
VALUES ('001_platform_workbench', '统一单据工作台、协同、通知与幂等')
ON DUPLICATE KEY UPDATE description = VALUES(description);
