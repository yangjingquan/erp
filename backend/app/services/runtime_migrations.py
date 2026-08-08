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
