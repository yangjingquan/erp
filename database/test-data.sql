-- ERP phase-2 functional test fixtures. Safe to re-run; all business keys use TEST- prefixes.
USE erp;
SET FOREIGN_KEY_CHECKS = 0;
START TRANSACTION;

SET @org = '00000000-0000-0000-0000-000000000001';
SET @admin = '00000000-0000-0000-0000-000000000004';
SET @dept = '00000000-0000-0000-0000-000000000002';

INSERT INTO md_unit (id, org_id, code, name, precision_scale) VALUES
('11111111-1111-1111-1111-111111111101', @org, 'TEST-PCS', '测试件', 2)
ON DUPLICATE KEY UPDATE name=VALUES(name);
INSERT INTO md_tax_rate (id, org_id, code, name, rate) VALUES
('11111111-1111-1111-1111-111111111102', @org, 'TEST-VAT13', '测试增值税13%', 13)
ON DUPLICATE KEY UPDATE name=VALUES(name), rate=VALUES(rate);
INSERT INTO md_customer (id, org_id, code, name, short_name, owner_id, contact_name, contact_phone, address, credit_limit, status) VALUES
('11111111-1111-1111-1111-111111111103', @org, 'TEST-CUST-01', '测试客户一', '测试客户', @admin, '测试联系人', '13800000001', '测试地址一', 100000, 'active'),
('11111111-1111-1111-1111-111111111104', @org, 'TEST-CUST-02', '测试客户二', '客户二', @admin, '联系人二', '13800000002', '测试地址二', 50000, 'active')
ON DUPLICATE KEY UPDATE name=VALUES(name), status='active';
INSERT INTO md_supplier (id, org_id, code, name, short_name, owner_id, contact_name, contact_phone, address, credit_days, status) VALUES
('11111111-1111-1111-1111-111111111105', @org, 'TEST-SUP-01', '测试供应商一', '测试供应商', @admin, '供应商联系人', '13900000001', '供应商地址', 30, 'active')
ON DUPLICATE KEY UPDATE name=VALUES(name), status='active';
INSERT INTO md_material (id, org_id, code, name, category, unit_id, tax_rate_id, material_type, standard_cost, sale_price, purchase_price, min_stock, max_stock, specification, status) VALUES
('11111111-1111-1111-1111-111111111106', @org, 'TEST-MAT-001', '测试成品', '测试产品', '11111111-1111-1111-1111-111111111101', '11111111-1111-1111-1111-111111111102', 'goods', 50, 88, 52, 10, 500, '成品规格A', 'active'),
('11111111-1111-1111-1111-111111111107', @org, 'TEST-MAT-002', '测试原料', '测试原料', '11111111-1111-1111-1111-111111111101', '11111111-1111-1111-1111-111111111102', 'goods', 20, 35, 22, 20, 1000, '原料规格B', 'active')
ON DUPLICATE KEY UPDATE name=VALUES(name), status='active';
INSERT INTO md_warehouse (id, org_id, code, name, manager_id, address, status) VALUES
('11111111-1111-1111-1111-111111111108', @org, 'TEST-WH-01', '测试主仓', @admin, '测试仓库地址', 'active'),
('11111111-1111-1111-1111-111111111109', @org, 'TEST-WH-02', '测试成品仓', @admin, '测试二号仓', 'active')
ON DUPLICATE KEY UPDATE name=VALUES(name), status='active';

INSERT INTO inv_warehouse_access (id, org_id, warehouse_id, user_id, access_level) VALUES
('11111111-1111-1111-1111-111111111110', @org, '11111111-1111-1111-1111-111111111108', @admin, 'manage'),
('11111111-1111-1111-1111-111111111111', @org, '11111111-1111-1111-1111-111111111109', @admin, 'manage')
ON DUPLICATE KEY UPDATE access_level='manage';
INSERT INTO inv_zone (id, org_id, warehouse_id, code, name) VALUES
('11111111-1111-1111-1111-111111111112', @org, '11111111-1111-1111-1111-111111111108', 'TEST-ZONE-A', '测试A区')
ON DUPLICATE KEY UPDATE name=VALUES(name);
INSERT INTO inv_location (id, org_id, warehouse_id, zone_id, code, name, status) VALUES
('11111111-1111-1111-1111-111111111113', @org, '11111111-1111-1111-1111-111111111108', '11111111-1111-1111-1111-111111111112', 'TEST-A-01', '测试A区01库位', 'active')
ON DUPLICATE KEY UPDATE name=VALUES(name), status='active';
INSERT INTO inv_batch (id, org_id, material_id, batch_no, production_date, expiry_date, status) VALUES
('11111111-1111-1111-1111-111111111114', @org, '11111111-1111-1111-1111-111111111107', 'TEST-LOT-001', CURRENT_DATE, DATE_ADD(CURRENT_DATE, INTERVAL 365 DAY), 'active')
ON DUPLICATE KEY UPDATE status='active';
INSERT INTO inv_stock (id, org_id, warehouse_id, material_id, quantity, locked_quantity, available_quantity, average_cost) VALUES
('11111111-1111-1111-1111-111111111115', @org, '11111111-1111-1111-1111-111111111108', '11111111-1111-1111-1111-111111111107', 120, 0, 120, 20),
('11111111-1111-1111-1111-111111111116', @org, '11111111-1111-1111-1111-111111111109', '11111111-1111-1111-1111-111111111106', 40, 0, 40, 50)
ON DUPLICATE KEY UPDATE quantity=VALUES(quantity), available_quantity=VALUES(available_quantity), average_cost=VALUES(average_cost);

