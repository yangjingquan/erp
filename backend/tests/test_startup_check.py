from app.services.startup_check import REQUIRED_TABLES, schema_status_from_tables


def test_schema_status_reports_missing_tables_with_initialization_guidance():
    result = schema_status_from_tables({"sys_user"})

    assert result.initialized is False
    assert "sys_role" in result.missing_tables
    assert "database/init.sql" in result.guidance


def test_schema_status_is_initialized_when_all_required_tables_exist():
    result = schema_status_from_tables(set(REQUIRED_TABLES))

    assert result.initialized is True
    assert result.missing_tables == []
