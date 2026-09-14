-- P1-02：统一会计期间状态，修复期间边界，并确保当前自然月可入账。
USE erp;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS fin_fiscal_period_p102_backup LIKE fin_fiscal_period;
INSERT IGNORE INTO fin_fiscal_period_p102_backup
SELECT *
FROM fin_fiscal_period
WHERE status NOT IN ('open', 'closed')
   OR (status = 'open' AND closed_at IS NOT NULL)
   OR (status = 'closed' AND closed_at IS NULL)
   OR start_date <> STR_TO_DATE(CONCAT(period, '-01'), '%Y-%m-%d')
   OR end_date <> LAST_DAY(STR_TO_DATE(CONCAT(period, '-01'), '%Y-%m-%d'));

-- Period boundaries are derived from the YYYY-MM key, never from seed-row timestamps.
UPDATE fin_fiscal_period
SET start_date = STR_TO_DATE(CONCAT(period, '-01'), '%Y-%m-%d'),
    end_date = LAST_DAY(STR_TO_DATE(CONCAT(period, '-01'), '%Y-%m-%d'))
WHERE period REGEXP '^[0-9]{4}-(0[1-9]|1[0-2])$';

-- Preserve closed intent when a legacy active row has a close timestamp; otherwise it is open.
UPDATE fin_fiscal_period
SET status = CASE
      WHEN period = DATE_FORMAT(CURDATE(), '%Y-%m') THEN 'open'
      WHEN closed_at IS NOT NULL THEN 'closed'
      ELSE 'open'
    END,
    closed_at = CASE
      WHEN period = DATE_FORMAT(CURDATE(), '%Y-%m') THEN NULL
      WHEN closed_at IS NOT NULL THEN closed_at
      ELSE NULL
    END;

INSERT INTO fin_fiscal_period (id, org_id, period, start_date, end_date, status)
SELECT UUID(), o.id, DATE_FORMAT(CURDATE(), '%Y-%m'),
       STR_TO_DATE(DATE_FORMAT(CURDATE(), '%Y-%m-01'), '%Y-%m-%d'),
       LAST_DAY(CURDATE()), 'open'
FROM sys_org o
WHERE NOT EXISTS (
  SELECT 1 FROM fin_fiscal_period p
  WHERE p.org_id = o.id AND p.period = DATE_FORMAT(CURDATE(), '%Y-%m')
);

SET @sql = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE fin_fiscal_period ADD CONSTRAINT ck_fin_fiscal_period_status CHECK (status IN (''open'', ''closed''))',
  'SELECT 1')
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'fin_fiscal_period'
    AND constraint_name = 'ck_fin_fiscal_period_status');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

INSERT INTO sys_schema_migration (version, description)
VALUES ('025_p1_fiscal_period_integrity', 'P1-02 会计期间状态、边界与当前期间修复')
ON DUPLICATE KEY UPDATE description = VALUES(description);
