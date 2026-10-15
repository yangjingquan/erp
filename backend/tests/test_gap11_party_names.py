"""GAP-11: 应收/应付/收付款列表返回客户/供应商名称."""
from decimal import Decimal

from app.services.finance_service import (
    create_payable_from_purchase_receipt, create_payment, create_receipt, list_payables, list_payments, list_receipts, list_receivables,
)
from app.services.inventory_service import complete_sales_delivery
from app.services.finance_service import create_receivable_from_sales_delivery
from app.services.sales_service import create_delivery_from_order
from tests.gap_helpers import approved_sales_order, receive


def test_lists_include_party_names(db, ctx, md):
    _, receipt = receive(db, ctx, md, "10", "5")
    create_payable_from_purchase_receipt(db, receipt.id, ctx)
    order = approved_sales_order(db, ctx, md, "1", "9")
    delivery = create_delivery_from_order(db, order.id, ctx)
    complete_sales_delivery(db, delivery.id, ctx)
    create_receivable_from_sales_delivery(db, delivery.id, ctx)
    create_receipt(db, ctx, customer_id=md.cus.id, amount=Decimal("1"))
    create_payment(db, ctx, supplier_id=md.sup.id, amount=Decimal("1"))
    ar = list_receivables(db, ctx)[0]; ap = list_payables(db, ctx)[0]
    assert ar["customer_name"] == "测试客户乙" and ar["customer_code"] == "C1"
    assert ap["supplier_name"] == "测试供应商甲" and ap["supplier_code"] == "S1"
    assert list_receipts(db, ctx)[0]["customer_name"] == "测试客户乙"
    assert list_payments(db, ctx)[0]["supplier_name"] == "测试供应商甲"


def test_frontend_filters_match_name_and_code():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "frontend/src/views/finance"
    assert "row.customer_name, row.customer_code, row.customer_id" in (root / "ReceivableList.vue").read_text(encoding="utf-8")
    assert "row.supplier_name, row.supplier_code, row.supplier_id" in (root / "PayableList.vue").read_text(encoding="utf-8")
