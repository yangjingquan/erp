-- EAM asset lifecycle, maintenance execution and after-sales service closure.
USE erp;

DROP PROCEDURE IF EXISTS phase7_add_eam_service_closed_loop;
DELIMITER //
CREATE PROCEDURE phase7_add_eam_service_closed_loop()
BEGIN
  DECLARE column_exists INT DEFAULT 0;

  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'eam_asset' AND column_name = 'retired_at';
  IF column_exists = 0 THEN ALTER TABLE eam_asset ADD COLUMN retired_at DATETIME(6) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'eam_asset' AND column_name = 'retirement_reason';
  IF column_exists = 0 THEN ALTER TABLE eam_asset ADD COLUMN retirement_reason VARCHAR(500) NULL; END IF;

  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'eam_maintenance_plan' AND column_name = 'last_work_order_id';
  IF column_exists = 0 THEN ALTER TABLE eam_maintenance_plan ADD COLUMN last_work_order_id CHAR(36) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'eam_maintenance_plan' AND column_name = 'last_completed_at';
  IF column_exists = 0 THEN ALTER TABLE eam_maintenance_plan ADD COLUMN last_completed_at DATETIME(6) NULL; END IF;

  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'eam_work_order' AND column_name = 'maintenance_plan_id';
  IF column_exists = 0 THEN ALTER TABLE eam_work_order ADD COLUMN maintenance_plan_id CHAR(36) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'eam_work_order' AND column_name = 'actual_hours';
  IF column_exists = 0 THEN ALTER TABLE eam_work_order ADD COLUMN actual_hours DECIMAL(12,2) NOT NULL DEFAULT 0; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'eam_work_order' AND column_name = 'parts_cost';
  IF column_exists = 0 THEN ALTER TABLE eam_work_order ADD COLUMN parts_cost DECIMAL(18,2) NOT NULL DEFAULT 0; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'eam_work_order' AND column_name = 'labor_cost';
  IF column_exists = 0 THEN ALTER TABLE eam_work_order ADD COLUMN labor_cost DECIMAL(18,2) NOT NULL DEFAULT 0; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'eam_work_order' AND column_name = 'assigned_at';
  IF column_exists = 0 THEN ALTER TABLE eam_work_order ADD COLUMN assigned_at DATETIME(6) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'eam_work_order' AND column_name = 'started_at';
  IF column_exists = 0 THEN ALTER TABLE eam_work_order ADD COLUMN started_at DATETIME(6) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'eam_work_order' AND column_name = 'resolved_at';
  IF column_exists = 0 THEN ALTER TABLE eam_work_order ADD COLUMN resolved_at DATETIME(6) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'eam_work_order' AND column_name = 'closed_at';
  IF column_exists = 0 THEN ALTER TABLE eam_work_order ADD COLUMN closed_at DATETIME(6) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'eam_work_order' AND column_name = 'closed_by';
  IF column_exists = 0 THEN ALTER TABLE eam_work_order ADD COLUMN closed_by CHAR(36) NULL; END IF;

  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'svc_case' AND column_name = 'sla_hours';
  IF column_exists = 0 THEN ALTER TABLE svc_case ADD COLUMN sla_hours INT NULL DEFAULT 48; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'svc_case' AND column_name = 'first_response_at';
  IF column_exists = 0 THEN ALTER TABLE svc_case ADD COLUMN first_response_at DATETIME(6) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'svc_case' AND column_name = 'resolved_at';
  IF column_exists = 0 THEN ALTER TABLE svc_case ADD COLUMN resolved_at DATETIME(6) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'svc_case' AND column_name = 'closed_at';
  IF column_exists = 0 THEN ALTER TABLE svc_case ADD COLUMN closed_at DATETIME(6) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'svc_case' AND column_name = 'customer_feedback';
  IF column_exists = 0 THEN ALTER TABLE svc_case ADD COLUMN customer_feedback VARCHAR(1000) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'svc_case' AND column_name = 'satisfaction_score';
  IF column_exists = 0 THEN ALTER TABLE svc_case ADD COLUMN satisfaction_score INT NULL; END IF;
  UPDATE svc_case SET sla_hours = 48 WHERE sla_hours IS NULL;

  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'svc_visit' AND column_name = 'outcome';
  IF column_exists = 0 THEN ALTER TABLE svc_visit ADD COLUMN outcome VARCHAR(1000) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'svc_visit' AND column_name = 'completed_at';
  IF column_exists = 0 THEN ALTER TABLE svc_visit ADD COLUMN completed_at DATETIME(6) NULL; END IF;
  SELECT COUNT(*) INTO column_exists FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'svc_visit' AND column_name = 'feedback_score';
  IF column_exists = 0 THEN ALTER TABLE svc_visit ADD COLUMN feedback_score INT NULL; END IF;
END//
DELIMITER ;
CALL phase7_add_eam_service_closed_loop();
DROP PROCEDURE IF EXISTS phase7_add_eam_service_closed_loop;

INSERT INTO sys_schema_migration (version, description)
VALUES ('020_eam_service_closed_loop', '资产生命周期、维修派工结案与售后服务回访闭环')
ON DUPLICATE KEY UPDATE description = VALUES(description);
