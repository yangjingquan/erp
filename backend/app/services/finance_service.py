from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_now, local_today
from app.models.finance import (
    FinExpense,
    FinReceipt,
    FinReceiptReconcile,
    FinPayment,
    FinPaymentReconcile,
    FinVoucher,
    FinVoucherEntry,
    PurchasePayable,
    SalesReceivable,
)
from app.models.purchase import PurchaseReceipt
from app.models.production import MfgSubcontractReceipt
from app.models.sales import SalesDelivery
from app.services.auth_service import UserContext


def _new_finance_doc_no(prefix: str, context: UserContext) -> str:
    """Build a human-readable finance number with a collision-resistant suffix."""
    timestamp = local_now().strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}-{context.id[:8]}-{timestamp}-{uuid4().hex[:8]}"


def create_receivable_from_sales_delivery(db: Session, delivery_id: str, context: UserContext) -> SalesReceivable:
    delivery = db.get(SalesDelivery, delivery_id)
    if delivery is None or delivery.org_id != context.org_id:
        raise AppError("销售出库单不存在", code=404)
    existing = db.scalar(select(SalesReceivable).where(SalesReceivable.source_type == "sales_delivery", SalesReceivable.source_id == delivery.id))
    if existing:
        return existing
    receivable = SalesReceivable(
        org_id=context.org_id,
        doc_no=f"AR-{delivery.doc_no}",
        customer_id=delivery.customer_id,
        source_type="sales_delivery",
        source_id=delivery.id,
        total_amount=delivery.total_amount,
        status="open",
    )
    db.add(receivable)
    db.flush()
    return receivable


def create_payable_from_purchase_receipt(db: Session, receipt_id: str, context: UserContext) -> PurchasePayable:
    receipt = db.get(PurchaseReceipt, receipt_id)
    if receipt is None or receipt.org_id != context.org_id:
        raise AppError("采购入库单不存在", code=404)
    existing = db.scalar(select(PurchasePayable).where(PurchasePayable.source_type == "purchase_receipt", PurchasePayable.source_id == receipt.id))
    if existing:
        return existing
    payable = PurchasePayable(
        org_id=context.org_id,
        doc_no=f"AP-{receipt.doc_no}",
        supplier_id=receipt.supplier_id,
        source_type="purchase_receipt",
        source_id=receipt.id,
        total_amount=receipt.total_amount,
        status="open",
    )
    db.add(payable)
    db.flush()
    return payable


def create_payable_from_subcontract_receipt(
    db: Session, receipt_id: str, context: UserContext
) -> PurchasePayable:
    receipt = db.get(MfgSubcontractReceipt, receipt_id)
    if receipt is None or receipt.org_id != context.org_id:
        raise AppError("委外收货单不存在", code=404)
    existing = db.scalar(
        select(PurchasePayable).where(
            PurchasePayable.org_id == context.org_id,
            PurchasePayable.source_type == "subcontract_receipt",
            PurchasePayable.source_id == receipt.id,
        )
    )
    if existing:
        return existing
    payable = PurchasePayable(
        org_id=context.org_id,
        doc_no=f"AP-{receipt.doc_no}",
        supplier_id=receipt.subcontract_order.supplier_id,
        source_type="subcontract_receipt",
        source_id=receipt.id,
        total_amount=receipt.processing_fee_amount,
        status="open",
    )
    try:
        with db.begin_nested():
            db.add(payable)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(PurchasePayable).where(
                PurchasePayable.org_id == context.org_id,
                PurchasePayable.source_type == "subcontract_receipt",
                PurchasePayable.source_id == receipt.id,
            )
        )
        if existing is None:
            raise
        return existing
    return payable


def create_receipt(db: Session, context: UserContext, *, customer_id: str, amount: Decimal) -> FinReceipt:
    if amount <= 0:
        raise AppError("收款金额必须大于 0", code=400)
    receipt = FinReceipt(
        org_id=context.org_id,
        doc_no=_new_finance_doc_no("RC", context),
        customer_id=customer_id,
        amount=amount,
        receipt_date=local_today(),
        status="confirmed",
    )
    db.add(receipt)
    db.flush()
    return receipt


