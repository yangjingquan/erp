"""GAP-01: receipt/delivery completion writes back order quantities and status."""
from decimal import Decimal

import pytest

from app.core.exceptions import AppError
from app.models.purchase import PurchaseOrder
from app.models.sales import SalesOrder
from app.services.inventory_service import complete_purchase_receipt, complete_sales_delivery
from app.services.purchase_service import create_receipt_from_order
from app.services.sales_service import create_delivery_from_order
from tests.gap_helpers import approved_purchase_order, approved_sales_order, receive


def test_full_receipt_completes_purchase_order(db, ctx, md):
    order, _ = receive(db, ctx, md, "10", "5")
    order = db.get(PurchaseOrder, order.id)
    assert order.items[0].received_quantity == Decimal("10")
    assert order.status == "completed"
    with pytest.raises(AppError):
        create_receipt_from_order(db, order.id, ctx)


def test_partial_receipt_then_rest(db, ctx, md):
    order = approved_purchase_order(db, ctx, md, "10", "5")
    receipt = create_receipt_from_order(db, order.id, ctx)
    receipt.items[0].quantity = Decimal("4")
    db.commit()
    with pytest.raises(AppError):  # draft receipt still open
        create_receipt_from_order(db, order.id, ctx)
    complete_purchase_receipt(db, receipt.id, ctx); db.commit()
    order = db.get(PurchaseOrder, order.id)
    assert order.status == "partially_received"
    assert order.items[0].received_quantity == Decimal("4")
    second = create_receipt_from_order(db, order.id, ctx)
    assert second.items[0].quantity == Decimal("6")
    assert second.total_amount == Decimal("30.00")
    complete_purchase_receipt(db, second.id, ctx); db.commit()
    assert db.get(PurchaseOrder, order.id).status == "completed"


def test_delivery_writeback(db, ctx, md):
    receive(db, ctx, md, "10", "5")
    order = approved_sales_order(db, ctx, md, "4", "20")
    delivery = create_delivery_from_order(db, order.id, ctx)
    delivery.items[0].quantity = Decimal("1"); db.commit()
    complete_sales_delivery(db, delivery.id, ctx); db.commit()
    order = db.get(SalesOrder, order.id)
    assert order.status == "partially_delivered"
    assert order.items[0].delivered_quantity == Decimal("1")
    rest = create_delivery_from_order(db, order.id, ctx)
    complete_sales_delivery(db, rest.id, ctx); db.commit()
    order = db.get(SalesOrder, order.id)
    assert order.status == "completed" and order.items[0].delivered_quantity == Decimal("4")
