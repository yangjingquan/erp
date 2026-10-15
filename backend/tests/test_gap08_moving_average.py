"""GAP-08: 移动加权平均成本 + 禁止负库存."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.exceptions import AppError
from app.models.configuration import CfgGlobalParameter
from app.models.inventory import InvStock, InvStockTransaction
from app.services.inventory_service import complete_sales_delivery, post_stock_transaction
from app.services.sales_service import create_delivery_from_order
from tests.gap_helpers import approved_sales_order, receive


def _stock(db, md):
    return db.scalar(select(InvStock).where(InvStock.warehouse_id == md.wh.id, InvStock.material_id == md.mat.id))


def test_moving_weighted_average_on_inbound(db, ctx, md):
    receive(db, ctx, md, "10", "5")
    assert _stock(db, md).average_cost == Decimal("5")
    receive(db, ctx, md, "10", "8")
    stock = _stock(db, md)
    assert stock.quantity == Decimal("20")
    assert stock.average_cost == Decimal("6.5")


def test_sales_delivery_costed_at_average_not_price(db, ctx, md):
    receive(db, ctx, md, "10", "5")
    order = approved_sales_order(db, ctx, md, "4", "20")
    delivery = create_delivery_from_order(db, order.id, ctx)
    complete_sales_delivery(db, delivery.id, ctx)
    tx = db.scalar(select(InvStockTransaction).where(InvStockTransaction.source_type == "sales_delivery"))
    assert tx.unit_cost == Decimal("5") and tx.amount == Decimal("20.00")
    assert _stock(db, md).average_cost == Decimal("5")


def test_negative_stock_blocked_with_chinese_message(db, ctx, md):
    receive(db, ctx, md, "2", "5")
    with pytest.raises(AppError) as exc:
        post_stock_transaction(db, ctx, source_type="manual", source_id="x", warehouse_id=md.wh.id, material_id=md.mat.id, quantity=Decimal("3"), direction="out")
    assert "可用库存不足" in exc.value.msg and "测试物料" in exc.value.msg and "负库存" in exc.value.msg


def test_negative_stock_allowed_by_parameter(db, ctx, md):
    db.add(CfgGlobalParameter(org_id="org-test", parameter_key="inventory.allow_negative_stock", parameter_value="true", value_type="boolean"))
    receive(db, ctx, md, "2", "5")
    post_stock_transaction(db, ctx, source_type="manual", source_id="x", warehouse_id=md.wh.id, material_id=md.mat.id, quantity=Decimal("3"), direction="out")
    assert _stock(db, md).quantity == Decimal("-1")
    # inbound after negative balance restarts average from the receipt cost
    post_stock_transaction(db, ctx, source_type="manual", source_id="y", warehouse_id=md.wh.id, material_id=md.mat.id, quantity=Decimal("5"), direction="in", unit_cost=Decimal("9"))
    assert _stock(db, md).average_cost == Decimal("9")


def test_runtime_migration_adds_parameter_only(db, ctx):
    from app.services.runtime_migrations import ensure_negative_stock_parameter
    db.add(CfgGlobalParameter(org_id="org-test", parameter_key="inventory.costing_method", parameter_value="weighted_average"))
    db.commit()
    ensure_negative_stock_parameter(db); ensure_negative_stock_parameter(db)
    rows = db.scalars(select(CfgGlobalParameter).where(CfgGlobalParameter.parameter_key == "inventory.allow_negative_stock")).all()
    assert len(rows) == 1 and rows[0].parameter_value == "false"
