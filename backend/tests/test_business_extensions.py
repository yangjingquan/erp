from app.core.security import create_access_token
from app.models.configuration import CfgNumberRule
from app.models.master_data import MdMaterial


def headers():
    return {"Authorization": f"Bearer {create_access_token('user-1', ['sales:manage', 'purchase:manage'])}"}


def test_quote_and_purchase_request_can_be_created(client_and_session):
    client, session = client_and_session
    session.add(MdMaterial(id="ext-material", org_id="org-1", code="EXT-1", name="扩展物料"))
    for key, prefix in [("sales_quote", "QT"), ("purchase_request", "PRQ")]:
        session.add(CfgNumberRule(id=f"rule-{key}", org_id="org-1", rule_key=key, prefix=prefix, date_format="%Y%m%d", sequence_length=4, reset_cycle="day"))
    session.commit()
    response = client.post("/api/sales/quotes", json={"customer_id": "c-1", "quote_date": "2026-08-02", "items": [{"material_id": "ext-material", "quantity": 2, "unit_price": 10}]}, headers=headers())
    assert response.json()["code"] == 0
    response = client.post("/api/purchase/requests", json={"request_date": "2026-08-02", "items": [{"material_id": "ext-material", "quantity": 3, "estimated_price": 4}]}, headers=headers())
    assert response.json()["code"] == 0
    assert len(client.get("/api/sales/quotes", headers=headers()).json()["data"]) == 1
    assert len(client.get("/api/purchase/requests", headers=headers()).json()["data"]) == 1
