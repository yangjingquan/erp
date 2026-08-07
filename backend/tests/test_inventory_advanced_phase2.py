from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.exceptions import AppError
from app.core.security import create_access_token
from app.models.inventory import InvCount, InvStock, InvStockTransaction, InvTransfer
from app.models.inventory_advanced import (
    InvBatch,
    InvCostLayer,
    InvCostLayerConsumption,
    InvLocation,
    InvSlowMovingRule,
    InvWarehouseAccess,
)
from app.models.master_data import MdMaterial, MdWarehouse
from app.models.system import SysUser
from app.schemas.inventory_advanced import BatchCreate, FifoInboundCreate, LocationCreate
from app.services.auth_service import UserContext
from app.services.inventory_advanced_service import (
    assert_warehouse_access,
    create_batch,
    create_location,
    list_slow_moving,
    post_fifo_inbound,
    post_fifo_outbound,
)
from app.services.inventory_service import serialize_transaction
from app.services.inventory_service import (
    approve_transfer,
    complete_count,
    complete_transfer,
    create_count,
    create_transfer,
    list_counts,
    list_safety_warnings,
    list_stock_transactions,
    list_transfers,
)


def _context(session, user_id: str = "user-1", permissions: set[str] | None = None) -> UserContext:
    return UserContext(
        user=session.get(SysUser, user_id),
        permissions=permissions or {"*"},
        warehouse_ids=set(session.scalars(select(InvWarehouseAccess.warehouse_id).where(
            InvWarehouseAccess.user_id == user_id, InvWarehouseAccess.org_id == "org-1"
        )).all()),
    )


def _seed_inventory(session) -> None:
    session.add_all(
        [
            MdWarehouse(id="warehouse-1", org_id="org-1", code="WH-1", name="Main"),
            MdWarehouse(id="warehouse-2", org_id="org-1", code="WH-2", name="Overflow"),
            MdWarehouse(id="warehouse-other", org_id="org-2", code="WH-X", name="Other"),
            MdMaterial(id="material-1", org_id="org-1", code="MAT-1", name="Material one"),
            MdMaterial(id="material-other", org_id="org-2", code="MAT-X", name="Other material"),
        ]
    )
    session.commit()


def _grant(session, warehouse_id: str, user_id: str = "user-1") -> None:
    session.add(
        InvWarehouseAccess(
            org_id="org-1",
            warehouse_id=warehouse_id,
            user_id=user_id,
            access_level="manage",
        )
    )
    session.flush()


def _location(session, context, code: str = "A-01") -> InvLocation:
    return create_location(
        session,
        "warehouse-1",
        None,
        LocationCreate(code=code, name=f"Location {code}"),
        context,
    )


def _batch(session, context, batch_no: str) -> InvBatch:
    return create_batch(
        session,
        "material-1",
        BatchCreate(batch_no=batch_no, expiry_date=date.today() + timedelta(days=30)),
        context,
    )


def test_fifo_outbound_consumes_oldest_layers_and_records_source_layer(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session)
    location = _location(session, current_context)
    first_batch = _batch(session, current_context, "B-1")
    second_batch = _batch(session, current_context, "B-2")

    post_fifo_inbound(
        session, "receipt", "r1", "warehouse-1", location.id, "material-1", first_batch.id,
        Decimal("3"), Decimal("10"), current_context,
    )
    post_fifo_inbound(
        session, "receipt", "r2", "warehouse-1", location.id, "material-1", second_batch.id,
        Decimal("4"), Decimal("12"), current_context,
    )
    consumed = post_fifo_outbound(
        session, "delivery", "d1", "warehouse-1", location.id, "material-1", None,
        Decimal("5"), current_context,
    )

    assert [(row["quantity"], row["unit_cost"]) for row in consumed] == [
        ("3", "10"),
        ("2", "12"),
    ]
    assert {row.cost_layer_id for row in session.query(InvCostLayerConsumption)} == {
        consumed[0]["cost_layer_id"], consumed[1]["cost_layer_id"]
    }
    assert [str(row.remaining_quantity) for row in session.query(InvCostLayer).order_by(InvCostLayer.created_at)] == [
        "0.000000", "2.000000"
    ]


def test_fifo_outbound_rejects_insufficient_layer_stock_without_writing_ledger(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session)
    location = _location(session, current_context)
    batch = _batch(session, current_context, "B-1")
    post_fifo_inbound(
        session, "receipt", "r1", "warehouse-1", location.id, "material-1", batch.id,
        Decimal("2"), Decimal("10"), current_context,
    )
    session.flush()

    with pytest.raises(AppError) as error:
        post_fifo_outbound(
            session, "delivery", "d1", "warehouse-1", location.id, "material-1", None,
            Decimal("3"), current_context,
        )

    assert error.value.code == 400
    assert session.query(InvStockTransaction).count() == 1
    assert session.query(InvCostLayerConsumption).count() == 0
    assert str(session.query(InvCostLayer).one().remaining_quantity) == "2.000000"


