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
    # doc_no was part of the legacy table but is not mapped by the current ORM.
    # Making it nullable lets the current create_inspection flow insert safely.
    if columns.get("doc_no", {}).get("nullable") is False:
        db.execute(text("ALTER TABLE qa_inspection MODIFY COLUMN doc_no VARCHAR(64) NULL"))
        changed = True
    if changed:
        db.commit()
