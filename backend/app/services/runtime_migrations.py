from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


def ensure_employee_account_column(db: Session) -> None:
    """Add the employee-to-user link for databases created before employee accounts."""
    inspector = inspect(db.bind)
    if "hr_employee" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("hr_employee")}
    if "user_id" in columns:
        return
    db.execute(text("ALTER TABLE hr_employee ADD COLUMN user_id CHAR(36) NULL"))
    db.execute(text("CREATE INDEX idx_hr_employee_user_id ON hr_employee (user_id)"))
    db.commit()


def ensure_purchase_request_supplier_column(db: Session) -> None:
    """Add optional supplier linkage for purchase requests created before the field existed."""
    inspector = inspect(db.bind)
    if "purchase_request" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("purchase_request")}
    if "supplier_id" in columns:
        return
    db.execute(text("ALTER TABLE purchase_request ADD COLUMN supplier_id CHAR(36) NULL"))
    db.commit()


def ensure_api_client_schema(db: Session) -> None:
    """Bring the API client table up to the current ORM contract.

    Early versions of the schema created ``sys_api_client`` with legacy
    credential columns and without the common audit columns.  Since
    ``CREATE TABLE IF NOT EXISTS`` does not alter an existing table, those
    installations otherwise fail on both the list query and client creation.
    """
    if db.bind.dialect.name != "mysql":
        return
    inspector = inspect(db.bind)
    if "sys_api_client" not in inspector.get_table_names():
        return

    columns = {column["name"]: column for column in inspector.get_columns("sys_api_client")}
    statements: list[str] = []

    if "secret_hash" not in columns:
        statements.append("ALTER TABLE sys_api_client ADD COLUMN secret_hash VARCHAR(128) NULL")
    if "scopes" not in columns:
        statements.append("ALTER TABLE sys_api_client ADD COLUMN scopes JSON NULL")
    if "status" not in columns:
        statements.append(
            "ALTER TABLE sys_api_client ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'active'"
        )
    if "created_at" not in columns:
        statements.append(
            "ALTER TABLE sys_api_client ADD COLUMN created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)"
        )
    if "updated_at" not in columns:
        statements.append(
            "ALTER TABLE sys_api_client ADD COLUMN updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"
        )
    if "is_deleted" not in columns:
        statements.append(
            "ALTER TABLE sys_api_client ADD COLUMN is_deleted TINYINT(1) NOT NULL DEFAULT 0"
        )
    if "version" not in columns:
        statements.append(
            "ALTER TABLE sys_api_client ADD COLUMN version INT NOT NULL DEFAULT 1"
        )

    # The legacy table required fields that are not part of the current API
    # client contract.  Make them optional so current inserts do not need to
    # fabricate values for fields that the application no longer uses.
    if columns.get("client_name", {}).get("nullable") is False:
        statements.append(
            "ALTER TABLE sys_api_client MODIFY COLUMN client_name VARCHAR(128) NULL"
        )
    if columns.get("client_secret_hash", {}).get("nullable") is False:
        statements.append(
            "ALTER TABLE sys_api_client MODIFY COLUMN client_secret_hash VARCHAR(255) NULL"
        )

    for statement in statements:
        db.execute(text(statement))
    if statements:
        db.commit()


def ensure_quality_inspection_columns(db: Session) -> None:
    """Bring legacy quality inspection tables up to the current ORM contract."""
    if db.bind.dialect.name != "mysql":
        return
    inspector = inspect(db.bind)
    if "qa_inspection" not in inspector.get_table_names():
        return

    columns = {column["name"]: column for column in inspector.get_columns("qa_inspection")}
    changed = False
    if "inspection_type" not in columns:
        db.execute(
            text(
                "ALTER TABLE qa_inspection "
                "ADD COLUMN inspection_type VARCHAR(32) NOT NULL DEFAULT 'incoming' AFTER org_id"
            )
        )
        changed = True
    if "results_json" not in columns:
        db.execute(text("ALTER TABLE qa_inspection ADD COLUMN results_json JSON NULL AFTER result"))
        db.execute(text("UPDATE qa_inspection SET results_json = '[]' WHERE results_json IS NULL"))
        db.execute(text("ALTER TABLE qa_inspection MODIFY COLUMN results_json JSON NOT NULL"))
        changed = True
    elif columns["results_json"].get("nullable"):
        db.execute(text("UPDATE qa_inspection SET results_json = '[]' WHERE results_json IS NULL"))
        db.execute(text("ALTER TABLE qa_inspection MODIFY COLUMN results_json JSON NOT NULL"))
        changed = True
    if "disposition" not in columns:
        db.execute(text("ALTER TABLE qa_inspection ADD COLUMN disposition VARCHAR(32) NULL AFTER results_json"))
        changed = True
    if "plan_id" not in columns:
        db.execute(text("ALTER TABLE qa_inspection ADD COLUMN plan_id CHAR(36) NULL AFTER disposition"))
        changed = True
    if "sample_size" not in columns:
        db.execute(text("ALTER TABLE qa_inspection ADD COLUMN sample_size INT NULL AFTER plan_id"))
        changed = True
    # doc_no was part of the legacy table but is not mapped by the current ORM.
    # Making it nullable lets the current create_inspection flow insert safely.
    if columns.get("doc_no", {}).get("nullable") is False:
        db.execute(text("ALTER TABLE qa_inspection MODIFY COLUMN doc_no VARCHAR(64) NULL"))
        changed = True
    if changed:
        db.commit()


