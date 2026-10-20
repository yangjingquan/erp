-- 为所有组织补齐缺失的基础单据编号规则，并延续当前周期已有序号。
-- INSERT IGNORE + (org_id, rule_key) 唯一键保证可重复执行且不覆盖已有规则。
USE erp;
SET NAMES utf8mb4;

INSERT IGNORE INTO cfg_number_rule
  (id, org_id, rule_key, prefix, date_format, sequence_length, reset_cycle,
   current_date_key, current_sequence)
SELECT UUID(), o.id, r.rule_key, r.prefix, r.date_format, 4, r.reset_cycle,
       DATE_FORMAT(CURRENT_DATE, r.date_format), COALESCE(s.current_sequence, 0)
FROM sys_org AS o
CROSS JOIN (
  SELECT 'sales_order' AS rule_key, 'SO' AS prefix, '%Y%m%d' AS date_format, 'day' AS reset_cycle UNION ALL
  SELECT 'purchase_order', 'PO', '%Y%m%d', 'day' UNION ALL
  SELECT 'sales_delivery', 'SD', '%Y%m%d', 'day' UNION ALL
  SELECT 'purchase_receipt', 'PR', '%Y%m%d', 'day' UNION ALL
  SELECT 'fin_voucher', 'FV', '%Y%m%d', 'day' UNION ALL
  SELECT 'sales_quote', 'QT', '%Y%m%d', 'day' UNION ALL
  SELECT 'purchase_request', 'PRQ', '%Y%m', 'month' UNION ALL
  SELECT 'purchase_return', 'PTR', '%Y%m%d', 'day' UNION ALL
  SELECT 'sales_return', 'STR', '%Y%m%d', 'day' UNION ALL
  SELECT 'mfg_work_order', 'WO', '%Y%m', 'month' UNION ALL
  SELECT 'qa_inspection', 'QI', '%Y%m%d', 'day' UNION ALL
  SELECT 'mfg_mps', 'MPS', '%Y%m%d', 'day' UNION ALL
  SELECT 'mfg_mrp', 'MRP', '%Y%m%d', 'day' UNION ALL
  SELECT 'mfg_subcontract_order', 'SC', '%Y%m%d', 'day' UNION ALL
  SELECT 'mfg_subcontract_receipt', 'SR', '%Y%m%d', 'day' UNION ALL
  SELECT 'crm_lead', 'LD', '%Y%m%d', 'day' UNION ALL
  SELECT 'crm_opportunity', 'OP', '%Y%m%d', 'day'
) AS r
LEFT JOIN (
  SELECT org_id, 'sales_order' AS rule_key,
         MAX(CAST(RIGHT(doc_no, 4) AS UNSIGNED)) AS current_sequence
  FROM sales_order
  WHERE doc_no REGEXP CONCAT('^SO', DATE_FORMAT(CURRENT_DATE, '%Y%m%d'), '[0-9]{4}$')
  GROUP BY org_id
  UNION ALL
  SELECT org_id, 'purchase_order', MAX(CAST(RIGHT(doc_no, 4) AS UNSIGNED))
  FROM purchase_order
  WHERE doc_no REGEXP CONCAT('^PO', DATE_FORMAT(CURRENT_DATE, '%Y%m%d'), '[0-9]{4}$')
  GROUP BY org_id
  UNION ALL
  SELECT org_id, 'sales_delivery', MAX(CAST(RIGHT(doc_no, 4) AS UNSIGNED))
  FROM sales_delivery
  WHERE doc_no REGEXP CONCAT('^SD', DATE_FORMAT(CURRENT_DATE, '%Y%m%d'), '[0-9]{4}$')
  GROUP BY org_id
  UNION ALL
  SELECT org_id, 'purchase_receipt', MAX(CAST(RIGHT(doc_no, 4) AS UNSIGNED))
  FROM purchase_receipt
  WHERE doc_no REGEXP CONCAT('^PR', DATE_FORMAT(CURRENT_DATE, '%Y%m%d'), '[0-9]{4}$')
  GROUP BY org_id
  UNION ALL
  SELECT org_id, 'fin_voucher', MAX(CAST(RIGHT(voucher_no, 4) AS UNSIGNED))
  FROM fin_voucher
  WHERE voucher_no REGEXP CONCAT('^FV', DATE_FORMAT(CURRENT_DATE, '%Y%m%d'), '[0-9]{4}$')
  GROUP BY org_id
  UNION ALL
  SELECT org_id, 'sales_quote', MAX(CAST(RIGHT(doc_no, 4) AS UNSIGNED))
  FROM sales_quote
  WHERE doc_no REGEXP CONCAT('^QT', DATE_FORMAT(CURRENT_DATE, '%Y%m%d'), '[0-9]{4}$')
  GROUP BY org_id
  UNION ALL
  SELECT org_id, 'purchase_request', MAX(CAST(RIGHT(doc_no, 4) AS UNSIGNED))
  FROM purchase_request
  WHERE doc_no REGEXP CONCAT('^PRQ', DATE_FORMAT(CURRENT_DATE, '%Y%m'), '[0-9]{4}$')
  GROUP BY org_id
  UNION ALL
  SELECT org_id, 'purchase_return', MAX(CAST(RIGHT(doc_no, 4) AS UNSIGNED))
  FROM purchase_return
  WHERE doc_no REGEXP CONCAT('^PTR', DATE_FORMAT(CURRENT_DATE, '%Y%m%d'), '[0-9]{4}$')
  GROUP BY org_id
  UNION ALL
  SELECT org_id, 'sales_return', MAX(CAST(RIGHT(doc_no, 4) AS UNSIGNED))
  FROM sales_return
  WHERE doc_no REGEXP CONCAT('^STR', DATE_FORMAT(CURRENT_DATE, '%Y%m%d'), '[0-9]{4}$')
  GROUP BY org_id
  UNION ALL
  SELECT org_id, 'mfg_work_order', MAX(CAST(RIGHT(doc_no, 4) AS UNSIGNED))
  FROM mfg_work_order
  WHERE doc_no REGEXP CONCAT('^WO', DATE_FORMAT(CURRENT_DATE, '%Y%m'), '[0-9]{4}$')
  GROUP BY org_id
  UNION ALL
  SELECT org_id, 'mfg_mps', MAX(CAST(RIGHT(doc_no, 4) AS UNSIGNED))
  FROM mfg_mps
  WHERE doc_no REGEXP CONCAT('^MPS', DATE_FORMAT(CURRENT_DATE, '%Y%m%d'), '[0-9]{4}$')
  GROUP BY org_id
  UNION ALL
  SELECT org_id, 'mfg_mrp', MAX(CAST(RIGHT(doc_no, 4) AS UNSIGNED))
  FROM mfg_mrp_run
  WHERE doc_no REGEXP CONCAT('^MRP', DATE_FORMAT(CURRENT_DATE, '%Y%m%d'), '[0-9]{4}$')
  GROUP BY org_id
  UNION ALL
  SELECT org_id, 'mfg_subcontract_order', MAX(CAST(RIGHT(doc_no, 4) AS UNSIGNED))
  FROM mfg_subcontract_order
  WHERE doc_no REGEXP CONCAT('^SC', DATE_FORMAT(CURRENT_DATE, '%Y%m%d'), '[0-9]{4}$')
  GROUP BY org_id
  UNION ALL
  SELECT org_id, 'mfg_subcontract_receipt', MAX(CAST(RIGHT(doc_no, 4) AS UNSIGNED))
  FROM mfg_subcontract_receipt
  WHERE doc_no REGEXP CONCAT('^SR', DATE_FORMAT(CURRENT_DATE, '%Y%m%d'), '[0-9]{4}$')
  GROUP BY org_id
  UNION ALL
  SELECT org_id, 'crm_lead', MAX(CAST(RIGHT(lead_no, 4) AS UNSIGNED))
  FROM crm_lead
  WHERE lead_no REGEXP CONCAT('^LD', DATE_FORMAT(CURRENT_DATE, '%Y%m%d'), '[0-9]{4}$')
  GROUP BY org_id
  UNION ALL
  SELECT org_id, 'crm_opportunity', MAX(CAST(RIGHT(opportunity_no, 4) AS UNSIGNED))
  FROM crm_opportunity
  WHERE opportunity_no REGEXP CONCAT('^OP', DATE_FORMAT(CURRENT_DATE, '%Y%m%d'), '[0-9]{4}$')
  GROUP BY org_id
) AS s ON s.org_id = o.id AND s.rule_key = r.rule_key
WHERE o.is_deleted = 0;

INSERT INTO sys_schema_migration (version, description)
VALUES ('027_all_org_number_rules', '为所有组织补齐基础单据编号规则并延续当前周期序号')
ON DUPLICATE KEY UPDATE description = VALUES(description);
