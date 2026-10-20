-- 为 P1/P2 扩展模块补齐统一单据编号规则。
-- 这些模块此前在缺少规则时使用 UUID 编号；规则只新增，不覆盖组织已有配置。
USE erp;
SET NAMES utf8mb4;

INSERT IGNORE INTO cfg_number_rule
  (id, org_id, rule_key, prefix, date_format, sequence_length, reset_cycle,
   current_date_key, current_sequence)
SELECT UUID(), o.id, r.rule_key, r.prefix, r.date_format, 4, 'day',
       DATE_FORMAT(CURRENT_DATE, r.date_format), 0
FROM sys_org AS o
CROSS JOIN (
  SELECT 'plm_change_request' AS rule_key, 'PLMCR' AS prefix, '%Y%m%d' AS date_format UNION ALL
  SELECT 'plm_change_order', 'ECN', '%Y%m%d' UNION ALL
  SELECT 'srm_rfq', 'RFQ', '%Y%m%d' UNION ALL
  SELECT 'eam_work_order', 'EAMWO', '%Y%m%d' UNION ALL
  SELECT 'svc_contract', 'SVCC', '%Y%m%d' UNION ALL
  SELECT 'svc_case', 'SVCS', '%Y%m%d' UNION ALL
  SELECT 'tax_invoice', 'TAX', '%Y%m%d' UNION ALL
  SELECT 'intercompany', 'IC', '%Y%m%d'
) AS r
WHERE o.is_deleted = 0;

INSERT INTO sys_schema_migration (version, description)
VALUES ('028_extended_document_number_rules', '为扩展模块补齐统一单据编号规则')
ON DUPLICATE KEY UPDATE description = VALUES(description);
