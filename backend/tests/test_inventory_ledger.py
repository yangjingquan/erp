from decimal import Decimal

import pytest

from app.core.exceptions import AppError
from app.models.inventory import InvStock, InvStockTransaction
from app.models.inventory_advanced import InvWarehouseAccess
from app.models.master_data import MdMaterial
from app.services.auth_service import UserContext
from app.services.inventory_service import (
    complete_count,
    complete_transfer,
    create_count,
    create_transfer,
    list_safety_warnings,
    post_stock_transaction,
)
from app.models.system import SysUser


def headers():
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token('user-1', ['inventory:manage'])}"}


def context(session):
    return UserContext(user=session.query(SysUser).one(), permissions={"*"})


def seed_stock(session):
    session.add(
        MdMaterial(
            id="material-1",
            org_id="org-1",
            code="MAT-1",
            name="物料一",
            min_stock=Decimal("5"),
        )
    )
    session.add(
        InvStock(
            id="stock-1",
            org_id="org-1",
            warehouse_id="warehouse-1",
            material_id="material-1",
            quantity=Decimal("10"),
            available_quantity=Decimal("10"),
        )
    )
    session.add(
        InvWarehouseAccess(
            org_id="org-1",
            warehouse_id="warehouse-1",
            user_id="user-1",
            access_level="manage",
        )
    )
    session.commit()


def test_outbound_cannot_exceed_available_stock(client_and_session):
    _, session = client_and_session
    seed_stock(session)

    with pytest.raises(AppError) as error:
        post_stock_transaction(
            session,
            context(session),
            source_type="manual",
            source_id="source-1",
            warehouse_id="warehouse-1",
            material_id="material-1",
            quantity=Decimal("11"),
            direction="out",
        )

    assert error.value.code == 400


def test_inbound_updates_balance_and_writes_ledger(client_and_session):
    _, session = client_and_session
    seed_stock(session)

    post_stock_transaction(
        session,
        context(session),
        source_type="manual",
        source_id="source-in-1",
        warehouse_id="warehouse-1",
        material_id="material-1",
        quantity=Decimal("3"),
        direction="in",
    )
    session.commit()

    stock = session.get(InvStock, "stock-1")
    assert stock.quantity == Decimal("13.000000")
    assert session.query(InvStockTransaction).count() == 1


def test_duplicate_source_transaction_is_rejected(client_and_session):
    _, session = client_and_session
    seed_stock(session)
    kwargs = dict(
        db=session,
        context=context(session),
        source_type="manual",
        source_id="source-duplicate",
        warehouse_id="warehouse-1",
        material_id="material-1",
        quantity=Decimal("1"),
        direction="in",
    )
    post_stock_transaction(**kwargs)
    with pytest.raises(AppError) as error:
        post_stock_transaction(**kwargs)
    assert error.value.code == 409


def test_transfer_and_count_adjust_stock(client_and_session):
    _, session = client_and_session
    seed_stock(session)
    current_context = context(session)
    transfer = create_transfer(
        session,
        current_context,
        from_warehouse_id="warehouse-1",
        to_warehouse_id="warehouse-2",
        items=[{"material_id": "material-1", "quantity": Decimal("2")}],
    )
    transfer.status = "approved"
    complete_transfer(session, transfer.id, current_context)
    count = create_count(
        session,
        current_context,
        warehouse_id="warehouse-1",
        items=[{"material_id": "material-1", "actual_quantity": Decimal("6")}],
    )
    complete_count(session, count.id, current_context)
    session.commit()

    stock = session.get(InvStock, "stock-1")
    assert stock.quantity == Decimal("6.000000")
    assert session.query(InvStockTransaction).count() == 3


def test_safety_warning_returns_below_minimum_stock(client_and_session):
    _, session = client_and_session
    seed_stock(session)
    stock = session.get(InvStock, "stock-1")
    stock.quantity = Decimal("4")
    stock.available_quantity = Decimal("4")
    session.commit()

    warnings = list_safety_warnings(session, context(session))

    assert len(warnings) == 1
    assert warnings[0]["material_id"] == "material-1"


def test_inventory_transaction_list_returns_ledger_rows(client_and_session):
    client, session = client_and_session
    seed_stock(session)
    post_stock_transaction(
        session,
        context(session),
        source_type="manual",
        source_id="source-api-1",
        warehouse_id="warehouse-1",
        material_id="material-1",
        quantity=Decimal("2"),
        direction="in",
    )
    session.commit()

    response = client.get("/api/inventory/transactions", headers=headers())

    assert response.json()["code"] == 0
    assert response.json()["data"][0]["source_id"] == "source-api-1"
