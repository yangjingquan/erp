"""GAP-04: 收款/付款/核销生成凭证."""
from decimal import Decimal

from sqlalchemy import select

from app.models.finance import FinVoucher
from app.services.finance_service import (
    create_payable_from_purchase_receipt, create_payment, create_receipt,
    create_receivable_from_sales_delivery, list_payments, list_receipts, reconcile_payable, reconcile_receivable,
)
from app.services.inventory_service import complete_sales_delivery
from app.services.sales_service import create_delivery_from_order
from tests.gap_helpers import approved_sales_order, receive, voucher_lines


def _entries(db, source_type, source_id):
    v = db.scalar(select(FinVoucher).where(FinVoucher.source_type == source_type, FinVoucher.source_id == source_id))
    assert v is not None, f"missing voucher for {source_type}"
    return {(e.account_code, str(e.debit_amount), str(e.credit_amount)) for e in v.entries}, v


def test_receipt_voucher_and_reconcile(db, ctx, md):
    receive(db, ctx, md, "10", "5")
    order = approved_sales_order(db, ctx, md, "2", "50")
    delivery = create_delivery_from_order(db, order.id, ctx)
    complete_sales_delivery(db, delivery.id, ctx)
    ar = create_receivable_from_sales_delivery(db, delivery.id, ctx)
    rc = create_receipt(db, ctx, customer_id=md.cus.id, amount=Decimal("100"))
    assert voucher_lines(db, "receipt", rc.id) == {"1002": (Decimal("100"), 0), "1122": (0, Decimal("100"))}
    reconcile_receivable(db, rc.id, ar.id, Decimal("100"), ctx)
    count = len(db.scalars(select(FinVoucher).where(FinVoucher.source_type == "receipt", FinVoucher.source_id == rc.id)).all())
    assert count == 1  # 核销不重复过账
    assert ar.status == "settled"
    assert list_receipts(db, ctx)[0]["voucher_generated"] is True


def test_payment_voucher_and_reconcile(db, ctx, md):
    _, receipt = receive(db, ctx, md, "10", "5")
    ap = create_payable_from_purchase_receipt(db, receipt.id, ctx)
    py = create_payment(db, ctx, supplier_id=md.sup.id, amount=Decimal("50"))
    assert voucher_lines(db, "payment", py.id) == {"2202": (Decimal("50"), 0), "1002": (0, Decimal("50"))}
    reconcile_payable(db, py.id, ap.id, Decimal("50"), ctx)
    assert ap.status == "settled"
    assert list_payments(db, ctx)[0]["voucher_generated"] is True


def test_reconcile_backfills_missing_voucher(db, ctx, md):
    _, receipt = receive(db, ctx, md, "10", "5")
    ap = create_payable_from_purchase_receipt(db, receipt.id, ctx)
    py = create_payment(db, ctx, supplier_id=md.sup.id, amount=Decimal("20"))
    v = db.scalar(select(FinVoucher).where(FinVoucher.source_type == "payment", FinVoucher.source_id == py.id))
    db.delete(v); db.flush()
    reconcile_payable(db, py.id, ap.id, Decimal("20"), ctx)
    assert db.scalar(select(FinVoucher).where(FinVoucher.source_type == "payment", FinVoucher.source_id == py.id)) is not None
