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


def ensure_p0_completion_schema(db: Session) -> None:
    """Create/upgrade the P0 completion tables for installations without migration 014."""
    if db.bind.dialect.name != "mysql":
        return
    inspector = inspect(db.bind)
    tables = set(inspector.get_table_names())
    statements: list[str] = []
    for table, columns in {
        "mfg_bom_item": [
            ("scrap_rate", "DECIMAL(8,4) NOT NULL DEFAULT 0"),
            ("issue_operation_id", "CHAR(36) NULL"),
            ("is_phantom", "TINYINT(1) NOT NULL DEFAULT 0"),
        ],
        "mfg_routing_operation": [("quality_plan_id", "CHAR(36) NULL"), ("equipment_requirement", "VARCHAR(255) NULL")],
        "mfg_work_order_exception": [("severity", "VARCHAR(16) NOT NULL DEFAULT 'medium'"), ("owner_id", "CHAR(36) NULL"), ("due_at", "DATETIME NULL"), ("source_event", "CHAR(36) NULL")],
    }.items():
        if table not in tables:
            continue
        existing = {item["name"] for item in inspector.get_columns(table)}
        for name, definition in columns:
            if name not in existing:
                statements.append(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
    ddl = {
        "mfg_demand_line": """CREATE TABLE IF NOT EXISTS mfg_demand_line (id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, material_id CHAR(36) NOT NULL, warehouse_id CHAR(36) NULL, demand_date DATE NOT NULL, quantity DECIMAL(18,6) NOT NULL, source_type VARCHAR(64) NOT NULL, source_id CHAR(36) NOT NULL, source_line_id CHAR(36) NULL, status VARCHAR(32) NOT NULL DEFAULT 'open', created_by CHAR(36) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), KEY idx_mfg_demand_scope (org_id, demand_date, material_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        "mfg_plan_run": """CREATE TABLE IF NOT EXISTS mfg_plan_run (id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, run_no VARCHAR(64) NOT NULL, plan_from DATE NOT NULL, plan_to DATE NOT NULL, warehouse_id CHAR(36) NULL, status VARCHAR(32) NOT NULL DEFAULT 'completed', algorithm_version VARCHAR(32) NOT NULL DEFAULT 'rules-v1', input_snapshot JSON NOT NULL, output_snapshot JSON NOT NULL, created_by CHAR(36) NULL, confirmed_at DATETIME NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), UNIQUE KEY uk_mfg_plan_run_no (org_id, run_no)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        "mfg_planned_order": """CREATE TABLE IF NOT EXISTS mfg_planned_order (id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, run_id CHAR(36) NOT NULL, order_type VARCHAR(32) NOT NULL, material_id CHAR(36) NOT NULL, warehouse_id CHAR(36) NULL, due_date DATE NOT NULL, quantity DECIMAL(18,6) NOT NULL, status VARCHAR(32) NOT NULL DEFAULT 'pending', source_snapshot JSON NOT NULL, formal_document_type VARCHAR(64) NULL, formal_document_id CHAR(36) NULL, confirmed_by CHAR(36) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), KEY idx_mfg_planned_order_status (org_id, status, due_date)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        "mfg_plan_exception": """CREATE TABLE IF NOT EXISTS mfg_plan_exception (id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, run_id CHAR(36) NOT NULL, material_id CHAR(36) NULL, exception_type VARCHAR(64) NOT NULL, severity VARCHAR(16) NOT NULL DEFAULT 'warning', due_date DATE NULL, impact_quantity DECIMAL(18,6) NOT NULL DEFAULT 0, details JSON NOT NULL, status VARCHAR(32) NOT NULL DEFAULT 'open', owner_id CHAR(36) NULL, resolution VARCHAR(500) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), KEY idx_mfg_plan_exception_scope (org_id, status, severity)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        "mfg_execution_event": """CREATE TABLE IF NOT EXISTS mfg_execution_event (id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, work_order_id CHAR(36) NOT NULL, operation_id CHAR(36) NULL, execution_key VARCHAR(128) NOT NULL, good_quantity DECIMAL(18,6) NOT NULL DEFAULT 0, scrap_quantity DECIMAL(18,6) NOT NULL DEFAULT 0, hours DECIMAL(18,6) NOT NULL DEFAULT 0, report_id CHAR(36) NULL, created_by CHAR(36) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), UNIQUE KEY uk_mfg_execution_event_key (org_id, execution_key)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        "fin_bank_statement": """CREATE TABLE IF NOT EXISTS fin_bank_statement (id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, statement_no VARCHAR(64) NOT NULL, bank_account_id CHAR(36) NOT NULL, statement_date DATE NOT NULL, opening_balance DECIMAL(18,2) NOT NULL DEFAULT 0, closing_balance DECIMAL(18,2) NOT NULL DEFAULT 0, status VARCHAR(32) NOT NULL DEFAULT 'draft', source_file VARCHAR(255) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), UNIQUE KEY uk_fin_bank_statement_no (org_id, statement_no)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        "fin_bank_statement_line": """CREATE TABLE IF NOT EXISTS fin_bank_statement_line (id CHAR(36) PRIMARY KEY, statement_id CHAR(36) NOT NULL, line_no INT NOT NULL, transaction_date DATE NOT NULL, amount DECIMAL(18,2) NOT NULL, direction VARCHAR(8) NOT NULL, counterparty VARCHAR(128) NULL, reference_no VARCHAR(128) NULL, matched_amount DECIMAL(18,2) NOT NULL DEFAULT 0, status VARCHAR(32) NOT NULL DEFAULT 'unmatched', note VARCHAR(255) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), UNIQUE KEY uk_fin_bank_statement_line_no (statement_id, line_no)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        "fin_reconciliation_match": """CREATE TABLE IF NOT EXISTS fin_reconciliation_match (id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, statement_line_id CHAR(36) NOT NULL, source_type VARCHAR(64) NOT NULL, source_id CHAR(36) NOT NULL, matched_amount DECIMAL(18,2) NOT NULL, match_type VARCHAR(32) NOT NULL DEFAULT 'rule', override_reason VARCHAR(255) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        "fin_period_close_checklist": """CREATE TABLE IF NOT EXISTS fin_period_close_checklist (id CHAR(36) PRIMARY KEY, org_id CHAR(36) NOT NULL, period CHAR(7) NOT NULL, item_code VARCHAR(64) NOT NULL, item_name VARCHAR(128) NOT NULL, owner_id CHAR(36) NULL, blocking TINYINT(1) NOT NULL DEFAULT 1, status VARCHAR(32) NOT NULL DEFAULT 'pending', evidence VARCHAR(500) NULL, completed_at DATETIME NULL, completed_by CHAR(36) NULL, is_deleted TINYINT(1) NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), UNIQUE KEY uk_fin_period_checklist_item (org_id, period, item_code)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    }
    statements.extend(sql for table, sql in ddl.items() if table not in tables)
    for statement in statements:
        db.execute(text(statement))
    if statements:
        db.commit()


def ensure_p1_p2_extension_schema(db: Session) -> None:
    """Install the P1/P2 extension tables on an already initialized database.

    The extension models have no destructive alterations and intentionally use
    business-id links, so SQLAlchemy can safely create only the new tables for
    an incremental deployment.  The versioned SQL migration remains the
    operator-facing installation artifact; this runtime guard keeps local and
    rolling deployments from failing when the migration was not run manually.
    """
    from app.core.database import Base
    from app.models import phase2_extensions  # noqa: F401

    table_names = {
        "plm_product_revision", "plm_change_request", "plm_change_order", "plm_change_impact",
        "srm_rfq", "srm_supplier_score", "project", "project_wbs", "project_milestone",
        "project_entry", "eam_asset", "eam_maintenance_plan", "eam_work_order", "svc_contract",
        "svc_case", "svc_visit", "tax_code", "tax_invoice", "org_intercompany_transaction",
        "low_code_definition", "metric_definition", "ai_exception_alert", "hr_leave_request",
    }
    missing = [table for table in Base.metadata.sorted_tables if table.name in table_names and table.name not in inspect(db.bind).get_table_names()]
    if missing:
        Base.metadata.create_all(bind=db.bind, tables=missing, checkfirst=True)
        db.commit()
