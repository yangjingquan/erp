-- Customer quality claim source traceability, workflow evidence and finance link.
USE erp;

DROP PROCEDURE IF EXISTS phase6_add_customer_claim_closed_loop;
DELIMITER //
CREATE PROCEDURE phase6_add_customer_claim_closed_loop()
BEGIN
  DECLARE column_exists INT DEFAULT 0;

  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_customer_claim' AND column_name = 'approved_amount';
  IF column_exists = 0 THEN ALTER TABLE qa_customer_claim ADD COLUMN approved_amount DECIMAL(18,2) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_customer_claim' AND column_name = 'owner_id';
  IF column_exists = 0 THEN ALTER TABLE qa_customer_claim ADD COLUMN owner_id CHAR(36) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_customer_claim' AND column_name = 'due_date';
  IF column_exists = 0 THEN ALTER TABLE qa_customer_claim ADD COLUMN due_date DATE NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_customer_claim' AND column_name = 'review_evidence';
  IF column_exists = 0 THEN ALTER TABLE qa_customer_claim ADD COLUMN review_evidence VARCHAR(1000) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_customer_claim' AND column_name = 'review_comment';
  IF column_exists = 0 THEN ALTER TABLE qa_customer_claim ADD COLUMN review_comment VARCHAR(500) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_customer_claim' AND column_name = 'reviewed_by';
  IF column_exists = 0 THEN ALTER TABLE qa_customer_claim ADD COLUMN reviewed_by CHAR(36) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_customer_claim' AND column_name = 'reviewed_at';
  IF column_exists = 0 THEN ALTER TABLE qa_customer_claim ADD COLUMN reviewed_at DATETIME(6) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_customer_claim' AND column_name = 'closure_evidence';
  IF column_exists = 0 THEN ALTER TABLE qa_customer_claim ADD COLUMN closure_evidence VARCHAR(1000) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_customer_claim' AND column_name = 'nonconformance_id';
  IF column_exists = 0 THEN ALTER TABLE qa_customer_claim ADD COLUMN nonconformance_id CHAR(36) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_customer_claim' AND column_name = 'financial_expense_id';
  IF column_exists = 0 THEN ALTER TABLE qa_customer_claim ADD COLUMN financial_expense_id CHAR(36) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'qa_customer_claim' AND column_name = 'closed_by';
  IF column_exists = 0 THEN ALTER TABLE qa_customer_claim ADD COLUMN closed_by CHAR(36) NULL; END IF;

  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'fin_expense' AND column_name = 'source_type';
  IF column_exists = 0 THEN ALTER TABLE fin_expense ADD COLUMN source_type VARCHAR(64) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'fin_expense' AND column_name = 'source_id';
  IF column_exists = 0 THEN ALTER TABLE fin_expense ADD COLUMN source_id CHAR(36) NULL; END IF;
END//
DELIMITER ;
CALL phase6_add_customer_claim_closed_loop();
DROP PROCEDURE IF EXISTS phase6_add_customer_claim_closed_loop;

INSERT INTO sys_schema_migration (version, description)
VALUES ('019_customer_claim_closed_loop', '客户质量索赔来源、审核、CAPA 与财务费用闭环')
ON DUPLICATE KEY UPDATE description = VALUES(description);
