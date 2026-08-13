-- P2: 多组织成员、开放平台事件订阅、多币种与汇率
USE erp;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS sys_org_membership (
  id CHAR(36) PRIMARY KEY,
  user_id CHAR(36) NOT NULL,
  org_id CHAR(36) NOT NULL,
  membership_type VARCHAR(32) NOT NULL DEFAULT 'member',
  is_default TINYINT(1) NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_sys_org_membership_user_org (user_id, org_id),
  KEY idx_sys_org_membership_org (org_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ext_event_subscription (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  name VARCHAR(128) NOT NULL,
  endpoint_url VARCHAR(500) NOT NULL,
  event_types JSON NOT NULL,
  secret_hash VARCHAR(128) NOT NULL,
  signing_secret VARCHAR(255) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  failure_count INT NOT NULL DEFAULT 0,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_ext_event_subscription_name (org_id, name),
  KEY idx_ext_event_subscription_org (org_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ext_event_delivery (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  event_id CHAR(36) NOT NULL,
  subscription_id CHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  attempt_count INT NOT NULL DEFAULT 0,
  response_status INT NULL,
  response_body VARCHAR(1000) NULL,
  delivered_at DATETIME(6) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_ext_event_delivery_event_subscription (event_id, subscription_id),
  KEY idx_ext_event_delivery_org (org_id, status),
  KEY idx_ext_event_delivery_event (event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_currency (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  code VARCHAR(8) NOT NULL,
  name VARCHAR(64) NOT NULL,
  symbol VARCHAR(8) NULL,
  decimal_places INT NOT NULL DEFAULT 2,
  is_base TINYINT(1) NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_fin_currency_org_code (org_id, code),
  KEY idx_fin_currency_org (org_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_exchange_rate (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  base_currency VARCHAR(8) NOT NULL,
  quote_currency VARCHAR(8) NOT NULL,
  rate_date DATE NOT NULL,
  rate DECIMAL(18,8) NOT NULL,
  source VARCHAR(64) NOT NULL DEFAULT 'manual',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_fin_exchange_rate_day (org_id, base_currency, quote_currency, rate_date),
  KEY idx_fin_exchange_rate_lookup (org_id, base_currency, quote_currency, rate_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO sys_schema_migration (version, description)
VALUES ('010_p2_multi_org_platform_currency', 'P2 多组织成员、开放平台事件订阅与多币种基础能力')
ON DUPLICATE KEY UPDATE description = VALUES(description);

INSERT INTO sys_menu (id, parent_id, code, name, path, component, menu_type, sort_order)
SELECT '10000000-0000-0000-0000-000000000020', id, 'page:finance:currencies:view', '多币种与汇率', '/finance/currencies', 'CurrencySettings', 'menu', 7
FROM sys_menu WHERE code = 'finance:view'
ON DUPLICATE KEY UPDATE name = VALUES(name), path = VALUES(path), component = VALUES(component), sort_order = VALUES(sort_order);
INSERT INTO sys_menu (id, parent_id, code, name, path, component, menu_type, sort_order)
SELECT '10000000-0000-0000-0000-000000000021', id, 'page:config:platform-events:view', '事件订阅', '/settings/platform-events', 'PlatformEvents', 'menu', 5
FROM sys_menu WHERE code = 'config:view'
ON DUPLICATE KEY UPDATE name = VALUES(name), path = VALUES(path), component = VALUES(component), sort_order = VALUES(sort_order);
