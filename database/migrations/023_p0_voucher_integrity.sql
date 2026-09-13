-- P0-02：禁止负数凭证分录；历史不平凭证由差异清单人工补录或冲销。
USE erp;
SET NAMES utf8mb4;

SET @sql = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE fin_voucher_entry ADD CONSTRAINT ck_fin_voucher_entry_debit_nonnegative CHECK (debit_amount >= 0)',
  'SELECT 1')
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'fin_voucher_entry'
    AND constraint_name = 'ck_fin_voucher_entry_debit_nonnegative');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE fin_voucher_entry ADD CONSTRAINT ck_fin_voucher_entry_credit_nonnegative CHECK (credit_amount >= 0)',
  'SELECT 1')
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'fin_voucher_entry'
    AND constraint_name = 'ck_fin_voucher_entry_credit_nonnegative');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 只读核查清单：此查询不修改历史账务，结果应导出后逐笔处理。
SELECT v.id, v.voucher_no, v.source_type, v.source_id, v.status,
       v.total_debit AS header_debit, v.total_credit AS header_credit,
       COALESCE(SUM(e.debit_amount), 0) AS entry_debit,
       COALESCE(SUM(e.credit_amount), 0) AS entry_credit
FROM fin_voucher v
LEFT JOIN fin_voucher_entry e ON e.voucher_id = v.id
GROUP BY v.id, v.voucher_no, v.source_type, v.source_id, v.status, v.total_debit, v.total_credit
HAVING entry_debit <= 0
    OR entry_debit <> entry_credit
    OR entry_debit <> header_debit
    OR entry_credit <> header_credit;

INSERT INTO sys_schema_migration (version, description)
VALUES ('023_p0_voucher_integrity', 'P0-02 凭证分录非负约束与历史差异清单')
ON DUPLICATE KEY UPDATE description = VALUES(description);
