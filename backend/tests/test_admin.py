from app.core.security import create_access_token


def auth_headers():
    return {"Authorization": f"Bearer {create_access_token('user-1', ['system:department:manage', 'system:role:manage', 'system:user:manage', 'system:menu:manage'])}"}


def test_admin_basics_can_create_and_list_resources(client_and_session):
    client, _ = client_and_session
    headers = auth_headers()
    assert client.post("/api/admin/departments", json={"code": "D-001", "name": "销售部"}, headers=headers).json()["code"] == 0
    assert client.post("/api/admin/roles", json={"code": "sales", "name": "销售角色"}, headers=headers).json()["code"] == 0
    assert client.post("/api/admin/users", json={"username": "bob", "display_name": "Bob", "password": "Password@123"}, headers=headers).json()["code"] == 0
    assert client.post("/api/admin/menus", json={"code": "sales:orders", "name": "销售订单", "path": "/sales/orders"}, headers=headers).json()["code"] == 0
    assert len(client.get("/api/admin/users", headers=headers).json()["data"]) == 2
    assert client.get("/api/admin/menus", headers=headers).json()["data"][0]["code"] == "sales:orders"


def test_admin_duplicate_user_is_rejected(client_and_session):
    client, _ = client_and_session
    headers = auth_headers()
    payload = {"username": "alice", "display_name": "Alice 2", "password": "Password@123"}
    assert client.post("/api/admin/users", json=payload, headers=headers).json()["code"] == 409


def test_user_management_updates_profile_and_password(client_and_session):
    client, _ = client_and_session
    headers = auth_headers()
    user_id = client.post(
        "/api/admin/users",
        json={"username": "managed-user", "display_name": "待维护用户", "password": "Password@123"},
        headers=headers,
    ).json()["data"]["id"]
    assert client.put(
        f"/api/admin/users/{user_id}",
        json={"display_name": "已维护用户", "email": "user@example.com", "phone": "13800000000", "status": "active"},
        headers=headers,
    ).json()["code"] == 0
    assert client.put(
        f"/api/admin/users/{user_id}/password",
        json={"password": "NewPassword@123"},
        headers=headers,
    ).json()["code"] == 0
    assert client.post("/api/auth/login", json={"username": "managed-user", "password": "NewPassword@123"}).json()["code"] == 0


def test_role_page_and_function_permissions_are_effective(client_and_session):
    client, _ = client_and_session
    headers = auth_headers()
    role_response = client.post("/api/admin/roles", json={"code": "sales", "name": "销售角色"}, headers=headers)
    role_id = role_response.json()["data"]["id"]
    catalog = client.get("/api/admin/permissions/catalog", headers=headers).json()["data"]

    def find_page(nodes, path):
        for node in nodes:
            if node.get("path") == path:
                return node
            found = find_page(node.get("children", []), path)
            if found:
                return found
        return None

    page = find_page(catalog["pages"], "/sales/orders")
    function = next(item for item in catalog["functions"] if item["code"] == "page:sales:orders:view:create")
    assert page is not None
    access = client.put(
        f"/api/admin/roles/{role_id}/access",
        json={"menu_ids": [page["id"]], "permission_ids": [function["id"]]},
        headers=headers,
    )
    assert access.json()["code"] == 0

    user_response = client.post(
        "/api/admin/users",
        json={"username": "sales-user", "display_name": "销售用户", "password": "Password@123", "role_ids": [role_id]},
        headers=headers,
    )
    user_id = user_response.json()["data"]["id"]
    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {create_access_token(user_id, ['*'])}"},
    ).json()["data"]
    paths = {item["path"] for item in me["menus"][0]["children"]}
    assert "/sales/orders" in paths
    assert "/finance/payables" not in paths
    assert "page:sales:orders:view:create" in me["permissions"]


def test_permission_catalog_is_idempotent_with_legacy_module_permissions(client_and_session):
    client, _ = client_and_session
    headers = auth_headers()
    first = client.get("/api/admin/permissions/catalog", headers=headers).json()
    second = client.get("/api/admin/permissions/catalog", headers=headers).json()
    assert first["code"] == 0
    assert second["code"] == 0
    codes = [item["code"] for item in second["data"]["functions"]]
    assert len(codes) == len(set(codes))


def test_employee_management_uses_role_permission_and_updates_account(client_and_session):
    client, _ = client_and_session
    headers = auth_headers()
    role_id = client.post("/api/admin/roles", json={"code": "hr-manager", "name": "人事管理员"}, headers=headers).json()["data"]["id"]
    catalog = client.get("/api/admin/permissions/catalog", headers=headers).json()["data"]

    def find_page(nodes, path):
        for node in nodes:
            if node.get("path") == path:
                return node
            found = find_page(node.get("children", []), path)
            if found:
                return found
        return None

    employee_page = find_page(catalog["pages"], "/hr/employees")
    manage_permission = next(item for item in catalog["functions"] if item["code"] == "hr:employee:manage")
    client.put(f"/api/admin/roles/{role_id}/access", json={"menu_ids": [employee_page["id"]], "permission_ids": [manage_permission["id"]], "data_scope_type": "all"}, headers=headers)
    user_id = client.post("/api/admin/users", json={"username": "hr-user", "display_name": "人事用户", "password": "Password@123", "role_ids": [role_id]}, headers=headers).json()["data"]["id"]
    user_headers = {"Authorization": f"Bearer {create_access_token(user_id, ['*'])}"}
    created = client.post("/api/hr/employees", json={"employee_no": "E-100", "name": "人事用户", "base_salary": 1000, "allowance": 100, "account_username": "employee-login", "account_password": "Password@123"}, headers=user_headers)
    assert created.json()["code"] == 0
    employee_id = created.json()["data"]["id"]
    assert client.put(f"/api/hr/employees/{employee_id}", json={"name": "人事用户A", "status": "active", "base_salary": 1200, "allowance": 100}, headers=user_headers).json()["code"] == 0
    assert client.put(f"/api/hr/employees/{employee_id}/password", json={"password": "NewPassword@123"}, headers=user_headers).json()["code"] == 0
    assert client.post("/api/auth/login", json={"username": "employee-login", "password": "NewPassword@123"}).json()["code"] == 0
