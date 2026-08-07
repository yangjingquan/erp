from datetime import date
from decimal import Decimal

from app.core.security import create_access_token
from app.models.configuration import CfgNumberRule
from app.models.inventory import InvStock
from app.models.master_data import MdMaterial, MdWarehouse
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from pathlib import Path


def headers():
    return {"Authorization": f"Bearer {create_access_token('user-1', ['production:manage'])}"}


def headers_without_production_permission():
    return {"Authorization": f"Bearer {create_access_token('user-1', [])}"}


def seed_number_rules(session):
    for key, prefix in [("mfg_mps", "MPS"), ("mfg_mrp", "MRP"), ("purchase_request", "PRQ")]:
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
    session.flush()


def create_approved_bom(client, material_id="finished-F", component_id="component-C", quantity="2"):
    created = client.post(
        "/api/production/boms",
        json={
            "material_id": material_id,
            "bom_version": "1.0",
            "effective_from": "2026-08-01",
            "items": [{"material_id": component_id, "quantity": quantity}],
        },
        headers=headers(),
    )
    bom_id = created.json()["data"]["id"]
    submitted = client.post(f"/api/production/boms/{bom_id}/submit", headers=headers())
    approved = client.post(f"/api/production/boms/{bom_id}/approve", headers=headers())
    assert submitted.json()["data"]["status"] == "submitted"
    assert approved.json()["data"]["status"] == "approved"
    return bom_id


def test_approved_bom_mrp_uses_stock_and_open_orders(client_and_session):
    """Removing supply snapshots or using gross instead of net demand breaks this contract."""
    client, session = client_and_session
    seed_number_rules(session)
    session.add_all(
        [
            MdMaterial(id="finished-F", org_id="org-1", code="F", name="Finished"),
            MdMaterial(id="component-C", org_id="org-1", code="C", name="Component"),
            MdWarehouse(id="warehouse-1", org_id="org-1", code="WH1", name="Main warehouse"),
            InvStock(
                org_id="org-1",
                warehouse_id="warehouse-1",
                material_id="component-C",
                quantity=Decimal("3"),
                available_quantity=Decimal("3"),
            ),
        ]
    )
    purchase_order = PurchaseOrder(
        id="open-purchase-order",
        org_id="org-1",
        doc_no="PO-OPEN",
        supplier_id="supplier-1",
        status="approved",
        order_date=date(2026, 8, 2),
    )
    purchase_order.items = [
        PurchaseOrderItem(
            material_id="component-C",
            warehouse_id="warehouse-1",
            quantity=Decimal("2"),
            received_quantity=Decimal("1"),
            unit_price=Decimal("10"),
        )
    ]
    session.add(purchase_order)
    session.commit()

    create_approved_bom(client)
    mps = client.post(
        "/api/production/mps",
        json={
            "material_id": "finished-F",
            "plan_date": "2026-08-10",
            "plan_quantity": "5",
            "warehouse_id": "warehouse-1",
        },
        headers=headers(),
    )
    run = client.post(f"/api/production/mps/{mps.json()['data']['id']}/run-mrp", headers=headers())

    assert run.json()["code"] == 0
    component_result = next(
        row for row in run.json()["data"]["results"] if row["material_id"] == "component-C"
    )
    assert component_result["gross_requirement"] == "10.000000"
    assert component_result["net_requirement"] == "6.000000"
    assert component_result["source_snapshot"]["available_stock"] == "3"
    assert component_result["source_snapshot"]["open_purchase_quantity"] == "1"


def test_bom_rejects_duplicate_components_and_invalid_effective_range(client_and_session):
    """Dropping BOM semantic validation must be visible through the public response contract."""
    client, session = client_and_session
    session.add_all(
        [
            MdMaterial(id="finished-F", org_id="org-1", code="F", name="Finished"),
            MdMaterial(id="component-C", org_id="org-1", code="C", name="Component"),
        ]
    )
    session.commit()

    duplicate = client.post(
        "/api/production/boms",
        json={
            "material_id": "finished-F",
            "effective_from": "2026-08-10",
            "items": [
                {"material_id": "component-C", "quantity": "1"},
                {"material_id": "component-C", "quantity": "2"},
            ],
        },
        headers=headers(),
    )
    invalid_range = client.post(
        "/api/production/boms",
        json={
            "material_id": "finished-F",
            "effective_from": "2026-08-10",
            "effective_to": "2026-08-01",
            "items": [{"material_id": "component-C", "quantity": "1"}],
        },
        headers=headers(),
    )

    assert duplicate.json()["code"] == 400
    assert "BOM" in duplicate.json()["msg"]
    assert invalid_range.json()["code"] == 400
    assert "BOM" in invalid_range.json()["msg"]


def test_mrp_confirmation_is_idempotent_and_production_routes_require_authentication(client_and_session):
    """A repeated confirmation must reuse its source document instead of duplicating procurement demand."""
    client, session = client_and_session
    seed_number_rules(session)
    session.add_all(
        [
            MdMaterial(id="finished-F", org_id="org-1", code="F", name="Finished"),
            MdMaterial(id="component-C", org_id="org-1", code="C", name="Component"),
        ]
    )
    session.commit()
    create_approved_bom(client)
    mps = client.post(
        "/api/production/mps",
        json={"material_id": "finished-F", "plan_date": "2026-08-10", "plan_quantity": "1"},
        headers=headers(),
    )
    run = client.post(f"/api/production/mps/{mps.json()['data']['id']}/run-mrp", headers=headers())
    component_result = next(
        row for row in run.json()["data"]["results"] if row["material_id"] == "component-C"
    )

    first = client.post(
        f"/api/production/mrp-results/{component_result['id']}/confirm", headers=headers()
    )
    second = client.post(
        f"/api/production/mrp-results/{component_result['id']}/confirm", headers=headers()
    )
    unauthenticated = client.get("/api/production/boms")

    assert first.json()["code"] == 0
    assert second.json()["data"]["source_document_ids"] == first.json()["data"]["source_document_ids"]
    assert unauthenticated.json()["code"] == 401


