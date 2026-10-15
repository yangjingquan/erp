"""GAP-05: 退货完成冲减应收/应付并生成反向凭证."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models.finance import PurchasePayable, SalesReceivable
from app.schemas.purchase import PurchaseReturnCreate
from app.schemas.sales import SalesReturnCreate
from app.services.business_extension_service import (
    complete_purchase_return, complete_sales_return, create_purchase_return, submit_purchase_return, submit_sales_return,
)
from app.services.finance_service import create_payable_from_purchase_receipt, create_receivable_from_sales_delivery
from app.services.inventory_service import complete_sales_delivery
from app.services.sales_service import create_delivery_from_order, create_sales_return
from tests.gap_helpers import approved_sales_order, receive, voucher_lines


def test_sales_return_offsets_receivable(db, ctx, md):
    receive(db, ctx, md, "10", "5")
    order = approved_sales_order(db, ctx, md, "4", "20")
    delivery = create_delivery_from_order(db, order.id, ctx)
    complete_sales_delivery(db, delivery.id, ctx)
    ar = create_receivable_from_sales_delivery(db, delivery.id, ctx)
    db.commit()
    ret = create_sales_return(db, SalesReturnCreate(source_delivery_id=delivery.id, customer_id=md.cus.id, warehouse_id=md.wh.id, return_date=date.today(), items=[{"material_id": md.mat.id, "quantity": "1", "unit_price": "20"}]), ctx)
    submit_sales_return(db, ret.id, ctx)
    complete_sales_return(db, ret.id, ctx)
    red = db.scalar(select(SalesReceivable).where(SalesReceivable.source_type == "sales_return"))
    assert red.total_amount == Decimal("-20.00")
    assert ar.total_amount - ar.reconciled_amount == Decimal("60.00")
    assert ar.status == "partial" and red.status == "settled"
    assert voucher_lines(db, "sales_return", ret.id) == {"6001": (Decimal("20"), 0), "1122": (0, Decimal("20"))}


def test_purchase_return_offsets_payable(db, ctx, md):
    _, receipt = receive(db, ctx, md, "10", "5")
    ap = create_payable_from_purchase_receipt(db, receipt.id, ctx)
    db.commit()
    ret = create_purchase_return(db, PurchaseReturnCreate(source_receipt_id=receipt.id, supplier_id=md.sup.id, warehouse_id=md.wh.id, return_date=date.today(), items=[{"material_id": md.mat.id, "quantity": "2", "unit_price": "5"}]), ctx)
    submit_purchase_return(db, ret.id, ctx)
    complete_purchase_return(db, ret.id, ctx)
    red = db.scalar(select(PurchasePayable).where(PurchasePayable.source_type == "purchase_return"))
    assert red.total_amount == Decimal("-10.00")
    assert ap.total_amount - ap.reconciled_amount == Decimal("40.00")
    assert voucher_lines(db, "purchase_return", ret.id) == {"2202": (Decimal("10"), 0), "1403": (0, Decimal("10"))}


def test_return_without_source_creates_open_red_document(db, ctx, md):
    receive(db, ctx, md, "10", "5")
    ret = create_purchase_return(db, PurchaseReturnCreate(supplier_id=md.sup.id, warehouse_id=md.wh.id, return_date=date.today(), items=[{"material_id": md.mat.id, "quantity": "1", "unit_price": "5"}]), ctx)
    submit_purchase_return(db, ret.id, ctx)
    complete_purchase_return(db, ret.id, ctx)
    red = db.scalar(select(PurchasePayable).where(PurchasePayable.source_type == "purchase_return"))
    assert red.status == "open" and red.total_amount == Decimal("-5.00")
