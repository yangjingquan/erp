from sqlalchemy import select

from app.core.security import create_access_token
from app.models.system import SysUser
from app.services.auth_service import data_scope_condition


def test_permission_endpoint_rejects_user_without_required_button_permission(
    client_and_session,
):
    client, _ = client_and_session
    token = create_access_token("user-1", permissions=[])

    response = client.get(
        "/api/auth/permission-check",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.json()["code"] == 403


def test_department_data_scope_only_returns_current_department():
    class User:
        id = "user-1"
        department_id = "dept-1"
        org_id = "org-1"
        is_superuser = False

    statement = select(SysUser).where(
        data_scope_condition(SysUser, User(), scope_type="department")
    )

    assert "department_id" in str(statement)
