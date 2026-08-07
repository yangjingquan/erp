from pathlib import Path


REQUIRED_TABLES = {
    "sys_org",
    "sys_department",
    "sys_user",
    "sys_role",
    "sys_menu",
    "sys_permission",
    "md_material",
    "md_customer",
    "md_supplier",
    "md_warehouse",
    "sales_order",
    "purchase_order",
    "inv_stock",
    "inv_stock_transaction",
    "fin_voucher",
    "fin_voucher_entry",
    "wf_definition",
    "cfg_number_rule",
    "sys_operation_log",
}


def test_init_sql_contains_required_schema_and_seed_markers():
    sql_path = Path(__file__).parents[2] / "database" / "init.sql"
    sql = sql_path.read_text(encoding="utf-8").lower()

    assert "create database if not exists erp" in sql
    assert "admin@123" not in sql
    assert "bcrypt" in sql or "$2b$" in sql
    for table in REQUIRED_TABLES:
        assert f"create table if not exists {table}" in sql


def test_init_sql_keeps_audit_version_column_on_master_tables():
    sql_path = Path(__file__).parents[2] / "database" / "init.sql"
    sql = sql_path.read_text(encoding="utf-8").lower()

    for table in ("md_unit", "md_tax_rate", "md_material", "md_customer", "md_supplier", "md_warehouse"):
        table_sql = sql.split(f"create table if not exists {table}", 1)[1].split("engine=", 1)[0]
        assert "version int not null default 1" in table_sql, table


def test_init_sql_keeps_soft_delete_column_on_audited_document_tables():
    sql_path = Path(__file__).parents[2] / "database" / "init.sql"
    sql = sql_path.read_text(encoding="utf-8").lower()

    for table in ("sales_delivery", "sales_return", "purchase_receipt", "purchase_return"):
        table_sql = sql.split(f"create table if not exists {table}", 1)[1].split("engine=", 1)[0]
        assert "is_deleted tinyint(1) not null default 0" in table_sql, table
