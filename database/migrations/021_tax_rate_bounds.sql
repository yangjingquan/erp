-- Deactivate legacy tax rates outside the valid percentage range.
-- Values are retained for audit and the migration is safe to re-run.
USE erp;

START TRANSACTION;
ALTER TABLE md_tax_rate
ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'active' AFTER rate;
UPDATE md_tax_rate
SET status = 'inactive', version = version + 1
WHERE is_deleted = 0
  AND (rate < 0 OR rate > 100)
  AND status <> 'inactive';
COMMIT;
