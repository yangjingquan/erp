-- ERP MySQL 8.0 initialization script
-- Database: 127.0.0.1:3306/erp
-- User: root
-- The seeded admin password is documented in README.md and stored only as bcrypt.

CREATE DATABASE IF NOT EXISTS erp
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE erp;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS sys_org (
  id CHAR(36) PRIMARY KEY,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  parent_id CHAR(36) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_sys_org_code (code),
  KEY idx_sys_org_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sys_department (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  parent_id CHAR(36) NULL,
  manager_id CHAR(36) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_sys_department_org_code (org_id, code),
  KEY idx_sys_department_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sys_user (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  department_id CHAR(36) NULL,
  username VARCHAR(64) NOT NULL,
  display_name VARCHAR(128) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  email VARCHAR(128) NULL,
  phone VARCHAR(32) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_superuser TINYINT(1) NOT NULL DEFAULT 0,
  last_login_at DATETIME(6) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_sys_user_username (username),
  KEY idx_sys_user_org_department (org_id, department_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sys_role (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  data_scope_type VARCHAR(32) NOT NULL DEFAULT 'department',
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_sys_role_org_code (org_id, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sys_menu (
  id CHAR(36) PRIMARY KEY,
  parent_id CHAR(36) NULL,
  code VARCHAR(128) NOT NULL,
  name VARCHAR(128) NOT NULL,
  path VARCHAR(255) NULL,
  component VARCHAR(255) NULL,
  icon VARCHAR(128) NULL,
  menu_type VARCHAR(32) NOT NULL DEFAULT 'menu',
  sort_order INT NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  UNIQUE KEY uk_sys_menu_code (code),
  KEY idx_sys_menu_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sys_permission (
  id CHAR(36) PRIMARY KEY,
  menu_id CHAR(36) NOT NULL,
  code VARCHAR(128) NOT NULL,
  name VARCHAR(128) NOT NULL,
  permission_type VARCHAR(32) NOT NULL DEFAULT 'button',
  UNIQUE KEY uk_sys_permission_code (code),
  KEY idx_sys_permission_menu (menu_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sys_user_role (
  user_id CHAR(36) NOT NULL,
  role_id CHAR(36) NOT NULL,
  PRIMARY KEY (user_id, role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sys_role_menu (
  role_id CHAR(36) NOT NULL,
  menu_id CHAR(36) NOT NULL,
  PRIMARY KEY (role_id, menu_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sys_role_permission (
  role_id CHAR(36) NOT NULL,
  permission_id CHAR(36) NOT NULL,
  PRIMARY KEY (role_id, permission_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sys_user_data_scope (
  id CHAR(36) PRIMARY KEY,
  user_id CHAR(36) NOT NULL,
  resource VARCHAR(64) NOT NULL,
  scope_type VARCHAR(32) NOT NULL,
  scope_value VARCHAR(255) NULL,
  UNIQUE KEY uk_user_data_scope (user_id, resource)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sys_operation_log (
  id CHAR(36) PRIMARY KEY,
  request_id VARCHAR(64) NULL,
  user_id CHAR(36) NULL,
  username VARCHAR(64) NULL,
  org_id CHAR(36) NULL,
  department_id CHAR(36) NULL,
  action VARCHAR(64) NOT NULL,
  resource VARCHAR(128) NOT NULL,
  target_id CHAR(36) NULL,
  detail_json JSON NULL,
  ip_address VARCHAR(64) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY idx_operation_log_user_time (user_id, created_at),
  KEY idx_operation_log_resource_time (resource, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sys_login_log (
  id CHAR(36) PRIMARY KEY,
  user_id CHAR(36) NULL,
  username VARCHAR(64) NOT NULL,
  success TINYINT(1) NOT NULL DEFAULT 0,
  ip_address VARCHAR(64) NULL,
  user_agent VARCHAR(512) NULL,
  message VARCHAR(255) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY idx_login_log_username_time (username, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS md_unit (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(64) NOT NULL,
  precision_scale INT NOT NULL DEFAULT 2,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_md_unit_org_code (org_id, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS md_tax_rate (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(64) NOT NULL,
  rate DECIMAL(8,4) NOT NULL DEFAULT 0,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_md_tax_rate_org_code (org_id, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS md_material (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  category VARCHAR(128) NULL,
  unit_id CHAR(36) NULL,
  tax_rate_id CHAR(36) NULL,
  material_type VARCHAR(32) NOT NULL DEFAULT 'goods',
  standard_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
  sale_price DECIMAL(18,6) NOT NULL DEFAULT 0,
  purchase_price DECIMAL(18,6) NOT NULL DEFAULT 0,
  min_stock DECIMAL(18,6) NOT NULL DEFAULT 0,
  max_stock DECIMAL(18,6) NOT NULL DEFAULT 0,
  specification VARCHAR(255) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_md_material_org_code (org_id, code),
  KEY idx_md_material_name (org_id, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS md_customer (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  short_name VARCHAR(64) NULL,
  owner_id CHAR(36) NULL,
  contact_name VARCHAR(64) NULL,
  contact_phone VARCHAR(64) NULL,
  address VARCHAR(255) NULL,
  credit_limit DECIMAL(18,2) NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_md_customer_org_code (org_id, code),
  KEY idx_md_customer_name (org_id, name),
  KEY idx_md_customer_owner (owner_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS md_supplier (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  short_name VARCHAR(64) NULL,
  owner_id CHAR(36) NULL,
  contact_name VARCHAR(64) NULL,
  contact_phone VARCHAR(64) NULL,
  address VARCHAR(255) NULL,
  credit_days INT NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_md_supplier_org_code (org_id, code),
  KEY idx_md_supplier_name (org_id, name),
  KEY idx_md_supplier_owner (owner_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS md_warehouse (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  manager_id CHAR(36) NULL,
  address VARCHAR(255) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_md_warehouse_org_code (org_id, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sales_quote (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  customer_id CHAR(36) NOT NULL,
  owner_id CHAR(36) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  quote_date DATE NOT NULL,
  valid_until DATE NULL,
  total_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  created_by CHAR(36) NULL,
  updated_by CHAR(36) NULL,
  version INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_sales_quote_doc_no (org_id, doc_no),
  KEY idx_sales_quote_customer (customer_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sales_quote_item (
  id CHAR(36) PRIMARY KEY,
  quote_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  unit_price DECIMAL(18,6) NOT NULL,
  tax_rate DECIMAL(8,4) NOT NULL DEFAULT 0,
  amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  line_no INT NOT NULL DEFAULT 1,
  KEY idx_sales_quote_item_quote (quote_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sales_order (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  customer_id CHAR(36) NOT NULL,
  owner_id CHAR(36) NULL,
  department_id CHAR(36) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  order_date DATE NOT NULL,
  expected_date DATE NULL,
  total_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  receivable_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  remark VARCHAR(500) NULL,
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  created_by CHAR(36) NULL,
  updated_by CHAR(36) NULL,
  version INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_sales_order_doc_no (org_id, doc_no),
  KEY idx_sales_order_customer_owner (customer_id, owner_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sales_order_item (
  id CHAR(36) PRIMARY KEY,
  order_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NULL,
  quantity DECIMAL(18,6) NOT NULL,
  delivered_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  returned_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  unit_price DECIMAL(18,6) NOT NULL,
  tax_rate DECIMAL(8,4) NOT NULL DEFAULT 0,
  amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  line_no INT NOT NULL DEFAULT 1,
  KEY idx_sales_order_item_order (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sales_delivery (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  order_id CHAR(36) NOT NULL,
  customer_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  delivery_date DATE NOT NULL,
  total_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  created_by CHAR(36) NULL,
  updated_by CHAR(36) NULL,
  version INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_sales_delivery_doc_no (org_id, doc_no),
  KEY idx_sales_delivery_order (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sales_delivery_item (
  id CHAR(36) PRIMARY KEY,
  delivery_id CHAR(36) NOT NULL,
  order_item_id CHAR(36) NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  unit_price DECIMAL(18,6) NOT NULL DEFAULT 0,
  amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  KEY idx_sales_delivery_item_delivery (delivery_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sales_return (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  source_delivery_id CHAR(36) NULL,
  customer_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  return_date DATE NOT NULL,
  total_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  created_by CHAR(36) NULL,
  version INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_sales_return_doc_no (org_id, doc_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sales_return_item (
  id CHAR(36) PRIMARY KEY,
  return_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  unit_price DECIMAL(18,6) NOT NULL DEFAULT 0,
  amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  KEY idx_sales_return_item_return (return_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sales_receivable (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  customer_id CHAR(36) NOT NULL,
  source_type VARCHAR(64) NOT NULL,
  source_id CHAR(36) NOT NULL,
  total_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  reconciled_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'open',
  due_date DATE NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_sales_receivable_source (source_type, source_id),
  UNIQUE KEY uk_sales_receivable_doc_no (org_id, doc_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS purchase_request (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  department_id CHAR(36) NULL,
  requester_id CHAR(36) NULL,
  supplier_id CHAR(36) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  request_date DATE NOT NULL,
  remark VARCHAR(500) NULL,
  created_by CHAR(36) NULL,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_purchase_request_doc_no (org_id, doc_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS purchase_request_item (
  id CHAR(36) PRIMARY KEY,
  request_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  estimated_price DECIMAL(18,6) NOT NULL DEFAULT 0,
  line_no INT NOT NULL DEFAULT 1,
  KEY idx_purchase_request_item_request (request_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS purchase_order (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  supplier_id CHAR(36) NOT NULL,
  department_id CHAR(36) NULL,
  owner_id CHAR(36) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  order_date DATE NOT NULL,
  expected_date DATE NULL,
  total_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  payable_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  created_by CHAR(36) NULL,
  updated_by CHAR(36) NULL,
  version INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_purchase_order_doc_no (org_id, doc_no),
  KEY idx_purchase_order_supplier_owner (supplier_id, owner_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS purchase_order_item (
  id CHAR(36) PRIMARY KEY,
  order_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NULL,
  quantity DECIMAL(18,6) NOT NULL,
  received_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  returned_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  unit_price DECIMAL(18,6) NOT NULL,
  tax_rate DECIMAL(8,4) NOT NULL DEFAULT 0,
  amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  line_no INT NOT NULL DEFAULT 1,
  KEY idx_purchase_order_item_order (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS purchase_receipt (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  order_id CHAR(36) NOT NULL,
  supplier_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  receipt_date DATE NOT NULL,
  total_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  created_by CHAR(36) NULL,
  version INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_purchase_receipt_doc_no (org_id, doc_no),
  KEY idx_purchase_receipt_order (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS purchase_receipt_item (
  id CHAR(36) PRIMARY KEY,
  receipt_id CHAR(36) NOT NULL,
  order_item_id CHAR(36) NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  unit_price DECIMAL(18,6) NOT NULL DEFAULT 0,
  amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  KEY idx_purchase_receipt_item_receipt (receipt_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS purchase_return (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  source_receipt_id CHAR(36) NULL,
  supplier_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  return_date DATE NOT NULL,
  total_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  created_by CHAR(36) NULL,
  version INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_purchase_return_doc_no (org_id, doc_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS purchase_return_item (
  id CHAR(36) PRIMARY KEY,
  return_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  unit_price DECIMAL(18,6) NOT NULL DEFAULT 0,
  amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  KEY idx_purchase_return_item_return (return_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS purchase_payable (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  supplier_id CHAR(36) NOT NULL,
  source_type VARCHAR(64) NOT NULL,
  source_id CHAR(36) NOT NULL,
  total_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  reconciled_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'open',
  due_date DATE NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_purchase_payable_source (source_type, source_id),
  UNIQUE KEY uk_purchase_payable_doc_no (org_id, doc_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_stock (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  locked_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  available_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  average_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_inv_stock_wh_material (warehouse_id, material_id),
  KEY idx_inv_stock_org_material (org_id, material_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_stock_transaction (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  location_id CHAR(36) NULL,
  batch_id CHAR(36) NULL,
  source_type VARCHAR(64) NOT NULL,
  source_id CHAR(36) NOT NULL,
  direction VARCHAR(16) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  unit_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
  amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  transaction_date DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  created_by CHAR(36) NULL,
  consumed_layer_ids JSON NULL,
  UNIQUE KEY uk_inv_transaction_source (source_type, source_id, warehouse_id, material_id, direction),
  KEY idx_inv_transaction_material_time (material_id, warehouse_id, transaction_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_transfer (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  from_warehouse_id CHAR(36) NOT NULL,
  to_warehouse_id CHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  transfer_date DATE NOT NULL,
  created_by CHAR(36) NULL,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_inv_transfer_doc_no (org_id, doc_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_transfer_item (
  id CHAR(36) PRIMARY KEY,
  transfer_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  unit_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
  KEY idx_inv_transfer_item_transfer (transfer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_count (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  count_date DATE NOT NULL,
  created_by CHAR(36) NULL,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_inv_count_doc_no (org_id, doc_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_count_item (
  id CHAR(36) PRIMARY KEY,
  count_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  system_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  actual_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  difference_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  unit_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
  KEY idx_inv_count_item_count (count_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_warning (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  current_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  min_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'open',
  resolved_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_inv_warning_material (warehouse_id, material_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_receipt (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  customer_id CHAR(36) NULL,
  account_name VARCHAR(128) NULL,
  amount DECIMAL(18,2) NOT NULL,
  receipt_date DATE NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  remark VARCHAR(500) NULL,
  created_by CHAR(36) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_fin_receipt_doc_no (org_id, doc_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_receipt_reconcile (
  id CHAR(36) PRIMARY KEY,
  receipt_id CHAR(36) NOT NULL,
  receivable_id CHAR(36) NOT NULL,
  amount DECIMAL(18,2) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_fin_receipt_reconcile (receipt_id, receivable_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_payment (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  supplier_id CHAR(36) NULL,
  account_name VARCHAR(128) NULL,
  amount DECIMAL(18,2) NOT NULL,
  payment_date DATE NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  remark VARCHAR(500) NULL,
  created_by CHAR(36) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_fin_payment_doc_no (org_id, doc_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_payment_reconcile (
  id CHAR(36) PRIMARY KEY,
  payment_id CHAR(36) NOT NULL,
  payable_id CHAR(36) NOT NULL,
  amount DECIMAL(18,2) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_fin_payment_reconcile (payment_id, payable_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_expense (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  applicant_id CHAR(36) NULL,
  department_id CHAR(36) NULL,
  amount DECIMAL(18,2) NOT NULL,
  expense_date DATE NOT NULL,
  expense_type VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  description VARCHAR(500) NULL,
  created_by CHAR(36) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_fin_expense_doc_no (org_id, doc_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_asset (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  asset_code VARCHAR(64) NOT NULL,
  asset_name VARCHAR(128) NOT NULL,
  category VARCHAR(64) NULL,
  purchase_date DATE NULL,
  original_value DECIMAL(18,2) NOT NULL DEFAULT 0,
  accumulated_depreciation DECIMAL(18,2) NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_fin_asset_org_code (org_id, asset_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_voucher (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  voucher_no VARCHAR(64) NOT NULL,
  voucher_date DATE NOT NULL,
  period VARCHAR(16) NOT NULL,
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  total_debit DECIMAL(18,2) NOT NULL DEFAULT 0,
  total_credit DECIMAL(18,2) NOT NULL DEFAULT 0,
  created_by CHAR(36) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_fin_voucher_no (org_id, voucher_no),
  UNIQUE KEY uk_fin_voucher_source (source_type, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fin_voucher_entry (
  id CHAR(36) PRIMARY KEY,
  voucher_id CHAR(36) NOT NULL,
  line_no INT NOT NULL,
  account_code VARCHAR(64) NOT NULL,
  account_name VARCHAR(128) NOT NULL,
  summary VARCHAR(255) NULL,
  debit_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  credit_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  customer_id CHAR(36) NULL,
  supplier_id CHAR(36) NULL,
  department_id CHAR(36) NULL,
  KEY idx_fin_voucher_entry_voucher (voucher_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wf_definition (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  business_type VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  version INT NOT NULL DEFAULT 1,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  config_json JSON NOT NULL,
  created_by CHAR(36) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_wf_definition_business_version (org_id, business_type, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wf_node (
  id CHAR(36) PRIMARY KEY,
  definition_id CHAR(36) NOT NULL,
  node_key VARCHAR(64) NOT NULL,
  node_name VARCHAR(128) NOT NULL,
  node_type VARCHAR(32) NOT NULL DEFAULT 'approval',
  sort_order INT NOT NULL DEFAULT 0,
  approver_type VARCHAR(32) NOT NULL DEFAULT 'role',
  approver_value VARCHAR(255) NULL,
  condition_json JSON NULL,
  UNIQUE KEY uk_wf_node_definition_key (definition_id, node_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wf_instance (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  business_type VARCHAR(64) NOT NULL,
  business_id CHAR(36) NOT NULL,
  definition_id CHAR(36) NOT NULL,
  current_node_key VARCHAR(64) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'running',
  started_by CHAR(36) NULL,
  started_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  completed_at DATETIME(6) NULL,
  UNIQUE KEY uk_wf_instance_business (business_type, business_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wf_task (
  id CHAR(36) PRIMARY KEY,
  instance_id CHAR(36) NOT NULL,
  node_key VARCHAR(64) NOT NULL,
  assignee_user_id CHAR(36) NULL,
  assignee_role_id CHAR(36) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  comment VARCHAR(500) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  completed_at DATETIME(6) NULL,
  KEY idx_wf_task_assignee_status (assignee_user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wf_action_log (
  id CHAR(36) PRIMARY KEY,
  instance_id CHAR(36) NOT NULL,
  task_id CHAR(36) NULL,
  action VARCHAR(32) NOT NULL,
  user_id CHAR(36) NULL,
  comment VARCHAR(500) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cfg_field_definition (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  business_type VARCHAR(64) NOT NULL,
  field_key VARCHAR(128) NOT NULL,
  label VARCHAR(128) NOT NULL,
  field_type VARCHAR(32) NOT NULL,
  visible TINYINT(1) NOT NULL DEFAULT 1,
  required TINYINT(1) NOT NULL DEFAULT 0,
  readonly TINYINT(1) NOT NULL DEFAULT 0,
  permission_code VARCHAR(128) NULL,
  sort_order INT NOT NULL DEFAULT 0,
  config_json JSON NULL,
  UNIQUE KEY uk_cfg_field_business_key (org_id, business_type, field_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cfg_number_rule (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  rule_key VARCHAR(64) NOT NULL,
  prefix VARCHAR(32) NOT NULL,
  date_format VARCHAR(32) NULL,
  sequence_length INT NOT NULL DEFAULT 4,
  reset_cycle VARCHAR(16) NOT NULL DEFAULT 'day',
  current_date_key VARCHAR(32) NULL,
  current_sequence BIGINT NOT NULL DEFAULT 0,
  UNIQUE KEY uk_cfg_number_rule_key (org_id, rule_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cfg_print_template (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  business_type VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  template_html LONGTEXT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_cfg_print_template_business_name (org_id, business_type, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cfg_global_parameter (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  parameter_key VARCHAR(128) NOT NULL,
  parameter_value TEXT NULL,
  value_type VARCHAR(32) NOT NULL DEFAULT 'string',
  description VARCHAR(255) NULL,
  UNIQUE KEY uk_cfg_global_parameter_key (org_id, parameter_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sys_backup_record (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NULL,
  file_name VARCHAR(255) NOT NULL,
  file_path VARCHAR(512) NOT NULL,
  backup_type VARCHAR(32) NOT NULL DEFAULT 'sql',
  status VARCHAR(32) NOT NULL DEFAULT 'success',
  created_by CHAR(36) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ext_module_registry (
  id CHAR(36) PRIMARY KEY,
  module_key VARCHAR(64) NOT NULL,
  module_name VARCHAR(128) NOT NULL,
  phase VARCHAR(16) NOT NULL,
  enabled TINYINT(1) NOT NULL DEFAULT 0,
  config_json JSON NULL,
  UNIQUE KEY uk_ext_module_registry_key (module_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ext_openapi_endpoint (
  id CHAR(36) PRIMARY KEY,
  endpoint_key VARCHAR(128) NOT NULL,
  path VARCHAR(255) NOT NULL,
  http_method VARCHAR(16) NOT NULL,
  module_key VARCHAR(64) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  config_json JSON NULL,
  UNIQUE KEY uk_ext_openapi_endpoint_key (endpoint_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ext_event_outbox (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NULL,
  event_type VARCHAR(128) NOT NULL,
  aggregate_type VARCHAR(128) NOT NULL,
  aggregate_id CHAR(36) NOT NULL,
  payload_json JSON NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  retry_count INT NOT NULL DEFAULT 0,
  next_retry_at DATETIME(6) NULL,
  claim_token CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_ext_event_outbox_aggregate_event (event_type, aggregate_type, aggregate_id),
  KEY idx_ext_event_outbox_claim_token (claim_token),
  KEY idx_ext_event_outbox_status_retry (status, next_retry_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_bom (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  bom_version VARCHAR(32) NOT NULL DEFAULT '1.0',
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  effective_from DATE NOT NULL,
  effective_to DATE NULL,
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  created_by CHAR(36) NULL,
  updated_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_bom_material_version (org_id, material_id, bom_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_bom_item (
  id CHAR(36) PRIMARY KEY,
  bom_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  line_no INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_bom_item_bom (bom_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_mps (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  material_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NULL,
  plan_date DATE NOT NULL,
  plan_quantity DECIMAL(18,6) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  created_by CHAR(36) NULL,
  updated_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_mps_doc_no (org_id, doc_no),
  KEY idx_mfg_mps_material_date (org_id, material_id, plan_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_mrp_run (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  mps_id CHAR(36) NOT NULL,
  bom_id CHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'completed',
  source_snapshot JSON NOT NULL,
  created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_mrp_run_doc_no (org_id, doc_no),
  KEY idx_mfg_mrp_run_mps (mps_id),
  KEY idx_mfg_mrp_run_bom (bom_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_mrp_result (
  id CHAR(36) PRIMARY KEY,
  run_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  gross_requirement DECIMAL(18,6) NOT NULL,
  available_stock DECIMAL(18,6) NOT NULL,
  open_supply_quantity DECIMAL(18,6) NOT NULL,
  safety_stock DECIMAL(18,6) NOT NULL,
  net_requirement DECIMAL(18,6) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  source_snapshot JSON NOT NULL,
  confirmed_source_ids JSON NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_mrp_result_run (run_id),
  KEY idx_mfg_mrp_result_material (material_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Upgrade the Task 1 BOM stub when this script is re-run against an existing
-- MySQL 8.0 database. CREATE TABLE IF NOT EXISTS does not add new columns.
DROP PROCEDURE IF EXISTS phase2_add_mfg_bom_column;
DELIMITER //
CREATE PROCEDURE phase2_add_mfg_bom_column(
  IN column_name_input VARCHAR(64),
  IN column_definition TEXT
)
BEGIN
  DECLARE column_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO column_exists
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'mfg_bom'
    AND column_name = column_name_input;
  IF column_exists = 0 THEN
    SET @phase2_mfg_sql = CONCAT(
      'ALTER TABLE `mfg_bom` ADD COLUMN `', column_name_input, '` ', column_definition
    );
    PREPARE phase2_mfg_statement FROM @phase2_mfg_sql;
    EXECUTE phase2_mfg_statement;
    DEALLOCATE PREPARE phase2_mfg_statement;
  END IF;
END//
DELIMITER ;

CALL phase2_add_mfg_bom_column('effective_from', 'DATE NULL');
CALL phase2_add_mfg_bom_column('effective_to', 'DATE NULL');
CALL phase2_add_mfg_bom_column('source_type', 'VARCHAR(64) NULL');
CALL phase2_add_mfg_bom_column('source_id', 'CHAR(36) NULL');
CALL phase2_add_mfg_bom_column('created_by', 'CHAR(36) NULL');
CALL phase2_add_mfg_bom_column('updated_by', 'CHAR(36) NULL');

UPDATE mfg_bom
SET effective_from = DATE(created_at)
WHERE effective_from IS NULL;
ALTER TABLE `mfg_bom` MODIFY COLUMN `effective_from` DATE NOT NULL;
DROP PROCEDURE IF EXISTS phase2_add_mfg_bom_column;

CREATE TABLE IF NOT EXISTS mfg_routing (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_routing_material (org_id, material_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_routing_operation (
  id CHAR(36) PRIMARY KEY,
  routing_id CHAR(36) NOT NULL,
  operation_name VARCHAR(128) NOT NULL,
  line_no INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_routing_operation_routing (routing_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_work_order (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  material_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  bom_id CHAR(36) NOT NULL,
  plan_date DATE NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  reported_good_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  reported_scrap_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  completed_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  bom_snapshot JSON NOT NULL,
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  created_by CHAR(36) NULL,
  updated_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_work_order_doc_no (org_id, doc_no),
  KEY idx_mfg_work_order_material (org_id, material_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_work_order_material (
  id CHAR(36) PRIMARY KEY,
  work_order_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  required_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  issued_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  returned_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  line_no INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_work_order_material_order (work_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_material_issue (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  work_order_id CHAR(36) NULL,
  subcontract_order_id CHAR(36) NULL,
  warehouse_id CHAR(36) NOT NULL,
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_material_issue_order (work_order_id),
  KEY idx_mfg_material_issue_org (org_id),
  UNIQUE KEY uk_mfg_material_issue_subcontract_order (subcontract_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_material_issue_item (
  id CHAR(36) PRIMARY KEY,
  issue_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  returned_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  unit_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
  line_no INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_material_issue_item_issue (issue_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_material_return (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  work_order_id CHAR(36) NOT NULL,
  issue_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_material_return_order (work_order_id),
  KEY idx_mfg_material_return_issue (issue_id),
  KEY idx_mfg_material_return_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_material_return_item (
  id CHAR(36) PRIMARY KEY,
  return_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  unit_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
  line_no INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_material_return_item_return (return_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_work_report (
  id CHAR(36) PRIMARY KEY,
  work_order_id CHAR(36) NOT NULL,
  good_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  scrap_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  hours DECIMAL(18,6) NOT NULL DEFAULT 0,
  report_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_work_report_order (work_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_subcontract_order (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  supplier_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  plan_date DATE NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  received_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  processing_fee DECIMAL(18,2) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  created_by CHAR(36) NULL,
  updated_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_subcontract_order_doc_no (org_id, doc_no),
  KEY idx_mfg_subcontract_order_supplier (org_id, supplier_id),
  KEY idx_mfg_subcontract_order_material (org_id, material_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_subcontract_receipt (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  subcontract_order_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  good_quantity DECIMAL(18,6) NOT NULL,
  unit_cost DECIMAL(18,6) NOT NULL,
  processing_fee_amount DECIMAL(18,2) NOT NULL,
  operation_key VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'completed',
  source_type VARCHAR(64) NOT NULL,
  source_id CHAR(36) NOT NULL,
  created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_subcontract_receipt_doc_no (org_id, doc_no),
  UNIQUE KEY uk_mfg_subcontract_receipt_operation (org_id, subcontract_order_id, operation_key),
  KEY idx_mfg_subcontract_receipt_order (subcontract_order_id),
  KEY idx_mfg_subcontract_receipt_source (org_id, source_type, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Upgrade the Task 1 work-order stub and any partial Task 3 schema when this
-- script is re-run. CREATE TABLE IF NOT EXISTS does not add columns.
DROP PROCEDURE IF EXISTS phase2_add_task3_column;
DELIMITER //
CREATE PROCEDURE phase2_add_task3_column(
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
    SET @phase2_task3_sql = CONCAT(
      'ALTER TABLE `', table_name_input, '` ADD COLUMN `', column_name_input, '` ', column_definition
    );
    PREPARE phase2_task3_statement FROM @phase2_task3_sql;
    EXECUTE phase2_task3_statement;
    DEALLOCATE PREPARE phase2_task3_statement;
  END IF;
END//
DELIMITER ;

DROP PROCEDURE IF EXISTS phase2_rename_task3_column;
DELIMITER //
CREATE PROCEDURE phase2_rename_task3_column(
  IN table_name_input VARCHAR(64),
  IN old_column_name_input VARCHAR(64),
  IN new_column_name_input VARCHAR(64),
  IN new_column_definition TEXT
)
BEGIN
  DECLARE old_column_exists INT DEFAULT 0;
  DECLARE new_column_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO old_column_exists
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = table_name_input
    AND column_name = old_column_name_input;
  SELECT COUNT(*) INTO new_column_exists
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = table_name_input
    AND column_name = new_column_name_input;
  IF old_column_exists = 1 AND new_column_exists = 0 THEN
    SET @phase2_task3_sql = CONCAT(
      'ALTER TABLE `', table_name_input, '` CHANGE COLUMN `', old_column_name_input,
      '` `', new_column_name_input, '` ', new_column_definition
    );
    PREPARE phase2_task3_statement FROM @phase2_task3_sql;
    EXECUTE phase2_task3_statement;
    DEALLOCATE PREPARE phase2_task3_statement;
  END IF;
END//
DELIMITER ;

CALL phase2_add_task3_column('mfg_work_order', 'warehouse_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_work_order', 'bom_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_work_order', 'plan_date', 'DATE NOT NULL DEFAULT ''1970-01-01''');
CALL phase2_add_task3_column('mfg_work_order', 'reported_good_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_order', 'reported_scrap_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_order', 'completed_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_order', 'bom_snapshot', 'JSON NULL');
CALL phase2_add_task3_column('mfg_work_order', 'source_type', 'VARCHAR(64) NULL');
CALL phase2_add_task3_column('mfg_work_order', 'source_id', 'CHAR(36) NULL');
CALL phase2_add_task3_column('mfg_work_order', 'created_by', 'CHAR(36) NULL');
CALL phase2_add_task3_column('mfg_work_order', 'updated_by', 'CHAR(36) NULL');

CALL phase2_add_task3_column('mfg_work_order_material', 'returned_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_order_material', 'line_no', 'INT NOT NULL DEFAULT 1');

CALL phase2_add_task3_column('mfg_material_issue', 'org_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_issue', 'work_order_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_issue', 'warehouse_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_issue', 'created_by', 'CHAR(36) NULL');
CALL phase2_add_task3_column('mfg_material_issue', 'is_deleted', 'TINYINT(1) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_issue', 'created_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_issue', 'updated_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_issue', 'version', 'INT NOT NULL DEFAULT 1');
CALL phase2_add_task3_column('mfg_material_issue_item', 'issue_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_issue_item', 'material_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_issue_item', 'quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_issue_item', 'returned_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_issue_item', 'unit_cost', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_issue_item', 'line_no', 'INT NOT NULL DEFAULT 1');
CALL phase2_add_task3_column('mfg_material_issue_item', 'is_deleted', 'TINYINT(1) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_issue_item', 'created_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_issue_item', 'updated_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_issue_item', 'version', 'INT NOT NULL DEFAULT 1');
CALL phase2_add_task3_column('mfg_material_return', 'org_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_return', 'work_order_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_return', 'issue_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_return', 'warehouse_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_return', 'created_by', 'CHAR(36) NULL');
CALL phase2_add_task3_column('mfg_material_return', 'is_deleted', 'TINYINT(1) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_return', 'created_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_return', 'updated_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_return', 'version', 'INT NOT NULL DEFAULT 1');
CALL phase2_add_task3_column('mfg_material_return_item', 'return_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_return_item', 'material_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task3_column('mfg_material_return_item', 'quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_return_item', 'unit_cost', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_return_item', 'line_no', 'INT NOT NULL DEFAULT 1');
CALL phase2_add_task3_column('mfg_material_return_item', 'is_deleted', 'TINYINT(1) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_material_return_item', 'created_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_return_item', 'updated_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_material_return_item', 'version', 'INT NOT NULL DEFAULT 1');

CALL phase2_rename_task3_column('mfg_work_report', 'reported_quantity', 'good_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_report', 'good_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_report', 'scrap_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_report', 'hours', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_report', 'report_time', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_work_report', 'created_by', 'CHAR(36) NULL');

UPDATE mfg_work_order
SET bom_snapshot = JSON_OBJECT()
WHERE bom_snapshot IS NULL;
ALTER TABLE `mfg_work_order` MODIFY COLUMN `bom_snapshot` JSON NOT NULL;
DROP PROCEDURE IF EXISTS phase2_add_task3_column;
DROP PROCEDURE IF EXISTS phase2_rename_task3_column;

-- Upgrade Task 4 subcontract fields safely when this script is re-run against
-- an existing Phase 2 database. The prior material issue table only accepted
-- work-order issues, so its work_order_id must become optional.
DROP PROCEDURE IF EXISTS phase2_add_task4_column;
DELIMITER //
CREATE PROCEDURE phase2_add_task4_column(
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
    SET @phase2_task4_sql = CONCAT(
      'ALTER TABLE `', table_name_input, '` ADD COLUMN `', column_name_input, '` ', column_definition
    );
    PREPARE phase2_task4_statement FROM @phase2_task4_sql;
    EXECUTE phase2_task4_statement;
    DEALLOCATE PREPARE phase2_task4_statement;
  END IF;
END//
DELIMITER ;

DROP PROCEDURE IF EXISTS phase2_add_task4_index;
DELIMITER //
CREATE PROCEDURE phase2_add_task4_index(
  IN table_name_input VARCHAR(64),
  IN index_name_input VARCHAR(64),
  IN index_definition TEXT
)
BEGIN
  DECLARE index_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO index_exists
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = table_name_input
    AND index_name = index_name_input;
  IF index_exists = 0 THEN
    SET @phase2_task4_index_sql = CONCAT(
      'ALTER TABLE `', table_name_input, '` ADD ', index_definition
    );
    PREPARE phase2_task4_index_statement FROM @phase2_task4_index_sql;
    EXECUTE phase2_task4_index_statement;
    DEALLOCATE PREPARE phase2_task4_index_statement;
  END IF;
END//
DELIMITER ;

CALL phase2_add_task4_column('mfg_material_issue', 'subcontract_order_id', 'CHAR(36) NULL');
CALL phase2_add_task4_column('mfg_material_issue', 'source_type', 'VARCHAR(64) NULL');
CALL phase2_add_task4_column('mfg_material_issue', 'source_id', 'CHAR(36) NULL');
ALTER TABLE `mfg_material_issue` MODIFY COLUMN `work_order_id` CHAR(36) NULL;
CALL phase2_add_task4_column('mfg_subcontract_order', 'received_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task4_column('mfg_subcontract_order', 'processing_fee', 'DECIMAL(18,2) NOT NULL DEFAULT 0');
CALL phase2_add_task4_column('mfg_subcontract_order', 'source_type', 'VARCHAR(64) NULL');
CALL phase2_add_task4_column('mfg_subcontract_order', 'source_id', 'CHAR(36) NULL');
CALL phase2_add_task4_column('mfg_subcontract_order', 'created_by', 'CHAR(36) NULL');
CALL phase2_add_task4_column('mfg_subcontract_order', 'updated_by', 'CHAR(36) NULL');
CALL phase2_add_task4_column('mfg_subcontract_receipt', 'processing_fee_amount', 'DECIMAL(18,2) NOT NULL DEFAULT 0');
CALL phase2_add_task4_column('mfg_subcontract_receipt', 'operation_key', 'VARCHAR(64) NULL');
CALL phase2_add_task4_column('mfg_subcontract_receipt', 'source_type', 'VARCHAR(64) NOT NULL DEFAULT ''''');
CALL phase2_add_task4_column('mfg_subcontract_receipt', 'source_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task4_column('mfg_subcontract_receipt', 'created_by', 'CHAR(36) NULL');
UPDATE mfg_subcontract_receipt
SET operation_key = id
WHERE operation_key IS NULL OR operation_key = '';
ALTER TABLE `mfg_subcontract_receipt` MODIFY COLUMN `operation_key` VARCHAR(64) NOT NULL;
CALL phase2_add_task4_index('mfg_material_issue', 'uk_mfg_material_issue_subcontract_order', 'UNIQUE KEY uk_mfg_material_issue_subcontract_order (subcontract_order_id)');
CALL phase2_add_task4_index('mfg_subcontract_receipt', 'uk_mfg_subcontract_receipt_operation', 'UNIQUE KEY uk_mfg_subcontract_receipt_operation (org_id, subcontract_order_id, operation_key)');
DROP PROCEDURE IF EXISTS phase2_add_task4_column;
DROP PROCEDURE IF EXISTS phase2_add_task4_index;

CREATE TABLE IF NOT EXISTS inv_zone (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_inv_zone_code (warehouse_id, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_location (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  zone_id CHAR(36) NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_inv_location_code (warehouse_id, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_batch (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  batch_no VARCHAR(64) NOT NULL,
  production_date DATE NULL,
  expiry_date DATE NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_inv_batch_material_no (org_id, material_id, batch_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_cost_layer (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  location_id CHAR(36) NOT NULL,
  batch_id CHAR(36) NULL,
  inbound_transaction_id CHAR(36) NOT NULL,
  source_type VARCHAR(64) NOT NULL,
  source_id CHAR(36) NOT NULL,
  original_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  remaining_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  unit_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_inv_cost_layer_material (org_id, material_id, warehouse_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_cost_layer_consumption (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  outbound_transaction_id CHAR(36) NOT NULL,
  cost_layer_id CHAR(36) NOT NULL,
  source_type VARCHAR(64) NOT NULL,
  source_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  unit_cost DECIMAL(18,6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY idx_inv_layer_consumption_outbound (outbound_transaction_id),
  KEY idx_inv_layer_consumption_layer (cost_layer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_slow_moving_rule (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NULL,
  material_id CHAR(36) NULL,
  threshold_days INT NOT NULL DEFAULT 90,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_inv_slow_moving_rule_scope (org_id, warehouse_id, material_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_warehouse_access (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  user_id CHAR(36) NOT NULL,
  access_level VARCHAR(32) NOT NULL DEFAULT 'view',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_inv_warehouse_access_user (warehouse_id, user_id),
  KEY idx_inv_warehouse_access_org_user (org_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inv_scan_record (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  scan_id VARCHAR(128) NOT NULL,
  action VARCHAR(32) NOT NULL,
  document_id CHAR(36) NOT NULL,
  response_json JSON NOT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_inv_scan_record_org_scan (org_id, scan_id),
  KEY idx_inv_scan_record_document (org_id, document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Upgrade Task 5 advanced inventory fields safely when this script is re-run
-- against a Phase 2 foundation database that already has the placeholder tables.
DROP PROCEDURE IF EXISTS phase2_add_task5_column;
DELIMITER //
CREATE PROCEDURE phase2_add_task5_column(
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
    SET @phase2_task5_sql = CONCAT(
      'ALTER TABLE `', table_name_input, '` ADD COLUMN `', column_name_input, '` ', column_definition
    );
    PREPARE phase2_task5_statement FROM @phase2_task5_sql;
    EXECUTE phase2_task5_statement;
    DEALLOCATE PREPARE phase2_task5_statement;
  END IF;
END//
DELIMITER ;

DROP PROCEDURE IF EXISTS phase2_add_task5_index;
DELIMITER //
CREATE PROCEDURE phase2_add_task5_index(
  IN table_name_input VARCHAR(64),
  IN index_name_input VARCHAR(64),
  IN index_definition TEXT
)
BEGIN
  DECLARE index_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO index_exists
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = table_name_input
    AND index_name = index_name_input;
  IF index_exists = 0 THEN
    SET @phase2_task5_index_sql = CONCAT('ALTER TABLE `', table_name_input, '` ADD ', index_definition);
    PREPARE phase2_task5_index_statement FROM @phase2_task5_index_sql;
    EXECUTE phase2_task5_index_statement;
    DEALLOCATE PREPARE phase2_task5_index_statement;
  END IF;
END//
DELIMITER ;

CALL phase2_add_task5_column('inv_stock_transaction', 'location_id', 'CHAR(36) NULL');
CALL phase2_add_task5_column('inv_stock_transaction', 'batch_id', 'CHAR(36) NULL');
CALL phase2_add_task5_column('inv_stock_transaction', 'consumed_layer_ids', 'JSON NULL');
CALL phase2_add_task5_column('inv_location', 'status', 'VARCHAR(32) NOT NULL DEFAULT ''active''');
CALL phase2_add_task5_column('inv_batch', 'status', 'VARCHAR(32) NOT NULL DEFAULT ''active''');
CALL phase2_add_task5_column('inv_cost_layer', 'location_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task5_column('inv_cost_layer', 'batch_id', 'CHAR(36) NULL');
CALL phase2_add_task5_column('inv_cost_layer', 'inbound_transaction_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task5_column('inv_cost_layer', 'original_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task5_index('inv_cost_layer', 'idx_inv_cost_layer_fifo', 'KEY idx_inv_cost_layer_fifo (org_id, warehouse_id, location_id, material_id, created_at)');
CALL phase2_add_task5_index('inv_stock_transaction', 'idx_inv_transaction_location_batch', 'KEY idx_inv_transaction_location_batch (warehouse_id, location_id, batch_id)');
DROP PROCEDURE IF EXISTS phase2_add_task5_column;
DROP PROCEDURE IF EXISTS phase2_add_task5_index;

CREATE TABLE IF NOT EXISTS cost_period_close (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  period VARCHAR(16) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'open',
  closed_at DATETIME(6) NULL,
  closed_by CHAR(36) NULL,
  reopened_at DATETIME(6) NULL,
  reopened_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_cost_period_close (org_id, period)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cost_allocation (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, allocation_date DATE NOT NULL, period VARCHAR(16) NOT NULL,
  amount DECIMAL(18,2) NOT NULL, basis VARCHAR(16) NOT NULL, source_type VARCHAR(64) NOT NULL, source_id CHAR(36) NOT NULL DEFAULT '',
  idempotency_key VARCHAR(128) NULL, status VARCHAR(32) NOT NULL DEFAULT 'draft', items_json JSON NOT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_cost_allocation_idempotency (org_id, idempotency_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS cost_project_entry (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, project_id CHAR(36) NOT NULL, period VARCHAR(16) NOT NULL, entry_date DATE NOT NULL,
  line_no INT NOT NULL, category VARCHAR(32) NOT NULL, source_type VARCHAR(64) NOT NULL, source_id CHAR(36) NOT NULL, allocation_id CHAR(36) NULL, amount DECIMAL(18,2) NOT NULL,
  KEY idx_cost_project_period (org_id, project_id, period)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS sys_api_client (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, client_key VARCHAR(64) NOT NULL, secret_hash VARCHAR(128) NOT NULL, scopes JSON NOT NULL, status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_sys_api_client_key (client_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cost_allocation_rule (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  rule_key VARCHAR(64) NOT NULL,
  rule_name VARCHAR(128) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_cost_allocation_rule_key (org_id, rule_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cost_allocation (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  allocation_date DATE NOT NULL,
  period VARCHAR(16) NOT NULL,
  amount DECIMAL(18,2) NOT NULL,
  basis VARCHAR(32) NOT NULL,
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  category VARCHAR(64) NOT NULL DEFAULT 'expense',
  idempotency_key VARCHAR(128) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  created_by CHAR(36) NULL,
  posted_at DATETIME(6) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_cost_allocation_idempotency (org_id, idempotency_key),
  KEY idx_cost_allocation_period (org_id, period, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cost_allocation_item (
  id CHAR(36) PRIMARY KEY,
  allocation_id CHAR(36) NOT NULL,
  line_no INT NOT NULL,
  project_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NULL,
  amount DECIMAL(18,2) NULL,
  hours DECIMAL(18,6) NULL,
  basis_value DECIMAL(18,6) NOT NULL,
  allocated_amount DECIMAL(18,2) NULL,
  source_snapshot JSON NULL,
  UNIQUE KEY uk_cost_allocation_item_line (allocation_id, line_no),
  KEY idx_cost_allocation_item_project (project_id),
  CONSTRAINT fk_cost_allocation_item_allocation FOREIGN KEY (allocation_id) REFERENCES cost_allocation(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cost_project (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  project_code VARCHAR(64) NOT NULL,
  project_name VARCHAR(128) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_cost_project_code (org_id, project_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cost_project_entry (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  project_id CHAR(36) NOT NULL,
  period VARCHAR(16) NOT NULL,
  entry_date DATE NOT NULL,
  line_no INT NOT NULL,
  category VARCHAR(64) NOT NULL,
  source_type VARCHAR(64) NOT NULL,
  source_id CHAR(36) NOT NULL,
  amount DECIMAL(18,2) NOT NULL,
  allocation_id CHAR(36) NULL,
  description VARCHAR(500) NULL,
  source_snapshot JSON NULL,
  KEY idx_cost_project_entry_project_period (org_id, project_id, period),
  KEY idx_cost_project_entry_source (source_type, source_id),
  CONSTRAINT fk_cost_project_entry_allocation FOREIGN KEY (allocation_id) REFERENCES cost_allocation(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP PROCEDURE IF EXISTS phase2_add_task7_column;
DELIMITER //
CREATE PROCEDURE phase2_add_task7_column(
  IN table_name_input VARCHAR(64),
  IN column_name_input VARCHAR(64),
  IN column_definition_input VARCHAR(255)
)
BEGIN
  DECLARE column_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO column_exists
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = table_name_input
    AND column_name = column_name_input;
  IF column_exists = 0 THEN
    SET @phase2_task7_column_sql = CONCAT('ALTER TABLE `', table_name_input, '` ADD COLUMN `', column_name_input, '` ', column_definition_input);
    PREPARE phase2_task7_column_statement FROM @phase2_task7_column_sql;
    EXECUTE phase2_task7_column_statement;
    DEALLOCATE PREPARE phase2_task7_column_statement;
  END IF;
END//
DELIMITER ;

CALL phase2_add_task7_column('cost_period_close', 'closed_by', 'CHAR(36) NULL');
CALL phase2_add_task7_column('cost_period_close', 'reopened_at', 'DATETIME(6) NULL');
CALL phase2_add_task7_column('cost_period_close', 'reopened_by', 'CHAR(36) NULL');
DROP PROCEDURE IF EXISTS phase2_add_task7_column;

CREATE TABLE IF NOT EXISTS crm_lead (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  lead_no VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  phone VARCHAR(64) NULL,
  email VARCHAR(128) NULL,
  source VARCHAR(64) NULL,
  owner_id CHAR(36) NOT NULL,
  department_id CHAR(36) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'new',
  customer_id CHAR(36) NULL, contact_id CHAR(36) NULL, opportunity_id CHAR(36) NULL,
  lost_reason VARCHAR(500) NULL,
  converted_customer_id CHAR(36) NULL,
  converted_contact_id CHAR(36) NULL,
  converted_opportunity_id CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_crm_lead_org_no (org_id, lead_no),
  KEY idx_crm_lead_owner_status (org_id, owner_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS crm_opportunity (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  opportunity_no VARCHAR(64) NOT NULL,
  lead_id CHAR(36) NULL,
  customer_id CHAR(36) NULL,
  contact_id CHAR(36) NULL,
  name VARCHAR(128) NOT NULL,
  owner_id CHAR(36) NOT NULL,
  department_id CHAR(36) NULL,
  stage VARCHAR(32) NOT NULL DEFAULT 'new',
  loss_reason VARCHAR(255) NULL,
  estimated_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  expected_close_date DATE NULL,
  source VARCHAR(64) NULL,
  lost_reason VARCHAR(500) NULL,
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_crm_opportunity_org_no (org_id, opportunity_no),
  KEY idx_crm_opportunity_owner_stage (org_id, owner_id, stage),
  KEY idx_crm_opportunity_lead (org_id, lead_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS crm_contact (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  customer_id CHAR(36) NULL,
  lead_id CHAR(36) NULL,
  name VARCHAR(128) NOT NULL,
  phone VARCHAR(64) NULL,
  email VARCHAR(128) NULL,
  title VARCHAR(128) NULL,
  owner_id CHAR(36) NULL,
  department_id CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_crm_contact_owner (org_id, owner_id),
  KEY idx_crm_contact_phone (org_id, phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS crm_follow_up (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  opportunity_id CHAR(36) NOT NULL,
  lead_id CHAR(36) NULL,
  owner_id CHAR(36) NOT NULL,
  department_id CHAR(36) NULL,
  followed_at DATETIME(6) NOT NULL,
  method VARCHAR(32) NOT NULL,
  content TEXT NOT NULL,
  next_step VARCHAR(500) NULL,
  next_follow_up_at DATETIME(6) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_crm_follow_up_opportunity_time (org_id, opportunity_id, followed_at),
  KEY idx_crm_follow_up_owner (org_id, owner_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS crm_activity (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  activity_type VARCHAR(64) NOT NULL,
  subject VARCHAR(255) NOT NULL,
  owner_id CHAR(36) NULL,
  occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_crm_activity_owner_time (owner_id, occurred_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS qa_inspection (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NULL,
  inspection_type VARCHAR(32) NOT NULL,
  source_type VARCHAR(64) NOT NULL,
  source_id CHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  result VARCHAR(32) NULL,
  results_json JSON NOT NULL,
  disposition VARCHAR(32) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_qa_inspection_doc_no (org_id, doc_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS qa_plan (
  id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, name VARCHAR(128) NOT NULL, items_json JSON NOT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), version INT NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS qa_inspection_item (
  id CHAR(36) PRIMARY KEY,
  inspection_id CHAR(36) NOT NULL,
  item_name VARCHAR(128) NOT NULL,
  result VARCHAR(32) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_qa_inspection_item_inspection (inspection_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS qa_nonconformance (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  inspection_id CHAR(36) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'open',
  description VARCHAR(500) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_qa_nonconformance_inspection (inspection_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS hr_employee (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  employee_no VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  department_id CHAR(36) NULL,
  user_id CHAR(36) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  base_salary DECIMAL(18,2) NOT NULL DEFAULT 0, allowance DECIMAL(18,2) NOT NULL DEFAULT 0,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_hr_employee_no (org_id, employee_no)
  , KEY idx_hr_employee_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS hr_attendance (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  employee_id CHAR(36) NOT NULL,
  attendance_date DATE NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'present',
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_hr_attendance_employee_date (employee_id, attendance_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS hr_leave_request (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  employee_id CHAR(36) NOT NULL,
  leave_type VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_hr_leave_request_employee_status (employee_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS hr_payroll_run (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  period VARCHAR(16) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  total_amount DECIMAL(18,2) NOT NULL DEFAULT 0, items_json JSON NOT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_hr_payroll_run_period (org_id, period)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ext_ai_alert_rule (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  rule_key VARCHAR(128) NOT NULL,
  rule_name VARCHAR(128) NOT NULL,
  metric_key VARCHAR(128) NOT NULL,
  condition_json JSON NOT NULL,
  enabled TINYINT(1) NOT NULL DEFAULT 0,
  UNIQUE KEY uk_ext_ai_alert_rule_key (org_id, rule_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO sys_org (id, code, name)
VALUES ('00000000-0000-0000-0000-000000000001', 'DEFAULT', '默认组织')
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO sys_department (id, org_id, code, name)
VALUES ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'ROOT', '总部')
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO sys_role (id, org_id, code, name, data_scope_type)
VALUES ('00000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', 'SUPER_ADMIN', '超级管理员', 'all')
ON DUPLICATE KEY UPDATE name = VALUES(name), data_scope_type = VALUES(data_scope_type);

INSERT INTO sys_user (id, org_id, department_id, username, display_name, password_hash, is_superuser)
VALUES (
  '00000000-0000-0000-0000-000000000004',
  '00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000002',
  'admin',
  '超级管理员',
  '$2b$12$RckZCeAnrsylXY0Jfny5HeBIFOY3QYe0Mqu0U4NKqPDBvGXPxpT2K',
  1
)
ON DUPLICATE KEY UPDATE display_name = VALUES(display_name), password_hash = VALUES(password_hash), is_superuser = 1;

INSERT INTO sys_menu (id, code, name, path, component, menu_type, sort_order)
VALUES
('10000000-0000-0000-0000-000000000001', 'dashboard:view', '经营看板', '/dashboard', 'Dashboard', 'menu', 1),
('10000000-0000-0000-0000-000000000002', 'master:view', '基础资料', '/master-data', 'MasterData', 'menu', 10),
('10000000-0000-0000-0000-000000000003', 'sales:view', '销售管理', '/sales', 'Sales', 'menu', 20),
('10000000-0000-0000-0000-000000000004', 'purchase:view', '采购管理', '/purchase', 'Purchase', 'menu', 30),
('10000000-0000-0000-0000-000000000005', 'inventory:view', '库存管理', '/inventory', 'Inventory', 'menu', 40),
('10000000-0000-0000-0000-000000000006', 'finance:view', '财务管理', '/finance', 'Finance', 'menu', 50),
('10000000-0000-0000-0000-000000000007', 'system:view', '系统运维', '/system', 'System', 'menu', 90),
('10000000-0000-0000-0000-000000000008', 'production:view', '生产管理', '/production', 'Production', 'menu', 35),
('10000000-0000-0000-0000-000000000009', 'cost:view', '成本管理', '/cost', 'Cost', 'menu', 45),
('10000000-0000-0000-0000-000000000010', 'crm:view', 'CRM 管理', '/crm', 'Crm', 'menu', 60),
('10000000-0000-0000-0000-000000000011', 'quality:view', '质量管理', '/quality', 'Quality', 'menu', 55),
('10000000-0000-0000-0000-000000000012', 'hr:view', '人事管理', '/hr', 'Hr', 'menu', 65),
('10000000-0000-0000-0000-000000000014', 'config:view', '系统配置', '/settings', 'Settings', 'menu', 95)
ON DUPLICATE KEY UPDATE name = VALUES(name), path = VALUES(path), component = VALUES(component);

INSERT INTO sys_menu (id, parent_id, code, name, path, component, menu_type, sort_order)
SELECT '10000000-0000-0000-0000-000000000013', id, 'page:hr:employees:view', '员工管理', '/hr/employees', 'EmployeeList', 'menu', 1
FROM sys_menu WHERE code = 'hr:view'
ON DUPLICATE KEY UPDATE name = VALUES(name), path = VALUES(path), component = VALUES(component);

INSERT INTO sys_permission (id, menu_id, code, name, permission_type)
SELECT '20000000-0000-0000-0000-000000000001', id, 'system:user:manage', '用户管理', 'button'
FROM sys_menu WHERE code = 'system:view'
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO sys_permission (id, menu_id, code, name, permission_type)
SELECT '20000000-0000-0000-0000-000000000002', id, 'production:manage', '生产计划管理', 'button'
FROM sys_menu WHERE code = 'production:view'
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO sys_permission (id, menu_id, code, name, permission_type)
SELECT '20000000-0000-0000-0000-000000000003', id, 'hr:employee:manage', '员工信息管理', 'button'
FROM sys_menu WHERE code = 'page:hr:employees:view'
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO sys_role_menu (role_id, menu_id)
SELECT '00000000-0000-0000-0000-000000000003', id FROM sys_menu
ON DUPLICATE KEY UPDATE role_id = VALUES(role_id);

INSERT INTO sys_role_permission (role_id, permission_id)
SELECT '00000000-0000-0000-0000-000000000003', id FROM sys_permission
ON DUPLICATE KEY UPDATE role_id = VALUES(role_id);

INSERT INTO sys_user_role (user_id, role_id)
VALUES ('00000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000003')
ON DUPLICATE KEY UPDATE user_id = VALUES(user_id);

INSERT INTO cfg_number_rule (id, org_id, rule_key, prefix, date_format, sequence_length, reset_cycle)
VALUES
('30000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'sales_order', 'SO', '%Y%m%d', 4, 'day'),
('30000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'purchase_order', 'PO', '%Y%m%d', 4, 'day'),
('30000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', 'sales_delivery', 'SD', '%Y%m%d', 4, 'day'),
('30000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000001', 'purchase_receipt', 'PR', '%Y%m%d', 4, 'day'),
('30000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000001', 'fin_voucher', 'FV', '%Y%m%d', 4, 'day')
,
('30000000-0000-0000-0000-000000000006', '00000000-0000-0000-0000-000000000001', 'sales_quote', 'QT', '%Y%m%d', 4, 'day'),
('30000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000001', 'purchase_request', 'PRQ', '%Y%m%d', 4, 'day'),
('30000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000001', 'purchase_return', 'PTR', '%Y%m%d', 4, 'day'),
('30000000-0000-0000-0000-000000000009', '00000000-0000-0000-0000-000000000001', 'sales_return', 'STR', '%Y%m%d', 4, 'day'),
('30000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'mfg_work_order', 'WO', '%Y%m%d', 4, 'day'),
('30000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000001', 'qa_inspection', 'QI', '%Y%m%d', 4, 'day'),
('30000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000001', 'mfg_mps', 'MPS', '%Y%m%d', 4, 'day'),
('30000000-0000-0000-0000-000000000013', '00000000-0000-0000-0000-000000000001', 'mfg_mrp', 'MRP', '%Y%m%d', 4, 'day'),
('30000000-0000-0000-0000-000000000014', '00000000-0000-0000-0000-000000000001', 'mfg_subcontract_order', 'SC', '%Y%m%d', 4, 'day'),
('30000000-0000-0000-0000-000000000015', '00000000-0000-0000-0000-000000000001', 'mfg_subcontract_receipt', 'SR', '%Y%m%d', 4, 'day'),
('30000000-0000-0000-0000-000000000016', '00000000-0000-0000-0000-000000000001', 'crm_lead', 'LD', '%Y%m%d', 4, 'day'),
('30000000-0000-0000-0000-000000000017', '00000000-0000-0000-0000-000000000001', 'crm_opportunity', 'OP', '%Y%m%d', 4, 'day')
ON DUPLICATE KEY UPDATE prefix = VALUES(prefix), date_format = VALUES(date_format), sequence_length = VALUES(sequence_length);

INSERT INTO cfg_global_parameter (id, org_id, parameter_key, parameter_value, value_type, description)
VALUES
('50000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'inventory.costing_method', 'weighted_average', 'string', '库存成本计价方法'),
('50000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'mfg.allow_over_issue', 'false', 'boolean', '生产领料是否允许超发'),
('50000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', 'qa.inspection_required', 'true', 'boolean', '质量检验是否必填')
ON DUPLICATE KEY UPDATE parameter_value = VALUES(parameter_value), value_type = VALUES(value_type), description = VALUES(description);

INSERT INTO ext_module_registry (id, module_key, module_name, phase, enabled)
VALUES
('40000000-0000-0000-0000-000000000001', 'production', '生产管理', 'phase2', 0),
('40000000-0000-0000-0000-000000000002', 'crm', 'CRM', 'phase2', 0),
('40000000-0000-0000-0000-000000000003', 'quality', '质量管理', 'phase2', 0),
('40000000-0000-0000-0000-000000000004', 'hr', '人事考勤薪资', 'phase2', 0),
('40000000-0000-0000-0000-000000000010', 'inventory_cost', '库存与成本', 'phase2', 0),
('40000000-0000-0000-0000-000000000011', 'platform', '平台能力', 'phase2', 0),
('40000000-0000-0000-0000-000000000005', 'group_org', '集团多组织', 'phase3', 0),
('40000000-0000-0000-0000-000000000006', 'bi', 'BI 报表框架', 'phase3', 0),
('40000000-0000-0000-0000-000000000007', 'ocr', 'OCR 发票识别', 'phase3', 0),
('40000000-0000-0000-0000-000000000008', 'ai_alert', 'AI 预警', 'phase3', 0),
('40000000-0000-0000-0000-000000000009', 'low_code', '低代码表单引擎', 'phase3', 0)
ON DUPLICATE KEY UPDATE module_name = VALUES(module_name), phase = VALUES(phase);

SET FOREIGN_KEY_CHECKS = 1;
