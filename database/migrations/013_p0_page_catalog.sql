-- P0：新增功能页面权限目录，确保普通用户可以访问新增页面
USE erp;
SET NAMES utf8mb4;

INSERT INTO sys_menu (id, parent_id, code, name, path, component, menu_type, sort_order)
SELECT '10000000-0000-0000-0000-000000000023', id, 'page:inventory:wms-tasks:view', 'WMS 作业中心', '/inventory/wms-tasks', 'WmsTaskCenter', 'menu', 8
FROM sys_menu WHERE code = 'inventory:view'
ON DUPLICATE KEY UPDATE name = VALUES(name), path = VALUES(path), component = VALUES(component), sort_order = VALUES(sort_order);

INSERT INTO sys_menu (id, parent_id, code, name, path, component, menu_type, sort_order)
SELECT '10000000-0000-0000-0000-000000000024', id, 'page:production:execution:view', '生产执行控制台', '/production/execution', 'ExecutionControl', 'menu', 5
FROM sys_menu WHERE code = 'production:view'
ON DUPLICATE KEY UPDATE name = VALUES(name), path = VALUES(path), component = VALUES(component), sort_order = VALUES(sort_order);

INSERT INTO sys_menu (id, parent_id, code, name, path, component, menu_type, sort_order)
SELECT '10000000-0000-0000-0000-000000000025', id, 'page:finance:controls:view', '财务控制中心', '/finance/controls', 'FinanceControls', 'menu', 8
FROM sys_menu WHERE code = 'finance:view'
ON DUPLICATE KEY UPDATE name = VALUES(name), path = VALUES(path), component = VALUES(component), sort_order = VALUES(sort_order);

INSERT INTO sys_menu (id, parent_id, code, name, path, component, menu_type, sort_order)
SELECT '10000000-0000-0000-0000-000000000026', id, 'page:production:planning:view', '供需计划控制塔', '/production/planning', 'PlanningControlTower', 'menu', 4
FROM sys_menu WHERE code = 'production:view'
ON DUPLICATE KEY UPDATE name = VALUES(name), path = VALUES(path), component = VALUES(component), sort_order = VALUES(sort_order);

INSERT INTO sys_schema_migration (version, description)
VALUES ('013_p0_page_catalog', 'P0 新增页面权限目录')
ON DUPLICATE KEY UPDATE description = VALUES(description);