def reconcile_receivable(db: Session, receipt_id: str, receivable_id: str, amount: Decimal, context: UserContext) -> None:
    receipt = db.get(FinReceipt, receipt_id)
    receivable = db.get(SalesReceivable, receivable_id)
    if receipt is None or receivable is None or receipt.org_id != context.org_id or receivable.org_id != context.org_id:
        raise AppError("收款或应收单不存在", code=404)
    if receipt.customer_id != receivable.customer_id:
        raise AppError("收款客户与应收客户不一致", code=400)
    amount = Decimal(str(amount))
    if amount <= 0 or amount > receivable.total_amount - receivable.reconciled_amount or amount > receipt.amount - sum(item.amount for item in receipt.reconciles):
        raise AppError("核销金额超过可核销余额", code=400)
    existing = db.scalar(
        select(FinReceiptReconcile).where(
            FinReceiptReconcile.receipt_id == receipt.id,
            FinReceiptReconcile.receivable_id == receivable.id,
        )
    )
    if existing:
        existing.amount += amount
    else:
        db.add(FinReceiptReconcile(receipt_id=receipt.id, receivable_id=receivable.id, amount=amount))
    receivable.reconciled_amount += amount
    receivable.status = "settled" if receivable.reconciled_amount == receivable.total_amount else "partial"
    receipt_reconciled = sum(item.amount for item in receipt.reconciles) + amount
    receipt.status = "settled" if receipt_reconciled == receipt.amount else "partial"
    db.flush()


def create_payment(db: Session, context: UserContext, *, supplier_id: str, amount: Decimal) -> FinPayment:
    if amount <= 0:
        raise AppError("付款金额必须大于 0", code=400)
    payment = FinPayment(
        org_id=context.org_id,
        doc_no=_new_finance_doc_no("PY", context),
        supplier_id=supplier_id,
        amount=amount,
        payment_date=local_today(),
        status="confirmed",
    )
    db.add(payment)
    db.flush()
    return payment


def reconcile_payable(db: Session, payment_id: str, payable_id: str, amount: Decimal, context: UserContext) -> None:
    payment = db.get(FinPayment, payment_id)
    payable = db.get(PurchasePayable, payable_id)
    if payment is None or payable is None or payment.org_id != context.org_id or payable.org_id != context.org_id:
        raise AppError("付款或应付单不存在", code=404)
    if payment.supplier_id != payable.supplier_id:
        raise AppError("付款供应商与应付供应商不一致", code=400)
    amount = Decimal(str(amount))
    payment_reconciled = sum(item.amount for item in payment.reconciles)
    payable_remaining = payable.total_amount - payable.reconciled_amount
    payment_remaining = payment.amount - payment_reconciled
    if amount <= 0 or amount > payable_remaining or amount > payment_remaining:
        raise AppError("核销金额超过可核销余额", code=400)
    existing = db.scalar(
        select(FinPaymentReconcile).where(
            FinPaymentReconcile.payment_id == payment.id,
            FinPaymentReconcile.payable_id == payable.id,
        )
    )
    if existing:
        existing.amount += amount
    else:
        db.add(FinPaymentReconcile(payment_id=payment.id, payable_id=payable.id, amount=amount))
    payable.reconciled_amount += amount
    payable.status = "settled" if payable.reconciled_amount == payable.total_amount else "partial"
    payment_reconciled += amount
    payment.status = "settled" if payment_reconciled == payment.amount else "partial"
    db.flush()


def create_expense(db: Session, context: UserContext, *, amount: Decimal, expense_type: str, description: str = "") -> FinExpense:
    from app.services.cost_service import assert_period_open

    assert_period_open(db, context.org_id, local_today())
    expense = FinExpense(
        org_id=context.org_id,
        doc_no=_new_finance_doc_no("EX", context),
        applicant_id=context.id,
        department_id=context.department_id,
        amount=amount,
        expense_date=local_today(),
        expense_type=expense_type,
        status="draft",
        description=description,
    )
    db.add(expense)
    db.flush()
    return expense


def approve_expense(db: Session, expense_id: str, context: UserContext) -> FinExpense:
    expense = db.get(FinExpense, expense_id)
    if expense is None or expense.org_id != context.org_id:
        raise AppError("报销单不存在", code=404)
    if expense.status != "draft":
        raise AppError("报销单当前不可审核", code=400)
    expense.status = "approved"
    db.flush()
    return expense


def settle_expense(db: Session, expense_id: str, context: UserContext) -> FinExpense:
    expense = db.get(FinExpense, expense_id)
    if expense is None or expense.org_id != context.org_id:
        raise AppError("报销单不存在", code=404)
    if expense.status != "approved":
        raise AppError("报销单必须先审核", code=400)
    expense.status = "settled"
    db.flush()
    return expense