INSERT INTO sales_order (id, org_id, doc_no, customer_id, owner_id, department_id, status, order_date, expected_date, total_amount, receivable_amount, remark, created_by, updated_by) VALUES
('11111111-1111-1111-1111-111111111201', @org, 'TEST-SO-001', '11111111-1111-1111-1111-111111111103', @admin, @dept, 'draft', CURRENT_DATE, DATE_ADD(CURRENT_DATE, INTERVAL 7 DAY), 880, 880, '销售订单测试数据', @admin, @admin)
ON DUPLICATE KEY UPDATE total_amount=VALUES(total_amount), status='draft';
INSERT INTO sales_order_item (id, order_id, material_id, warehouse_id, quantity, unit_price, tax_rate, amount, line_no) VALUES
('11111111-1111-1111-1111-111111111202', '11111111-1111-1111-1111-111111111201', '11111111-1111-1111-1111-111111111106', '11111111-1111-1111-1111-111111111109', 10, 88, 13, 880, 1)
ON DUPLICATE KEY UPDATE quantity=VALUES(quantity), amount=VALUES(amount);
INSERT INTO purchase_order (id, org_id, doc_no, supplier_id, department_id, owner_id, status, order_date, expected_date, total_amount, payable_amount, created_by, updated_by) VALUES
('11111111-1111-1111-1111-111111111203', @org, 'TEST-PO-001', '11111111-1111-1111-1111-111111111105', @dept, @admin, 'draft', CURRENT_DATE, DATE_ADD(CURRENT_DATE, INTERVAL 5 DAY), 440, 440, @admin, @admin)
ON DUPLICATE KEY UPDATE total_amount=VALUES(total_amount), status='draft';
INSERT INTO purchase_order_item (id, order_id, material_id, warehouse_id, quantity, unit_price, tax_rate, amount, line_no) VALUES
('11111111-1111-1111-1111-111111111204', '11111111-1111-1111-1111-111111111203', '11111111-1111-1111-1111-111111111107', '11111111-1111-1111-1111-111111111108', 20, 22, 13, 440, 1)
ON DUPLICATE KEY UPDATE quantity=VALUES(quantity), amount=VALUES(amount);
INSERT INTO fin_expense (id, org_id, doc_no, applicant_id, department_id, amount, expense_date, expense_type, status, description, created_by) VALUES
('11111111-1111-1111-1111-111111111205', @org, 'TEST-EXP-001', @admin, @dept, 680, CURRENT_DATE, '办公费用', 'draft', '测试费用报销', @admin)
ON DUPLICATE KEY UPDATE amount=VALUES(amount), status='draft';

INSERT INTO mfg_bom (id, org_id, material_id, bom_version, status, effective_from, created_by, updated_by) VALUES
('11111111-1111-1111-1111-111111111301', @org, '11111111-1111-1111-1111-111111111106', 'TEST-1.0', 'approved', CURRENT_DATE, @admin, @admin)
ON DUPLICATE KEY UPDATE status='approved';
INSERT INTO mfg_bom_item (id, bom_id, material_id, quantity, line_no) VALUES
('11111111-1111-1111-1111-111111111302', '11111111-1111-1111-1111-111111111301', '11111111-1111-1111-1111-111111111107', 2, 1)
ON DUPLICATE KEY UPDATE quantity=VALUES(quantity);
INSERT INTO mfg_mps (id, org_id, doc_no, material_id, warehouse_id, plan_date, plan_quantity, status, created_by, updated_by) VALUES
('11111111-1111-1111-1111-111111111303', @org, 'TEST-MPS-001', '11111111-1111-1111-1111-111111111106', '11111111-1111-1111-1111-111111111109', DATE_ADD(CURRENT_DATE, INTERVAL 7 DAY), 30, 'approved', @admin, @admin)
ON DUPLICATE KEY UPDATE status='approved';
INSERT INTO mfg_mrp_run (id, org_id, doc_no, mps_id, bom_id, status, source_snapshot, created_by) VALUES
('11111111-1111-1111-1111-111111111304', @org, 'TEST-MRP-001', '11111111-1111-1111-1111-111111111303', '11111111-1111-1111-1111-111111111301', 'completed', JSON_OBJECT('test', true, 'source', 'TEST-MPS-001'), @admin)
ON DUPLICATE KEY UPDATE status='completed';
INSERT INTO mfg_work_order (id, org_id, doc_no, material_id, warehouse_id, bom_id, plan_date, quantity, status, bom_snapshot, source_type, source_id, created_by, updated_by) VALUES
('11111111-1111-1111-1111-111111111305', @org, 'TEST-WO-001', '11111111-1111-1111-1111-111111111106', '11111111-1111-1111-1111-111111111109', '11111111-1111-1111-1111-111111111301', DATE_ADD(CURRENT_DATE, INTERVAL 7 DAY), 30, 'released', JSON_ARRAY(JSON_OBJECT('material_id', '11111111-1111-1111-1111-111111111107', 'quantity', 60)), 'mrp_result', '11111111-1111-1111-1111-111111111304', @admin, @admin)
ON DUPLICATE KEY UPDATE status='released';
INSERT INTO mfg_work_order_material (id, work_order_id, material_id, required_quantity, line_no) VALUES
('11111111-1111-1111-1111-111111111306', '11111111-1111-1111-1111-111111111305', '11111111-1111-1111-1111-111111111107', 60, 1)
ON DUPLICATE KEY UPDATE required_quantity=VALUES(required_quantity);

