from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import create_access_token
from app.models.configuration import CfgNumberRule
from app.models.finance import PurchasePayable
from app.models.inventory import InvStock, InvStockTransaction
from app.models.inventory_advanced import InvWarehouseAccess
from app.models.master_data import MdMaterial, MdSupplier, MdWarehouse
from app.models.production import MfgMaterialIssue
from app.models.system import SysUser
from app.services.auth_service import UserContext
from app.services.finance_service import create_payable_from_subcontract_receipt


def headers():
    return {"Authorization": f"Bearer {create_access_token('user-1', ['production:manage'])}"}


def seed_subcontract_data(session):
    session.add_all(
        [
            CfgNumberRule(
                id="rule-mfg-subcontract-order",
                org_id="org-1",
                rule_key="mfg_subcontract_order",
                prefix="SC",
                date_format="%Y%m%d",
                sequence_length=4,
                reset_cycle="day",
            ),
            CfgNumberRule(
                id="rule-mfg-subcontract-receipt",
                org_id="org-1",
                rule_key="mfg_subcontract_receipt",
                prefix="SR",
                date_format="%Y%m%d",
                sequence_length=4,
                reset_cycle="day",
            ),
            MdSupplier(id="supplier-1", org_id="org-1", code="SUP-1", name="Processor"),
            MdMaterial(id="subcontract-finished-1", org_id="org-1", code="SC-FG-1", name="Subcontract finished"),
            MdMaterial(id="subcontract-raw-1", org_id="org-1", code="SC-RM-1", name="Subcontract raw"),
            MdWarehouse(id="subcontract-warehouse-1", org_id="org-1", code="SC-WH-1", name="Subcontract warehouse"),
            InvWarehouseAccess(
                org_id="org-1", warehouse_id="subcontract-warehouse-1", user_id="user-1", access_level="manage"
            ),
            InvStock(
                id="subcontract-raw-stock-1",
                org_id="org-1",
                warehouse_id="subcontract-warehouse-1",
                material_id="subcontract-raw-1",
                quantity=Decimal("10"),
                available_quantity=Decimal("10"),
                average_cost=Decimal("3"),
            ),
        ]
    )
    session.commit()


def order_payload(**overrides):
    payload = {
        "supplier_id": "supplier-1",
        "material_id": "subcontract-finished-1",
        "warehouse_id": "subcontract-warehouse-1",
        "plan_date": "2026-08-02",
        "quantity": "10",
        "processing_fee": "120",
    }
    payload.update(overrides)
    return payload


def test_subcontract_issue_then_receive_creates_inventory_and_payable_source(client_and_session):
    """Dropping subcontract ledger or payable integration loses physical and financial traceability."""
    client, session = client_and_session
    seed_subcontract_data(session)

    created = client.post("/api/production/subcontract-orders", json=order_payload(), headers=headers())
    assert created.status_code == 200
    order = created.json()["data"]
    assert order["status"] == "draft"

    released = client.post(f"/api/production/subcontract-orders/{order['id']}/release", headers=headers())
    issue = client.post(
        f"/api/production/subcontract-orders/{order['id']}/issue",
        json={"items": [{"material_id": "subcontract-raw-1", "quantity": "10"}]},
        headers=headers(),
    )
    received = client.post(
        f"/api/production/subcontract-orders/{order['id']}/receipts",
        json={"good_quantity": "10", "unit_cost": "12", "operation_key": "receipt-full-1"},
        headers=headers(),
    )

    assert released.json()["data"]["status"] == "released"
    assert issue.json()["data"]["subcontract_order_id"] == order["id"]
    receipt = received.json()["data"]
    assert receipt["status"] == "completed"
    assert session.query(InvStockTransaction).filter_by(
        source_type="subcontract_material_issue", source_id=issue.json()["data"]["id"]
    ).count() == 1
    assert session.query(InvStockTransaction).filter_by(
        source_type="subcontract_receipt", source_id=receipt["id"]
    ).count() == 1
    payable = session.query(PurchasePayable).filter_by(
        source_type="subcontract_receipt", source_id=receipt["id"]
    ).one()
    assert payable.total_amount == Decimal("120.00")
    assert session.get(InvStock, "subcontract-raw-stock-1").quantity == Decimal("0.000000")

    assert client.post(f"/api/production/subcontract-orders/{order['id']}/release", headers=headers()).json()["data"]["id"] == order["id"]
    assert client.post(
        f"/api/production/subcontract-orders/{order['id']}/issue",
        json={"items": [{"material_id": "subcontract-raw-1", "quantity": "10"}]},
        headers=headers(),
    ).json()["data"]["id"] == issue.json()["data"]["id"]
    assert client.post(
        f"/api/production/subcontract-orders/{order['id']}/receipts",
        json={"good_quantity": "10", "unit_cost": "12", "operation_key": "receipt-full-1"},
        headers=headers(),
    ).json()["data"]["id"] == receipt["id"]
    assert session.query(PurchasePayable).filter_by(source_type="subcontract_receipt", source_id=receipt["id"]).count() == 1


