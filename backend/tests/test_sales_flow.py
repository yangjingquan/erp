from datetime import date

from app.core.security import create_access_token
from app.models.configuration import CfgNumberRule
from app.models.sales import SalesDelivery


def headers():
    return {"Authorization": f"Bearer {create_access_token('user-1', ['sales:manage'])}"}


def seed_rules(session):
    for key, prefix in [("sales_order", "SO"), ("sales_delivery", "SD")]:
        session.add(
            CfgNumberRule(
                id=f"rule-{key}",
                org_id="org-1",
                rule_key=key,
                prefix=prefix,
                date_format="%Y%m%d",
                sequence_length=4,
                reset_cycle="day",
            )
        )
    session.commit()


def test_sales_order_status_flow_creates_delivery(client_and_session):
    client, session = client_and_session
    seed_rules(session)
    payload = {
        "customer_id": "customer-1",
        "order_date": str(date(2026, 8, 2)),
        "items": [{"material_id": "material-1", "quantity": 10, "unit_price": 12.5}],
    }

    created = client.post("/api/sales/orders", json=payload, headers=headers())
    order_id = created.json()["data"]["id"]
    submitted = client.post(f"/api/sales/orders/{order_id}/submit", headers=headers())
    approved = client.post(f"/api/sales/orders/{order_id}/approve", headers=headers())
    delivery = client.post(f"/api/sales/orders/{order_id}/create-delivery", headers=headers())

    assert created.json()["data"]["status"] == "draft"
    assert submitted.json()["data"]["status"] == "submitted"
    assert approved.json()["data"]["status"] == "approved"
    assert delivery.json()["code"] == 0
    assert session.query(SalesDelivery).count() == 1


def test_sales_return_rejects_completed_delivery(client_and_session):
    client, session = client_and_session
    seed_rules(session)
    created = client.post(
        "/api/sales/orders",
        json={
            "customer_id": "customer-1",
            "order_date": str(date(2026, 8, 2)),
            "items": [{"material_id": "material-1", "quantity": 1, "unit_price": 10}],
        },
        headers=headers(),
    )
    order_id = created.json()["data"]["id"]
    client.post(f"/api/sales/orders/{order_id}/submit", headers=headers())
    client.post(f"/api/sales/orders/{order_id}/approve", headers=headers())
    delivery_response = client.post(f"/api/sales/orders/{order_id}/create-delivery", headers=headers())
    delivery_id = delivery_response.json()["data"]["id"]
    delivery = session.get(SalesDelivery, delivery_id)
    delivery.status = "completed"
    session.commit()

    response = client.post(
        "/api/sales/returns",
        json={"source_delivery_id": delivery_id, "customer_id": "customer-1", "warehouse_id": "warehouse-1", "items": []},
        headers=headers(),
    )

    assert response.json()["code"] == 400


def test_sales_order_list_returns_created_orders(client_and_session):
    client, session = client_and_session
    seed_rules(session)
    created = client.post(
        "/api/sales/orders",
        json={
            "customer_id": "customer-1",
            "order_date": str(date(2026, 8, 2)),
            "items": [{"material_id": "material-1", "quantity": 2, "unit_price": 10}],
        },
        headers=headers(),
    )

    response = client.get("/api/sales/orders", headers=headers())

    assert created.json()["code"] == 0
    assert response.json()["code"] == 0
    assert response.json()["data"][0]["doc_no"] == created.json()["data"]["doc_no"]
