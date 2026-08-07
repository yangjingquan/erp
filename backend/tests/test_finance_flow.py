from datetime import date
from decimal import Decimal

import pytest

from app.core.exceptions import AppError
from app.models.finance import FinExpense, FinVoucher, PurchasePayable, SalesReceivable
from app.models.purchase import PurchaseReceipt
from app.models.sales import SalesDelivery
from app.models.system import SysUser
from app.services.auth_service import UserContext
from app.services.finance_service import (
    approve_expense,
    create_expense,
    create_payable_from_purchase_receipt,
    create_receivable_from_sales_delivery,
    create_receipt,
    generate_voucher,
    reconcile_receivable,
    settle_expense,
)


def setup_context(session):
    return UserContext(user=session.query(SysUser).one(), permissions={"*"})


def test_sales_receivable_and_partial_receipt_reconciliation(client_and_session):
    _, session = client_and_session
    user = session.query(SysUser).one()
    delivery = SalesDelivery(
        id="delivery-fin-1",
        org_id=user.org_id,
        doc_no="SD-FIN-1",
        order_id="order-1",
        customer_id="customer-1",
        warehouse_id="warehouse-1",
        status="completed",
        delivery_date=date(2026, 8, 2),
        total_amount=Decimal("100"),
    )
    session.add(delivery)
    session.commit()
    context = setup_context(session)

    receivable = create_receivable_from_sales_delivery(session, delivery.id, context)
    receipt = create_receipt(session, context, customer_id="customer-1", amount=Decimal("40"))
    reconcile_receivable(session, receipt.id, receivable.id, Decimal("40"), context)

    stored = session.get(SalesReceivable, receivable.id)
    assert stored.reconciled_amount == Decimal("40.00")
    assert stored.status == "partial"


def test_over_reconciliation_is_rejected(client_and_session):
    _, session = client_and_session
    user = session.query(SysUser).one()
    delivery = SalesDelivery(
        id="delivery-fin-2", org_id=user.org_id, doc_no="SD-FIN-2", order_id="order-2",
        customer_id="customer-1", warehouse_id="warehouse-1", status="completed",
        delivery_date=date(2026, 8, 2), total_amount=Decimal("100"),
    )
    session.add(delivery)
    session.commit()
    context = setup_context(session)
    receivable = create_receivable_from_sales_delivery(session, delivery.id, context)
    receipt = create_receipt(session, context, customer_id="customer-1", amount=Decimal("101"))

    with pytest.raises(AppError) as error:
        reconcile_receivable(session, receipt.id, receivable.id, Decimal("101"), context)

    assert error.value.code == 400


def test_expense_approval_settlement_and_voucher_idempotency(client_and_session):
    _, session = client_and_session
    context = setup_context(session)
    expense = create_expense(session, context, amount=Decimal("25"), expense_type="travel", description="出差")
    approve_expense(session, expense.id, context)
    settle_expense(session, expense.id, context)
    voucher_one = generate_voucher(session, "expense", expense.id, context)
    voucher_two = generate_voucher(session, "expense", expense.id, context)

    assert session.get(FinExpense, expense.id).status == "settled"
    assert voucher_one.id == voucher_two.id
    assert session.query(FinVoucher).count() == 1
    assert voucher_one.total_debit == voucher_one.total_credit


def test_purchase_payable_can_be_created_from_receipt(client_and_session):
    _, session = client_and_session
    user = session.query(SysUser).one()
    receipt = PurchaseReceipt(
        id="receipt-fin-1", org_id=user.org_id, doc_no="PR-FIN-1", order_id="po-1",
        supplier_id="supplier-1", warehouse_id="warehouse-1", status="completed",
        receipt_date=date(2026, 8, 2), total_amount=Decimal("80"),
    )
    session.add(receipt)
    session.commit()
    payable = create_payable_from_purchase_receipt(session, receipt.id, setup_context(session))

    assert payable.total_amount == Decimal("80.00")
    assert payable.status == "open"


def test_expense_list_returns_created_expense(client_and_session):
    client, session = client_and_session
    context = setup_context(session)
    expense = create_expense(session, context, amount=Decimal("25"), expense_type="travel", description="出差")
    session.commit()

    from app.core.security import create_access_token

    response = client.get(
        "/api/finance/expenses",
        headers={"Authorization": f"Bearer {create_access_token('user-1', ['finance:manage'])}"},
    )

    assert response.json()["code"] == 0
    assert response.json()["data"][0]["id"] == expense.id


def test_expense_api_can_approve_and_settle(client_and_session):
    client, session = client_and_session
    context = setup_context(session)
    expense = create_expense(session, context, amount=Decimal("25"), expense_type="travel")
    session.commit()

    from app.core.security import create_access_token

    headers = {"Authorization": f"Bearer {create_access_token('user-1', ['finance:manage'])}"}
    approved = client.post(f"/api/finance/expenses/{expense.id}/approve", headers=headers)
    settled = client.post(f"/api/finance/expenses/{expense.id}/settle", headers=headers)

    assert approved.json()["code"] == 0
    assert settled.json()["data"]["status"] == "settled"