def test_fifo_preserves_batch_location_traceability_in_ledger_and_layers(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session)
    location = _location(session, current_context)
    batch = _batch(session, current_context, "LOT-202608")

    layers = post_fifo_inbound(
        session, "receipt", "r1", "warehouse-1", location.id, "material-1", batch.id,
        Decimal("2"), Decimal("9.50"), current_context,
    )
    transaction = session.query(InvStockTransaction).one()

    assert layers[0].location_id == location.id
    assert layers[0].batch_id == batch.id
    assert serialize_transaction(transaction)["location_id"] == location.id
    assert serialize_transaction(transaction)["batch_id"] == batch.id
    assert serialize_transaction(transaction)["consumed_layer_ids"] == []


def test_location_and_batch_reject_duplicate_or_cross_organization_references(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session)
    _location(session, current_context, "A-01")

    with pytest.raises(AppError) as duplicate:
        _location(session, current_context, "A-01")
    with pytest.raises(AppError) as cross_org:
        create_batch(
            session,
            "material-other",
            BatchCreate(batch_no="X-1"),
            current_context,
        )

    assert duplicate.value.code == 409
    assert cross_org.value.code == 404


def test_soft_deleted_location_and_batch_codes_return_conflicts(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session)
    location = _location(session, current_context, "A-01")
    batch = _batch(session, current_context, "B-01")
    location.is_deleted = True
    batch.is_deleted = True
    session.flush()

    with pytest.raises(AppError) as location_error:
        _location(session, current_context, "A-01")
    with pytest.raises(AppError) as batch_error:
        _batch(session, current_context, "B-01")

    assert location_error.value.code == 409
    assert batch_error.value.code == 409


def test_slow_moving_uses_most_specific_threshold_without_mutating_stock(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session)
    session.add(
        InvStock(
            id="stock-1", org_id="org-1", warehouse_id="warehouse-1", material_id="material-1",
            quantity=Decimal("4"), available_quantity=Decimal("4"),
        )
    )
    session.add_all(
        [
            InvStockTransaction(
                id="txn-old", org_id="org-1", warehouse_id="warehouse-1", material_id="material-1",
                source_type="receipt", source_id="old", direction="in", quantity=Decimal("4"), unit_cost=Decimal("10"),
                transaction_date=datetime(2026, 4, 1),
            ),
            InvSlowMovingRule(org_id="org-1", threshold_days=90),
            InvSlowMovingRule(org_id="org-1", warehouse_id="warehouse-1", material_id="material-1", threshold_days=60),
        ]
    )
    session.commit()

    rows = list_slow_moving(session, current_context, date(2026, 8, 2))

    assert rows == [{
        "warehouse_id": "warehouse-1", "material_id": "material-1", "quantity": "4",
        "days_since_movement": 123, "threshold_days": 60,
    }]
    assert str(session.get(InvStock, "stock-1").quantity) == "4.000000"


def test_slow_moving_rule_ties_use_stable_id_order(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session)
    session.add_all(
        [
            InvStock(
                id="stock-1", org_id="org-1", warehouse_id="warehouse-1", material_id="material-1",
                quantity=Decimal("1"), available_quantity=Decimal("1"),
            ),
            InvStockTransaction(
                id="txn-old", org_id="org-1", warehouse_id="warehouse-1", material_id="material-1",
                source_type="receipt", source_id="old", direction="in", quantity=Decimal("1"), unit_cost=Decimal("1"),
                transaction_date=datetime(2026, 4, 1),
            ),
            InvSlowMovingRule(id="rule-b", org_id="org-1", threshold_days=60),
            InvSlowMovingRule(id="rule-a", org_id="org-1", threshold_days=75),
        ]
    )
    session.commit()

    rows = list_slow_moving(session, current_context, date(2026, 8, 2))

    assert rows[0]["threshold_days"] == 75


def test_warehouse_access_blocks_unassigned_warehouse_and_cross_org_access(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session, permissions={"inventory:manage"})

    assert_warehouse_access(current_context, "warehouse-1")
    with pytest.raises(AppError) as unassigned:
        assert_warehouse_access(current_context, "warehouse-2")
    with pytest.raises(AppError) as cross_org:
        create_location(
            session, "warehouse-other", None, LocationCreate(code="X-01", name="Other"), current_context
        )

    assert unassigned.value.code == 403
    assert cross_org.value.code == 404


def test_production_manager_without_assignment_is_denied_warehouse_access(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)

    with pytest.raises(AppError) as error:
        assert_warehouse_access(_context(session, permissions={"production:manage"}), "warehouse-2")

    assert error.value.code == 403


def test_global_warehouse_permission_bypasses_assignments(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)

    assert_warehouse_access(_context(session, permissions={"warehouse:all"}), "warehouse-2")