def test_subcontract_rejects_missing_permission_and_foreign_supplier(client_and_session):
    """Removing route permission or supplier-organization validation enables unauthorized foreign processing orders."""
    client, session = client_and_session
    seed_subcontract_data(session)
    session.add(MdSupplier(id="supplier-foreign", org_id="org-2", code="SUP-2", name="Foreign processor"))
    session.commit()

    forbidden = client.post(
        "/api/production/subcontract-orders",
        json=order_payload(),
        headers={"Authorization": f"Bearer {create_access_token('user-1', [])}"},
    )
    foreign_supplier = client.post(
        "/api/production/subcontract-orders",
        json=order_payload(supplier_id="supplier-foreign"),
        headers=headers(),
    )

    assert forbidden.json()["code"] == 403
    assert foreign_supplier.json()["code"] == 404


def test_subcontract_order_can_be_cancelled_before_receipt(client_and_session):
    """Allowing post-cancellation issue would create stock movement for a terminal subcontract order."""
    client, session = client_and_session
    seed_subcontract_data(session)
    order = client.post("/api/production/subcontract-orders", json=order_payload(), headers=headers()).json()["data"]
    client.post(f"/api/production/subcontract-orders/{order['id']}/release", headers=headers())

    cancelled = client.post(f"/api/production/subcontract-orders/{order['id']}/cancel", headers=headers())
    issue_after_cancel = client.post(
        f"/api/production/subcontract-orders/{order['id']}/issue",
        json={"items": [{"material_id": "subcontract-raw-1", "quantity": "1"}]},
        headers=headers(),
    )

    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert issue_after_cancel.json()["code"] == 400


def test_subcontract_receipt_operation_key_allows_equal_partials_and_preserves_fee_residual(client_and_session):
    """Payload equality must not collapse two physical equal deliveries, while a retry must not duplicate stock or payables."""
    client, session = client_and_session
    seed_subcontract_data(session)
    order = client.post(
        "/api/production/subcontract-orders",
        json=order_payload(processing_fee="100.01"),
        headers=headers(),
    ).json()["data"]
    client.post(f"/api/production/subcontract-orders/{order['id']}/release", headers=headers())

    first = client.post(
        f"/api/production/subcontract-orders/{order['id']}/receipts",
        json={"good_quantity": "5", "unit_cost": "12", "operation_key": "partial-receipt-1"},
        headers=headers(),
    )
    second = client.post(
        f"/api/production/subcontract-orders/{order['id']}/receipts",
        json={"good_quantity": "5", "unit_cost": "12", "operation_key": "partial-receipt-2"},
        headers=headers(),
    )
    retried_first = client.post(
        f"/api/production/subcontract-orders/{order['id']}/receipts",
        json={"good_quantity": "5", "unit_cost": "12", "operation_key": "partial-receipt-1"},
        headers=headers(),
    )

    first_receipt = first.json()["data"]
    second_receipt = second.json()["data"]
    assert first_receipt["id"] != second_receipt["id"]
    assert first_receipt["processing_fee_amount"] == "50.01"
    assert second_receipt["processing_fee_amount"] == "50.00"
    assert retried_first.json()["data"]["id"] == first_receipt["id"]
    assert session.query(InvStockTransaction).filter_by(source_type="subcontract_receipt").count() == 2
    payables = session.query(PurchasePayable).filter_by(source_type="subcontract_receipt").all()
    assert {payable.total_amount for payable in payables} == {Decimal("50.01"), Decimal("50.00")}