def test_production_write_routes_require_production_manage_permission(client_and_session):
    """Removing the explicit permission dependency must deny an authenticated unprivileged user."""
    client, session = client_and_session
    session.add_all(
        [
            MdMaterial(id="finished-F", org_id="org-1", code="F", name="Finished"),
            MdMaterial(id="component-C", org_id="org-1", code="C", name="Component"),
        ]
    )
    session.commit()

    response = client.post(
        "/api/production/boms",
        json={
            "material_id": "finished-F",
            "effective_from": "2026-08-01",
            "items": [{"material_id": "component-C", "quantity": "1"}],
        },
        headers=headers_without_production_permission(),
    )

    assert response.json()["code"] == 403


def test_create_bom_and_mps_reject_cross_org_material_and_warehouse_references(client_and_session):
    """Dropping org ownership checks must prevent cross-organization planning references."""
    client, session = client_and_session
    seed_number_rules(session)
    session.add_all(
        [
            MdMaterial(id="finished-F", org_id="org-1", code="F", name="Finished"),
            MdMaterial(id="component-C", org_id="org-2", code="C", name="Other org component"),
            MdMaterial(id="component-own", org_id="org-1", code="CO", name="Own component"),
            MdWarehouse(id="warehouse-other", org_id="org-2", code="WH2", name="Other org warehouse"),
        ]
    )
    session.commit()

    cross_org_component = client.post(
        "/api/production/boms",
        json={
            "material_id": "finished-F",
            "effective_from": "2026-08-01",
            "items": [{"material_id": "component-C", "quantity": "1"}],
        },
        headers=headers(),
    )
    cross_org_warehouse = client.post(
        "/api/production/mps",
        json={
            "material_id": "finished-F",
            "warehouse_id": "warehouse-other",
            "plan_date": "2026-08-10",
            "plan_quantity": "1",
        },
        headers=headers(),
    )

    assert cross_org_component.json()["code"] == 404
    assert cross_org_warehouse.json()["code"] == 404


def test_bom_rejects_indirect_circular_reference_on_approval(client_and_session):
    client, session = client_and_session
    session.add_all(
        [
            MdMaterial(id="material-A", org_id="org-1", code="A", name="A"),
            MdMaterial(id="material-B", org_id="org-1", code="B", name="B"),
        ]
    )
    session.commit()
    create_approved_bom(client, material_id="material-B", component_id="material-A")
    circular = client.post(
        "/api/production/boms",
        json={
            "material_id": "material-A",
            "effective_from": "2026-08-01",
            "items": [{"material_id": "material-B", "quantity": "1"}],
        },
        headers=headers(),
    )
    bom_id = circular.json()["data"]["id"]
    client.post(f"/api/production/boms/{bom_id}/submit", headers=headers())

    approval = client.post(f"/api/production/boms/{bom_id}/approve", headers=headers())

    assert approval.json()["code"] == 400
    assert "循环" in approval.json()["msg"]


def test_mrp_requires_approved_bom_creates_fresh_runs_and_can_disable_unreferenced_bom(client_and_session):
    client, session = client_and_session
    seed_number_rules(session)
    session.add_all(
        [
            MdMaterial(id="finished-F", org_id="org-1", code="F", name="Finished"),
            MdMaterial(id="component-C", org_id="org-1", code="C", name="Component"),
            MdMaterial(id="finished-unused", org_id="org-1", code="FU", name="Unused finished"),
            MdMaterial(id="component-unused", org_id="org-1", code="CU", name="Unused component"),
        ]
    )
    session.commit()
    missing_bom_mps = client.post(
        "/api/production/mps",
        json={"material_id": "finished-F", "plan_date": "2026-08-10", "plan_quantity": "1"},
        headers=headers(),
    )
    missing_bom = client.post(
        f"/api/production/mps/{missing_bom_mps.json()['data']['id']}/run-mrp", headers=headers()
    )
    unreferenced_bom_id = create_approved_bom(
        client, material_id="finished-unused", component_id="component-unused"
    )
    disabled = client.post(f"/api/production/boms/{unreferenced_bom_id}/disable", headers=headers())
    bom_id = create_approved_bom(client)
    runnable_mps = client.post(
        "/api/production/mps",
        json={"material_id": "finished-F", "plan_date": "2026-08-10", "plan_quantity": "1"},
        headers=headers(),
    )
    first_run = client.post(
        f"/api/production/mps/{runnable_mps.json()['data']['id']}/run-mrp", headers=headers()
    )
    second_run = client.post(
        f"/api/production/mps/{runnable_mps.json()['data']['id']}/run-mrp", headers=headers()
    )

    assert missing_bom.json()["code"] == 400
    assert disabled.json()["data"]["status"] == "disabled"
    assert first_run.json()["data"]["id"] != second_run.json()["data"]["id"]
    assert client.post(f"/api/production/boms/{bom_id}/disable", headers=headers()).json()["code"] == 400


def test_sql_contains_repeatable_production_schema_upgrade_path():
    sql = (Path(__file__).parents[2] / "database" / "init.sql").read_text(encoding="utf-8").lower()

    assert "information_schema.columns" in sql
    assert "effective_from date" in sql
    assert "alter table `mfg_bom` add column" in sql
