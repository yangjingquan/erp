"""Helpers to build business documents for GAP tests."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.schemas.purchase import PurchaseOrderCreate, PurchaseOrderItemCreate
from app.services.purchase_service import approve_purchase_order, create_purchase_order, submit_purchase_order


def approved_purchase_order(db, ctx, md, qty="10", price="5"):
    order = create_purchase_order(db, PurchaseOrderCreate(
        supplier_id=md.sup.id, order_date=date.today(),
        items=[PurchaseOrderItemCreate(material_id=md.mat.id, quantity=Decimal(qty), unit_price=Decimal(price), warehouse_id=md.wh.id)],
    ), ctx)
    submit_purchase_order(db, order.id, ctx)
    return approve_purchase_order(db, order.id, ctx)


def approved_sales_order(db, ctx, md, qty="4", price="20"):
    from app.schemas.sales import SalesOrderCreate, SalesOrderItemCreate
    from app.services.sales_service import approve_sales_order, create_sales_order, submit_sales_order

    order = create_sales_order(db, SalesOrderCreate(
        customer_id=md.cus.id, order_date=date.today(),
        items=[SalesOrderItemCreate(material_id=md.mat.id, quantity=Decimal(qty), unit_price=Decimal(price), warehouse_id=md.wh.id)],
    ), ctx)
    submit_sales_order(db, order.id, ctx)
    return approve_sales_order(db, order.id, ctx)


def receive(db, ctx, md, qty="10", price="5"):
    from app.services.inventory_service import complete_purchase_receipt
    from app.services.purchase_service import create_receipt_from_order

    order = approved_purchase_order(db, ctx, md, qty, price)
    receipt = create_receipt_from_order(db, order.id, ctx)
    complete_purchase_receipt(db, receipt.id, ctx)
    db.commit()
    return order, receipt
