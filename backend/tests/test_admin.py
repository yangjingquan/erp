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