def generate_voucher(db: Session, source_type: str, source_id: str, context: UserContext) -> FinVoucher:
    existing = db.scalar(select(FinVoucher).where(FinVoucher.source_type == source_type, FinVoucher.source_id == source_id))
    if existing:
        return existing
    amount = Decimal("0")
    if source_type == "expense":
        source = db.get(FinExpense, source_id)
        if source is None:
            raise AppError("凭证来源单据不存在", code=404)
        amount = source.amount
        entries = [
            FinVoucherEntry(line_no=1, account_code="6602", account_name="费用", summary="业务费用", debit_amount=amount, credit_amount=0),
            FinVoucherEntry(line_no=2, account_code="1002", account_name="银行存款", summary="费用支付", debit_amount=0, credit_amount=amount),
        ]
    elif source_type == "receipt":
        source = db.get(FinReceipt, source_id)
        if source is None:
            raise AppError("凭证来源单据不存在", code=404)
        amount = source.amount
        entries = [
            FinVoucherEntry(line_no=1, account_code="1002", account_name="银行存款", summary="收到客户款项", debit_amount=amount, credit_amount=0),
            FinVoucherEntry(line_no=2, account_code="1122", account_name="应收账款", summary="收款核销", debit_amount=0, credit_amount=amount),
        ]
    elif source_type == "payment":
        source = db.get(FinPayment, source_id)
        if source is None:
            raise AppError("凭证来源单据不存在", code=404)
        amount = source.amount
        entries = [
            FinVoucherEntry(line_no=1, account_code="2202", account_name="应付账款", summary="付款核销", debit_amount=amount, credit_amount=0),
            FinVoucherEntry(line_no=2, account_code="1002", account_name="银行存款", summary="支付供应商款项", debit_amount=0, credit_amount=amount),
        ]
    else:
        raise AppError("暂不支持该凭证来源", code=400)
    voucher = FinVoucher(
        org_id=context.org_id,
        voucher_no=_new_finance_doc_no("FV", context),
        voucher_date=local_today(),
        period=local_today().strftime("%Y-%m"),
        source_type=source_type,
        source_id=source_id,
        status="draft",
        total_debit=amount,
        total_credit=amount,
    )
    voucher.entries = entries
    db.add(voucher)
    db.flush()
    return voucher


def _money(value: Decimal) -> str:
    return str(value)


def list_receivables(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(
        select(SalesReceivable).where(SalesReceivable.org_id == context.org_id).order_by(SalesReceivable.id.desc())
    ).all()
    return [
        {
            "id": row.id,
            "doc_no": row.doc_no,
            "customer_id": row.customer_id,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "total_amount": _money(row.total_amount),
            "reconciled_amount": _money(row.reconciled_amount),
            "status": row.status,
            "due_date": row.due_date.isoformat() if row.due_date else None,
        }
        for row in rows
    ]


def list_payables(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(
        select(PurchasePayable).where(PurchasePayable.org_id == context.org_id).order_by(PurchasePayable.id.desc())
    ).all()
    return [
        {
            "id": row.id,
            "doc_no": row.doc_no,
            "supplier_id": row.supplier_id,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "total_amount": _money(row.total_amount),
            "reconciled_amount": _money(row.reconciled_amount),
            "status": row.status,
            "due_date": row.due_date.isoformat() if row.due_date else None,
        }
        for row in rows
    ]


def list_receipts(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(FinReceipt).where(FinReceipt.org_id == context.org_id).order_by(FinReceipt.id.desc())).all()
    return [
        {
            "id": row.id,
            "doc_no": row.doc_no,
            "customer_id": row.customer_id,
            "account_name": row.account_name,
            "amount": _money(row.amount),
            "receipt_date": row.receipt_date.isoformat(),
            "status": row.status,
            "reconciled_amount": _money(sum(item.amount for item in row.reconciles)),
        }
        for row in rows
    ]


def list_payments(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(FinPayment).where(FinPayment.org_id == context.org_id).order_by(FinPayment.id.desc())).all()
    return [
        {
            "id": row.id,
            "doc_no": row.doc_no,
            "supplier_id": row.supplier_id,
            "account_name": row.account_name,
            "amount": _money(row.amount),
            "payment_date": row.payment_date.isoformat(),
            "reconciled_amount": _money(sum(item.amount for item in row.reconciles)),
            "status": row.status,
        }
        for row in rows
    ]


def list_expenses(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(FinExpense).where(FinExpense.org_id == context.org_id).order_by(FinExpense.id.desc())).all()
    voucher_source_ids = set(
        db.scalars(
            select(FinVoucher.source_id).where(
                FinVoucher.org_id == context.org_id,
                FinVoucher.source_type == "expense",
            )
        ).all()
    )
    return [
        {
            "id": row.id,
            "doc_no": row.doc_no,
            "applicant_id": row.applicant_id,
            "department_id": row.department_id,
            "amount": _money(row.amount),
            "expense_date": row.expense_date.isoformat(),
            "expense_type": row.expense_type,
            "status": row.status,
            "description": row.description,
            "voucher_generated": row.id in voucher_source_ids,
        }
        for row in rows
    ]


def list_vouchers(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(FinVoucher).where(FinVoucher.org_id == context.org_id).order_by(FinVoucher.id.desc())).all()
    return [
        {
            "id": row.id,
            "voucher_no": row.voucher_no,
            "voucher_date": row.voucher_date.isoformat(),
            "period": row.period,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "status": row.status,
            "total_debit": _money(row.total_debit),
            "total_credit": _money(row.total_credit),
        }
        for row in rows
    ]
