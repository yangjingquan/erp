-- 为所有组织补齐缺失的生产工单编号规则，并延续当月已有工单序号。
-- INSERT IGNORE + (org_id, rule_key) 唯一键保证可重复执行且不覆盖已有规则。
USE erp;
SET NAMES utf8mb4;

INSERT IGNORE INTO cfg_number_rule
  (id, org_id, rule_key, prefix, date_format, sequence_length, reset_cycle,
   current_date_key, current_sequence)
SELECT UUID(), o.id, 'mfg_work_order', 'WO', '%Y%m', 4, 'month',
       DATE_FORMAT(CURRENT_DATE, '%Y%m'),
       COALESCE(MAX(CAST(RIGHT(w.doc_no, 4) AS UNSIGNED)), 0)
FROM sys_org AS o
LEFT JOIN mfg_work_order AS w
  ON w.org_id = o.id
 AND w.doc_no REGEXP CONCAT('^WO', DATE_FORMAT(CURRENT_DATE, '%Y%m'), '[0-9]{4}$')
WHERE o.is_deleted = 0
GROUP BY o.id;

INSERT INTO sys_schema_migration (version, description)
VALUES ('026_organization_number_rules', '为所有组织补齐生产工单编号规则并延续当月序号')
ON DUPLICATE KEY UPDATE description = VALUES(description);
