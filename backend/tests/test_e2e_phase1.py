from datetime import date
from decimal import Decimal

from app.models.configuration import CfgNumberRule
from app.models.inventory import InvStock
from app.models.master_data import MdMaterial
from app.models.system import SysUser
from app.schemas.purchase import PurchaseOrderCreate, PurchaseOrderItemCreate
from app.schemas.sales import SalesOrderCreate, SalesOrderItemCreate
from app.services.auth_service import UserContext
from app.services.finance_service import (
    create_payable_from_purchase_receipt,
    create_receivable_from_sales_delivery,
    create_receipt,
    generate_voucher,
    reconcile_receivable,
)
from app.services.inventory_service import complete_purchase_receipt, complete_sales_delivery
from app.services.purchase_service import approve_purchase_order, create_purchase_order, create_receipt_from_order, submit_purchase_order
from app.services.sales_service import approve_sales_order, create_delivery_from_order, create_sales_order, submit_sales_order


def test_sales_and_purchase_drive_inventory_finance_and_vouchers(client_and_session):
    _, session = client_and_session
    user = session.query(SysUser).one()
    context = UserContext(user=user, permissions={"*"})
    session.add(MdMaterial(id="material-e2e", org_id=user.org_id, code="E2E-1", name="端到端物料"))
    session.add(InvStock(id="stock-e2e", org_id=user.org_id, warehouse_id="warehouse-1", material_id="material-e2e", quantity=Decimal("20"), available_quantity=Decimal("20")))
    for key, prefix in [("sales_order", "SO"), ("sales_delivery", "SD"), ("purchase_order", "PO"), ("purchase_receipt", "PR")]:
        session.add(CfgNumberRule(id=f"e2e-{key}", org_id=user.org_id, rule_key=key, prefix=prefix, date_format="%Y%m%d", sequence_length=4, reset_cycle="day"))
    session.commit()

    sales_order = create_sales_order(session, SalesOrderCreate(customer_id="customer-e2e", order_date=date(2026, 8, 2), items=[SalesOrderItemCreate(material_id="material-e2e", quantity=Decimal("2"), unit_price=Decimal("50"), warehouse_id="warehouse-1")]), context)
    submit_sales_order(session, sales_order.id, context)
    approve_sales_order(session, sales_order.id, context)
    delivery = create_delivery_from_order(session, sales_order.id, context)
    complete_sales_delivery(session, delivery.id, context)
    receivable = create_receivable_from_sales_delivery(session, delivery.id, context)
    receipt = create_receipt(session, context, customer_id="customer-e2e", amount=Decimal("100"))
    reconcile_receivable(session, receipt.id, receivable.id, Decimal("100"), context)
    sales_voucher = generate_voucher(session, "receipt", receipt.id, context)

    purchase_order = create_purchase_order(session, PurchaseOrderCreate(supplier_id="supplier-e2e", order_date=date(2026, 8, 2), items=[PurchaseOrderItemCreate(material_id="material-e2e", quantity=Decimal("3"), unit_price=Decimal("20"), warehouse_id="warehouse-1")]), context)
    submit_purchase_order(session, purchase_order.id, context)
    approve_purchase_order(session, purchase_order.id, context)
    receipt_doc = create_receipt_from_order(session, purchase_order.id, context)
    complete_purchase_receipt(session, receipt_doc.id, context)
    payable = create_payable_from_purchase_receipt(session, receipt_doc.id, context)

    stock = session.get(InvStock, "stock-e2e")
    assert stock.quantity == Decimal("21.000000")
    assert receivable.status == "settled"
    assert sales_voucher.total_debit == sales_voucher.total_credit
    assert payable.total_amount == Decimal("60.00")
