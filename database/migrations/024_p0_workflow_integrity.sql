-- P0-03：备份并清理孤儿任务，再为任务/实例建立外键约束。
USE erp;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS wf_task_p003_orphan_backup LIKE wf_task;
INSERT IGNORE INTO wf_task_p003_orphan_backup
SELECT t.*
FROM wf_task t
LEFT JOIN wf_instance i ON i.id = t.instance_id
WHERE i.id IS NULL;

DELETE t
FROM wf_task t
LEFT JOIN wf_instance i ON i.id = t.instance_id
WHERE i.id IS NULL;

SET @sql = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE wf_instance ADD CONSTRAINT fk_wf_instance_definition FOREIGN KEY (definition_id) REFERENCES wf_definition(id)',
  'SELECT 1')
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'wf_instance'
    AND constraint_name = 'fk_wf_instance_definition');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE wf_task ADD CONSTRAINT fk_wf_task_instance FOREIGN KEY (instance_id) REFERENCES wf_instance(id)',
  'SELECT 1')
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'wf_task'
    AND constraint_name = 'fk_wf_task_instance');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

INSERT INTO sys_schema_migration (version, description)
VALUES ('024_p0_workflow_integrity', 'P0-03 孤儿任务快照清理与流程外键约束')
ON DUPLICATE KEY UPDATE description = VALUES(description);