def ensure_p1_control_schema(db: Session) -> None:
    """Create P1 inventory and quality tables for databases upgraded without migration 009."""
    if db.bind.dialect.name != "mysql":
        return
    tables = set(inspect(db.bind).get_table_names())
    statements: list[str] = []
    if "inv_reservation" not in tables:
        statements.append(
            """
            CREATE TABLE IF NOT EXISTS inv_reservation (
              id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, source_type VARCHAR(64) NOT NULL,
              source_id CHAR(36) NOT NULL, material_id CHAR(36) NOT NULL, warehouse_id CHAR(36) NOT NULL,
              quantity DECIMAL(18,6) NOT NULL, released_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
              status VARCHAR(32) NOT NULL DEFAULT 'reserved', note VARCHAR(255) NULL,
              is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
              created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
              updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
              UNIQUE KEY uk_inv_reservation_source_line (org_id, source_type, source_id, material_id, warehouse_id),
              KEY idx_inv_reservation_material (org_id, material_id, warehouse_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    if "inv_trace_event" not in tables:
        statements.append(
            """
            CREATE TABLE IF NOT EXISTS inv_trace_event (
              id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, material_id CHAR(36) NOT NULL,
              batch_id CHAR(36) NULL, transaction_id CHAR(36) NULL, source_type VARCHAR(64) NOT NULL,
              source_id CHAR(36) NOT NULL, direction VARCHAR(16) NOT NULL, quantity DECIMAL(18,6) NOT NULL,
              warehouse_id CHAR(36) NOT NULL, location_id CHAR(36) NULL, event_time DATE NULL,
              is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
              created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
              updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
              KEY idx_inv_trace_material (org_id, material_id, batch_id),
              KEY idx_inv_trace_source (org_id, source_type, source_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    if "qa_plan" not in tables:
        statements.append(
            """
            CREATE TABLE IF NOT EXISTS qa_plan (
              id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, name VARCHAR(128) NOT NULL,
              items_json JSON NOT NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0,
              created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
              updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
              version INT NOT NULL DEFAULT 1, KEY idx_qa_plan_org (org_id, name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    if "qa_defect_catalog" not in tables:
        statements.append(
            """
            CREATE TABLE IF NOT EXISTS qa_defect_catalog (
              id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, code VARCHAR(64) NOT NULL,
              name VARCHAR(128) NOT NULL, severity VARCHAR(32) NOT NULL DEFAULT 'major',
              status VARCHAR(32) NOT NULL DEFAULT 'active', is_deleted TINYINT(1) NOT NULL DEFAULT 0,
              version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
              updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
              UNIQUE KEY uk_qa_defect_code (org_id, code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    for statement in statements:
        db.execute(text(statement))
    if statements:
        db.commit()


def ensure_p0_wms_schema(db: Session) -> None:
    """Create P0 execution tables for databases upgraded without migration 012."""
    if db.bind.dialect.name != "mysql":
        return
    tables = set(inspect(db.bind).get_table_names())
    statements: list[str] = []
    if "inv_pick_wave" not in tables:
        statements.append(
            """
            CREATE TABLE IF NOT EXISTS inv_pick_wave (
              id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, wave_no VARCHAR(64) NOT NULL,
              warehouse_id CHAR(36) NOT NULL, status VARCHAR(32) NOT NULL DEFAULT 'draft', priority INT NOT NULL DEFAULT 50,
              assigned_to CHAR(36) NULL, released_at DATETIME NULL, completed_at DATETIME NULL,
              is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
              created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
              updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
              UNIQUE KEY uk_inv_pick_wave_no (org_id, wave_no), KEY idx_inv_pick_wave_scope (org_id, warehouse_id, status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    if "inv_warehouse_task" not in tables:
        statements.append(
            """
            CREATE TABLE IF NOT EXISTS inv_warehouse_task (
              id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, task_no VARCHAR(64) NOT NULL, task_type VARCHAR(32) NOT NULL,
              source_type VARCHAR(64) NULL, source_id CHAR(36) NULL, warehouse_id CHAR(36) NOT NULL, location_id CHAR(36) NULL,
              material_id CHAR(36) NULL, batch_id CHAR(36) NULL, planned_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
              completed_quantity DECIMAL(18,6) NOT NULL DEFAULT 0, assigned_to CHAR(36) NULL, wave_id CHAR(36) NULL,
              status VARCHAR(32) NOT NULL DEFAULT 'ready', priority INT NOT NULL DEFAULT 50, exception_reason VARCHAR(500) NULL,
              completed_at DATETIME NULL, completed_by CHAR(36) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0,
              version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
              updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
              UNIQUE KEY uk_inv_warehouse_task_no (org_id, task_no), KEY idx_inv_warehouse_task_scope (org_id, warehouse_id, status),
              KEY idx_inv_warehouse_task_wave (wave_id), CONSTRAINT fk_inv_task_wave FOREIGN KEY (wave_id) REFERENCES inv_pick_wave(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    if "mfg_work_order_schedule" not in tables:
        statements.append(
            """
            CREATE TABLE IF NOT EXISTS mfg_work_order_schedule (
              id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, work_order_id CHAR(36) NOT NULL, operation_id CHAR(36) NULL,
              work_center_id CHAR(36) NOT NULL, schedule_date DATE NOT NULL, scheduled_hours DECIMAL(18,6) NOT NULL,
              actual_hours DECIMAL(18,6) NOT NULL DEFAULT 0, status VARCHAR(32) NOT NULL DEFAULT 'planned', created_by CHAR(36) NULL,
              is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
              created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
              UNIQUE KEY uk_mfg_work_order_schedule_operation (org_id, work_order_id, operation_id),
              KEY idx_mfg_schedule_capacity (org_id, work_center_id, schedule_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    if "mfg_alternate_material" not in tables:
        statements.append(
            """
            CREATE TABLE IF NOT EXISTS mfg_alternate_material (
              id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, work_order_id CHAR(36) NOT NULL, material_id CHAR(36) NOT NULL,
              alternate_material_id CHAR(36) NOT NULL, conversion_rate DECIMAL(18,6) NOT NULL DEFAULT 1,
              status VARCHAR(32) NOT NULL DEFAULT 'approved', reason VARCHAR(255) NULL, approved_by CHAR(36) NULL,
              is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
              created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
              UNIQUE KEY uk_mfg_alternate_material (org_id, work_order_id, material_id, alternate_material_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    if "mfg_work_order_exception" not in tables:
        statements.append(
            """
            CREATE TABLE IF NOT EXISTS mfg_work_order_exception (
              id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, work_order_id CHAR(36) NOT NULL, exception_type VARCHAR(64) NOT NULL,
              description VARCHAR(500) NOT NULL, status VARCHAR(32) NOT NULL DEFAULT 'open', occurred_at DATETIME NOT NULL,
              reported_by CHAR(36) NULL, resolved_at DATETIME NULL, resolved_by CHAR(36) NULL, resolution VARCHAR(500) NULL,
              is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
              created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
              KEY idx_mfg_exception_order_status (org_id, work_order_id, status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    if "fin_budget" not in tables:
        statements.append(
            """
            CREATE TABLE IF NOT EXISTS fin_budget (
              id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, budget_period CHAR(7) NOT NULL, account_code VARCHAR(64) NOT NULL,
              department_id CHAR(36) NULL, budget_amount DECIMAL(18,2) NOT NULL, actual_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
              status VARCHAR(32) NOT NULL DEFAULT 'draft', note VARCHAR(255) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
              created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
              UNIQUE KEY uk_fin_budget_scope (org_id, budget_period, account_code, department_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    if "fin_cash_forecast" not in tables:
        statements.append(
            """
            CREATE TABLE IF NOT EXISTS fin_cash_forecast (
              id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, forecast_date DATE NOT NULL,
              inflow_amount DECIMAL(18,2) NOT NULL DEFAULT 0, outflow_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
              net_amount DECIMAL(18,2) NOT NULL DEFAULT 0, source VARCHAR(64) NOT NULL DEFAULT 'manual',
              status VARCHAR(32) NOT NULL DEFAULT 'draft', note VARCHAR(255) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
              created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
              UNIQUE KEY uk_fin_cash_forecast_day (org_id, forecast_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    if "fin_reconciliation_statement" not in tables:
        statements.append(
            """
            CREATE TABLE IF NOT EXISTS fin_reconciliation_statement (
              id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, statement_no VARCHAR(64) NOT NULL, statement_type VARCHAR(8) NOT NULL,
              party_id CHAR(36) NOT NULL, period CHAR(7) NOT NULL, statement_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
              reconciled_amount DECIMAL(18,2) NOT NULL DEFAULT 0, status VARCHAR(32) NOT NULL DEFAULT 'draft', note VARCHAR(255) NULL,
              is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1,
              created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
              UNIQUE KEY uk_fin_reconciliation_statement_no (org_id, statement_no)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    for statement in statements:
        db.execute(text(statement))
    if statements:
        db.commit()