INSERT INTO cost_project (id, org_id, project_code, project_name, status) VALUES
('11111111-1111-1111-1111-111111111401', @org, 'TEST-PROJ-01', '测试项目一', 'active')
ON DUPLICATE KEY UPDATE project_name=VALUES(project_name), status='active';
INSERT INTO cost_allocation (id, org_id, allocation_date, period, amount, basis, source_type, source_id, idempotency_key, status, items_json) VALUES
('11111111-1111-1111-1111-111111111402', @org, CURRENT_DATE, DATE_FORMAT(CURRENT_DATE, '%Y-%m'), 1000, 'quantity', 'TEST-EXPENSE', '11111111-1111-1111-1111-111111111205', 'TEST-ALLOC-001', 'draft', JSON_ARRAY(JSON_OBJECT('project_id', '11111111-1111-1111-1111-111111111401', 'quantity', '1')))
ON DUPLICATE KEY UPDATE amount=VALUES(amount), status='draft';

INSERT INTO crm_lead (id, org_id, lead_no, name, phone, email, source, owner_id, department_id, status) VALUES
('11111111-1111-1111-1111-111111111501', @org, 'TEST-LEAD-001', '测试线索客户', '13700000001', 'test@example.com', '官网', @admin, @dept, 'new')
ON DUPLICATE KEY UPDATE name=VALUES(name), status='new';
INSERT INTO crm_opportunity (id, org_id, opportunity_no, name, owner_id, department_id, stage, estimated_amount, source) VALUES
('11111111-1111-1111-1111-111111111502', @org, 'TEST-OPP-001', '测试商机', @admin, @dept, 'new', 8800, '官网')
ON DUPLICATE KEY UPDATE name=VALUES(name), stage='new';

INSERT INTO qa_plan (id, org_id, name, items_json) VALUES
('11111111-1111-1111-1111-111111111601', @org, '测试来料检验方案', JSON_ARRAY(JSON_OBJECT('item', '外观', 'required', true), JSON_OBJECT('item', '尺寸', 'min', 9, 'max', 11)))
ON DUPLICATE KEY UPDATE name=VALUES(name);
INSERT INTO qa_inspection (id, org_id, doc_no, source_type, source_id, status, result) VALUES
('11111111-1111-1111-1111-111111111602', @org, 'TEST-QA-001', 'purchase_order', '11111111-1111-1111-1111-111111111203', 'draft', NULL)
ON DUPLICATE KEY UPDATE status='draft', result=NULL;
INSERT INTO hr_employee (id, org_id, employee_no, name, department_id, status, base_salary, allowance) VALUES
('11111111-1111-1111-1111-111111111701', @org, 'TEST-EMP-001', '测试员工一', @dept, 'active', 8000, 500)
ON DUPLICATE KEY UPDATE name=VALUES(name), status='active';
INSERT INTO hr_attendance (id, org_id, employee_id, attendance_date, status) VALUES
('11111111-1111-1111-1111-111111111702', @org, '11111111-1111-1111-1111-111111111701', CURRENT_DATE, 'present')
ON DUPLICATE KEY UPDATE status='present';
INSERT INTO hr_payroll_run (id, org_id, period, status, total_amount, items_json) VALUES
('11111111-1111-1111-1111-111111111703', @org, DATE_FORMAT(CURRENT_DATE, '%Y-%m'), 'calculated', 8500, JSON_ARRAY(JSON_OBJECT('employee_id', '11111111-1111-1111-1111-111111111701', 'amount', '8500.00')))
ON DUPLICATE KEY UPDATE status='calculated', total_amount=VALUES(total_amount);

COMMIT;
SET FOREIGN_KEY_CHECKS = 1;
