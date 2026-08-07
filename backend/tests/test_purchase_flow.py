from datetime import date

from app.core.security import create_access_token
from app.models.configuration import CfgNumberRule
from app.models.purchase import PurchaseReceipt


def headers():
    return {"Authorization": f"Bearer {create_access_token('user-1', ['purchase:manage'])}"}


def seed_rules(session):
    for key, prefix in [("purchase_order", "PO"), ("purchase_receipt", "PR")]:
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


def test_purchase_order_flow_creates_receipt(client_and_session):
    client, session = client_and_session
    seed_rules(session)
    created = client.post(
        "/api/purchase/orders",
        json={
            "supplier_id": "supplier-1",
            "order_date": str(date(2026, 8, 2)),
            "items": [{"material_id": "material-1", "quantity": 8, "unit_price": 7.5}],
        },
        headers=headers(),
    )
    order_id = created.json()["data"]["id"]
    client.post(f"/api/purchase/orders/{order_id}/submit", headers=headers())
    approved = client.post(f"/api/purchase/orders/{order_id}/approve", headers=headers())
    receipt = client.post(f"/api/purchase/orders/{order_id}/create-receipt", headers=headers())

    assert approved.json()["data"]["status"] == "approved"
    assert receipt.json()["code"] == 0
    assert session.query(PurchaseReceipt).count() == 1


def test_purchase_order_list_returns_created_orders(client_and_session):
    client, session = client_and_session
    seed_rules(session)
    created = client.post(
        "/api/purchase/orders",
        json={
            "supplier_id": "supplier-1",
            "order_date": str(date(2026, 8, 2)),
            "items": [{"material_id": "material-1", "quantity": 3, "unit_price": 8}],
        },
        headers=headers(),
    )

    response = client.get("/api/purchase/orders", headers=headers())

    assert created.json()["code"] == 0
    assert response.json()["code"] == 0
    assert response.json()["data"][0]["doc_no"] == created.json()["data"]["doc_no"]
