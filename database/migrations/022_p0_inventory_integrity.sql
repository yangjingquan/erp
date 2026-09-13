-- P0-01：按库存流水重算库存余额，并为 ATP 公式建立数据库约束。
USE erp;
SET NAMES utf8mb4;

-- 保留修复前快照，便于审计和回滚核对；不得直接覆盖为 quantity。
CREATE TABLE IF NOT EXISTS inv_stock_p001_backup LIKE inv_stock;
INSERT IGNORE INTO inv_stock_p001_backup
SELECT * FROM inv_stock;

-- quantity 以库存流水为准，locked_quantity 以未释放预留为准，available_quantity 为派生值。
UPDATE inv_stock s
LEFT JOIN (
  SELECT org_id, warehouse_id, material_id,
         SUM(CASE WHEN direction = 'in' THEN quantity ELSE -quantity END) AS quantity
  FROM inv_stock_transaction
  GROUP BY org_id, warehouse_id, material_id
) t ON t.org_id = s.org_id
   AND t.warehouse_id = s.warehouse_id
   AND t.material_id = s.material_id
LEFT JOIN (
  SELECT org_id, warehouse_id, material_id,
         SUM(quantity - released_quantity) AS locked_quantity
  FROM inv_reservation
  WHERE is_deleted = 0
    AND status IN ('reserved', 'active')
    AND quantity > released_quantity
  GROUP BY org_id, warehouse_id, material_id
) r ON r.org_id = s.org_id
   AND r.warehouse_id = s.warehouse_id
   AND r.material_id = s.material_id
SET s.quantity = COALESCE(t.quantity, 0),
    s.locked_quantity = COALESCE(r.locked_quantity, 0),
    s.available_quantity = COALESCE(t.quantity, 0) - COALESCE(r.locked_quantity, 0);

SET @sql = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE inv_stock ADD CONSTRAINT ck_inv_stock_locked_nonnegative CHECK (locked_quantity >= 0)',
  'SELECT 1')
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'inv_stock'
    AND constraint_name = 'ck_inv_stock_locked_nonnegative');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE inv_stock ADD CONSTRAINT ck_inv_stock_available_formula CHECK (available_quantity = quantity - locked_quantity)',
  'SELECT 1')
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'inv_stock'
    AND constraint_name = 'ck_inv_stock_available_formula');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

INSERT INTO sys_schema_migration (version, description)
VALUES ('022_p0_inventory_integrity', 'P0-01 库存流水重算、ATP 约束与修复前快照')
ON DUPLICATE KEY UPDATE description = VALUES(description);
