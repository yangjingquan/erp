-- Versioned migration: convert existing UTC wall-clock values to Asia/Shanghai.
-- The migration marker prevents a repeated eight-hour shift.
USE erp;
SET time_zone = '+08:00';

DELIMITER $$
DROP PROCEDURE IF EXISTS migrate_utc_datetimes_to_local$$
CREATE PROCEDURE migrate_utc_datetimes_to_local()
BEGIN
  DECLARE finished INT DEFAULT 0;
  DECLARE target_table VARCHAR(64);
  DECLARE column_updates LONGTEXT;
  DECLARE migration_applied INT DEFAULT 0;
  DECLARE datetime_tables CURSOR FOR
    SELECT DISTINCT table_name
    FROM information_schema.columns
    WHERE table_schema = 'erp'
      AND data_type = 'datetime'
      AND table_name <> 'sys_schema_migration'
    ORDER BY table_name;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET finished = 1;

  SELECT COUNT(*) INTO migration_applied
  FROM sys_schema_migration
  WHERE version = '004_local_timezone';

  IF migration_applied = 0 THEN
    SET SESSION group_concat_max_len = 1048576;
    OPEN datetime_tables;
    conversion_loop: LOOP
      FETCH datetime_tables INTO target_table;
      IF finished = 1 THEN
        LEAVE conversion_loop;
      END IF;

      SELECT GROUP_CONCAT(
        CONCAT('`', column_name, '` = DATE_ADD(`', column_name, '`, INTERVAL 8 HOUR)')
        ORDER BY ordinal_position SEPARATOR ', '
      ) INTO column_updates
      FROM information_schema.columns
      WHERE table_schema = 'erp'
        AND table_name = target_table
        AND data_type = 'datetime';

      SET @conversion_sql = CONCAT(
        'UPDATE `', target_table, '` SET ', column_updates
      );
      PREPARE conversion_statement FROM @conversion_sql;
      EXECUTE conversion_statement;
      DEALLOCATE PREPARE conversion_statement;
    END LOOP;
    CLOSE datetime_tables;

    INSERT INTO sys_schema_migration (version, description)
    VALUES ('004_local_timezone', '历史 UTC 时间统一转换为 Asia/Shanghai')
    ON DUPLICATE KEY UPDATE description = VALUES(description);
  END IF;
END$$
CALL migrate_utc_datetimes_to_local()$$
DROP PROCEDURE migrate_utc_datetimes_to_local$$
DELIMITER ;
