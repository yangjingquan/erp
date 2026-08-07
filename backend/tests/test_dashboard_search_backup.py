from datetime import date
from decimal import Decimal

import pytest

from app.core.exceptions import AppError
from app.models.master_data import MdMaterial
from app.models.sales import SalesOrder
from app.models.system import SysUser
from app.services.auth_service import UserContext
from app.services.backup_service import build_backup_command, validate_restore_request
from app.services.dashboard_service import dashboard_overview
from app.services.search_service import global_search


def context(session):
    return UserContext(user=session.query(SysUser).one(), permissions={"*"})


def test_dashboard_returns_scoped_summary(client_and_session):
    _, session = client_and_session
    user = session.query(SysUser).one()
    session.add(
        MdMaterial(id="material-dashboard", org_id=user.org_id, code="DASH-1", name="看板物料")
    )
    session.add(
        SalesOrder(
            id="order-dashboard", org_id=user.org_id, doc_no="SO-DASH-1", customer_id="customer-1",
            status="approved", order_date=date(2026, 8, 2), total_amount=Decimal("88"),
        )
    )
    session.commit()

    result = dashboard_overview(session, context(session))

    assert result["sales_total"] == Decimal("88.00")
    assert "inventory_warning_count" in result


def test_global_search_returns_material_and_order_matches(client_and_session):
    _, session = client_and_session
    user = session.query(SysUser).one()
    session.add(MdMaterial(id="material-search", org_id=user.org_id, code="SEARCH-1", name="检索轴承"))
    session.add(
        SalesOrder(
            id="order-search", org_id=user.org_id, doc_no="SO-SEARCH-1", customer_id="customer-1",
            status="draft", order_date=date(2026, 8, 2), total_amount=Decimal("10"),
        )
    )
    session.commit()

    result = global_search(session, context(session), "SEARCH")

    assert {row["resource"] for row in result} == {"material", "sales_order"}


def test_backup_command_has_explicit_database_and_target(tmp_path):
    command = build_backup_command(tmp_path / "erp.sql")

    assert "--databases" in command
    assert "erp" in command
    assert str(tmp_path / "erp.sql") in command


def test_backup_command_uses_the_local_shop_mysql_container(tmp_path):
    command = build_backup_command(tmp_path / "erp.sql")

    assert command[:3] == ["docker", "exec", "shop-mysql"]


def test_restore_requires_confirmation_and_valid_sql_path(tmp_path):
    backup = tmp_path / "erp.sql"
    backup.write_text("-- ERP backup\n", encoding="utf-8")

    with pytest.raises(AppError) as error:
        validate_restore_request(backup, "")
    assert error.value.code == 400
    assert validate_restore_request(backup, "RESTORE_ERP") is True


def test_restore_accepts_the_frontend_confirmation_word(tmp_path):
    backup = tmp_path / "erp.sql"
    backup.write_text("-- ERP backup\n", encoding="utf-8")

    assert validate_restore_request(backup, "RESTORE ERP") is True