def test_subcontract_receipt_requires_nonblank_operation_key_and_hides_foreign_order(client_and_session):
    """An empty idempotency key or foreign order must not create a receipt side effect."""
    client, session = client_and_session
    seed_subcontract_data(session)
    order = client.post("/api/production/subcontract-orders", json=order_payload(), headers=headers()).json()["data"]
    client.post(f"/api/production/subcontract-orders/{order['id']}/release", headers=headers())

    invalid_key = client.post(
        f"/api/production/subcontract-orders/{order['id']}/receipts",
        json={"good_quantity": "1", "unit_cost": "12", "operation_key": ""},
        headers=headers(),
    )
    foreign_order = client.post(
        "/api/production/subcontract-orders/foreign-order/receipts",
        json={"good_quantity": "1", "unit_cost": "12", "operation_key": "foreign-order-receipt"},
        headers=headers(),
    )

    assert invalid_key.json()["code"] == 422
    assert foreign_order.json()["code"] == 404
    assert session.query(InvStockTransaction).filter_by(source_type="subcontract_receipt").count() == 0


def test_subcontract_issue_unique_invariant_rejects_a_stale_duplicate(client_and_session):
    """Without the database invariant, two stale requests can both post outbound subcontract stock."""
    client, session = client_and_session
    seed_subcontract_data(session)
    order = client.post("/api/production/subcontract-orders", json=order_payload(), headers=headers()).json()["data"]
    client.post(f"/api/production/subcontract-orders/{order['id']}/release", headers=headers())
    issue = client.post(
        f"/api/production/subcontract-orders/{order['id']}/issue",
        json={"items": [{"material_id": "subcontract-raw-1", "quantity": "1"}]},
        headers=headers(),
    ).json()["data"]

    session.add(
        MfgMaterialIssue(
            org_id="org-1",
            subcontract_order_id=order["id"],
            warehouse_id="subcontract-warehouse-1",
            source_type="mfg_subcontract_order",
            source_id=order["id"],
            created_by="user-1",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    retried_issue = client.post(
        f"/api/production/subcontract-orders/{order['id']}/issue",
        json={"items": [{"material_id": "subcontract-raw-1", "quantity": "1"}]},
        headers=headers(),
    )
    assert retried_issue.json()["data"]["id"] == issue["id"]
    assert session.query(InvStockTransaction).filter_by(source_type="subcontract_material_issue").count() == 1


def test_subcontract_payable_recovers_from_a_stale_duplicate_lookup(client_and_session, monkeypatch):
    """A stale payable lookup must recover the source-unique payable instead of creating a second liability."""
    client, session = client_and_session
    seed_subcontract_data(session)
    order = client.post("/api/production/subcontract-orders", json=order_payload(), headers=headers()).json()["data"]
    client.post(f"/api/production/subcontract-orders/{order['id']}/release", headers=headers())
    receipt = client.post(
        f"/api/production/subcontract-orders/{order['id']}/receipts",
        json={"good_quantity": "10", "unit_cost": "12", "operation_key": "payable-recovery-receipt"},
        headers=headers(),
    ).json()["data"]
    payable = session.query(PurchasePayable).filter_by(source_type="subcontract_receipt", source_id=receipt["id"]).one()
    real_scalar = session.scalar
    lookup_count = 0

    def stale_first_lookup(*args, **kwargs):
        nonlocal lookup_count
        lookup_count += 1
        if lookup_count == 1:
            return None
        return real_scalar(*args, **kwargs)

    monkeypatch.setattr(session, "scalar", stale_first_lookup)
    recovered = create_payable_from_subcontract_receipt(
        session,
        receipt["id"],
        UserContext(user=session.get(SysUser, "user-1"), permissions={"*"}),
    )

    assert recovered.id == payable.id
    assert session.query(PurchasePayable).filter_by(source_type="subcontract_receipt", source_id=receipt["id"]).count() == 1


def test_sql_contains_repeatable_subcontract_schema_bootstrap():
    """Removing subcontract tables or guarded upgrades breaks existing MySQL installations on re-run."""
    sql = (Path(__file__).parents[2] / "database" / "init.sql").read_text(encoding="utf-8").lower()

    for table in ("mfg_subcontract_order", "mfg_subcontract_receipt"):
        table_sql = sql.split(f"create table if not exists {table}", 1)[1].split("engine=", 1)[0]
        assert "is_deleted tinyint(1) not null default 0" in table_sql
        assert "created_at datetime(6) not null default current_timestamp(6)" in table_sql
        assert "updated_at datetime(6) not null default current_timestamp(6) on update current_timestamp(6)" in table_sql
        assert "version int not null default 1" in table_sql
    assert "create procedure phase2_add_task4_column" in sql
    assert "call phase2_add_task4_column('mfg_material_issue', 'subcontract_order_id'" in sql
    assert "uk_mfg_material_issue_subcontract_order" in sql
    assert "uk_mfg_subcontract_receipt_operation" in sql
    assert "operation_key varchar(64) not null" in sql