def test_inventory_lists_only_return_assigned_warehouse_rows(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session, permissions={"inventory:manage"})
    material = session.get(MdMaterial, "material-1")
    material.min_stock = Decimal("5")
    session.add_all(
        [
            InvStock(id="stock-1", org_id="org-1", warehouse_id="warehouse-1", material_id="material-1", quantity=Decimal("1"), available_quantity=Decimal("1")),
            InvStock(id="stock-2", org_id="org-1", warehouse_id="warehouse-2", material_id="material-1", quantity=Decimal("1"), available_quantity=Decimal("1")),
            InvStockTransaction(id="txn-1", org_id="org-1", warehouse_id="warehouse-1", material_id="material-1", source_type="receipt", source_id="r1", direction="in", quantity=Decimal("1")),
            InvStockTransaction(id="txn-2", org_id="org-1", warehouse_id="warehouse-2", material_id="material-1", source_type="receipt", source_id="r2", direction="in", quantity=Decimal("1")),
            InvTransfer(id="transfer-1", org_id="org-1", doc_no="TR-1", from_warehouse_id="warehouse-1", to_warehouse_id="warehouse-1", transfer_date=date.today()),
            InvTransfer(id="transfer-2", org_id="org-1", doc_no="TR-2", from_warehouse_id="warehouse-2", to_warehouse_id="warehouse-2", transfer_date=date.today()),
            InvCount(id="count-1", org_id="org-1", doc_no="CT-1", warehouse_id="warehouse-1", count_date=date.today()),
            InvCount(id="count-2", org_id="org-1", doc_no="CT-2", warehouse_id="warehouse-2", count_date=date.today()),
        ]
    )
    session.commit()

    assert [row["warehouse_id"] for row in list_stock_transactions(session, current_context)] == ["warehouse-1"]
    assert [row["from_warehouse_id"] for row in list_transfers(session, current_context)] == ["warehouse-1"]
    assert [row["warehouse_id"] for row in list_counts(session, current_context)] == ["warehouse-1"]
    assert [row["warehouse_id"] for row in list_safety_warnings(session, current_context)] == ["warehouse-1"]


def test_stock_api_rejects_unassigned_warehouse_before_returning_stock(client_and_session):
    client, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    session.add_all(
        [
            InvStock(id="stock-1", org_id="org-1", warehouse_id="warehouse-1", material_id="material-1", quantity=Decimal("1"), available_quantity=Decimal("1")),
            InvStock(id="stock-2", org_id="org-1", warehouse_id="warehouse-2", material_id="material-1", quantity=Decimal("2"), available_quantity=Decimal("2")),
        ]
    )
    session.commit()
    headers = {"Authorization": f"Bearer {create_access_token('user-1', ['inventory:manage'])}"}

    allowed = client.get("/api/inventory/stock?warehouse_id=warehouse-1", headers=headers)
    denied = client.get("/api/inventory/stock?warehouse_id=warehouse-2", headers=headers)

    assert [row["id"] for row in allowed.json()["data"]] == ["stock-1"]
    assert denied.json()["code"] == 403


def test_inventory_count_and_transfer_operations_reject_unassigned_warehouses(client_and_session):
    _, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    current_context = _context(session, permissions={"inventory:manage"})
    transfer = InvTransfer(
        id="transfer-2", org_id="org-1", doc_no="TR-2", from_warehouse_id="warehouse-2",
        to_warehouse_id="warehouse-1", status="draft", transfer_date=date.today(),
    )
    count = InvCount(
        id="count-2", org_id="org-1", doc_no="CT-2", warehouse_id="warehouse-2", status="draft", count_date=date.today(),
    )
    session.add_all([transfer, count])
    session.commit()

    with pytest.raises(AppError) as create_count_error:
        create_count(session, current_context, warehouse_id="warehouse-2", items=[])
    with pytest.raises(AppError) as create_transfer_error:
        create_transfer(session, current_context, from_warehouse_id="warehouse-1", to_warehouse_id="warehouse-2", items=[])
    with pytest.raises(AppError) as approve_error:
        approve_transfer(session, transfer.id, current_context)
    transfer.status = "approved"
    with pytest.raises(AppError) as complete_transfer_error:
        complete_transfer(session, transfer.id, current_context)
    with pytest.raises(AppError) as complete_count_error:
        complete_count(session, count.id, current_context)

    assert {error.value.code for error in [create_count_error, create_transfer_error, approve_error, complete_transfer_error, complete_count_error]} == {403}


def test_advanced_api_requires_inventory_permission_and_warehouse_assignment(client_and_session):
    client, session = client_and_session
    _seed_inventory(session)
    _grant(session, "warehouse-1")
    no_permission_headers = {"Authorization": f"Bearer {create_access_token('user-1', [])}"}
    manage_headers = {"Authorization": f"Bearer {create_access_token('user-1', ['inventory:manage'])}"}

    denied = client.post(
        "/api/inventory/advanced/locations",
        json={"warehouse_id": "warehouse-1", "code": "A-01", "name": "A-01"},
        headers=no_permission_headers,
    )
    forbidden_warehouse = client.get(
        "/api/inventory/advanced/locations?warehouse_id=warehouse-2", headers=manage_headers
    )

    assert denied.status_code == 200
    assert denied.json()["code"] == 403
    assert forbidden_warehouse.status_code == 200
    assert forbidden_warehouse.json()["code"] == 403
