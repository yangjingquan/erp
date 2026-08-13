from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.finance import (
    AccountCreate,
    AssetCreate,
    BankAccountCreate,
    DepreciationRun,
    DimensionCreate,
    FiscalPeriodCreate,
    ManualVoucherCreate,
    CurrencyCreate,
    ExchangeRateCreate,
)
from app.services.auth_service import UserContext
from app.services.finance_service import (
    approve_expense,
    create_expense,
    create_payment,
    create_receipt,
    generate_voucher,
    list_expenses,
    list_payables,
    list_payments,
    list_receivables,
    list_receipts,
    list_vouchers,
    settle_expense,
    reconcile_payable,
    reconcile_receivable,
)
from app.services.ledger_service import (
    close_fiscal_period,
    create_account,
    create_asset,
    create_bank_account,
    create_dimension,
    create_manual_voucher,
    create_period,
    list_accounts,
    list_assets,
    list_bank_accounts,
    list_dimensions,
    list_periods,
    post_voucher,
    reopen_fiscal_period,
    reverse_voucher,
    run_asset_depreciation,
)
from app.services.currency_service import convert_amount, create_currency, list_currencies, list_exchange_rates, upsert_exchange_rate

router = APIRouter(prefix="/api/finance", tags=["finance"])


@router.get("/currencies")
def currencies(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_currencies(db, context))


@router.post("/currencies")
def currency(payload: CurrencyCreate, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = create_currency(db, payload, context); db.commit()
    return ok({"id": row.id, "code": row.code, "name": row.name, "is_base": row.is_base, "status": row.status})


@router.get("/exchange-rates")
def exchange_rates(currency: str | None = Query(default=None, min_length=3, max_length=8), context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_exchange_rates(db, context, currency))


@router.post("/exchange-rates")
def exchange_rate(payload: ExchangeRateCreate, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = upsert_exchange_rate(db, payload, context); db.commit()
    return ok({"id": row.id, "base_currency": row.base_currency, "quote_currency": row.quote_currency, "rate_date": row.rate_date.isoformat(), "rate": str(row.rate), "source": row.source})


@router.get("/currency-convert")
def currency_convert(amount: Decimal = Query(gt=0), base_currency: str = Query(min_length=3, max_length=8), quote_currency: str = Query(min_length=3, max_length=8), rate_date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"), context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import date
    return ok(convert_amount(db, amount, base_currency, quote_currency, date.fromisoformat(rate_date), context))


@router.get("/accounts")
def accounts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = list_accounts(db, context, page, page_size)
    db.commit()
    return ok(result)


@router.post("/accounts")
def account(payload: AccountCreate, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = create_account(db, payload, context)
    db.commit()
    return ok({"id": row.id, "code": row.code, "name": row.name, "status": row.status})


@router.get("/dimensions")
def dimensions(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_dimensions(db, context))


@router.post("/dimensions")
def dimension(payload: DimensionCreate, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = create_dimension(db, payload, context)
    db.commit()
    return ok({"id": row.id, "code": row.code, "name": row.name, "status": row.status})


@router.get("/periods")
def periods(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    result = list_periods(db, context)
    db.commit()
    return ok(result)


@router.post("/periods")
def period(payload: FiscalPeriodCreate, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = create_period(db, payload, context)
    db.commit()
    return ok({"id": row.id, "period": row.period, "status": row.status})


@router.post("/periods/{period}/close")
def close_period_api(period: str, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = close_fiscal_period(db, period, context)
    db.commit()
    return ok({"id": row.id, "period": row.period, "status": row.status})


@router.post("/periods/{period}/reopen")
def reopen_period_api(period: str, context: UserContext = Depends(require_permission("cost:period:reopen")), db: Session = Depends(get_db)):
    row = reopen_fiscal_period(db, period, context)
    db.commit()
    return ok({"id": row.id, "period": row.period, "status": row.status})


@router.get("/bank-accounts")
def bank_accounts(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_bank_accounts(db, context))


@router.post("/bank-accounts")
def bank_account(payload: BankAccountCreate, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = create_bank_account(db, payload, context)
    db.commit()
    return ok({"id": row.id, "name": row.name, "status": row.status})


@router.get("/assets")
def assets(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_assets(db, context))


@router.post("/assets")
def asset(payload: AssetCreate, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = create_asset(db, payload, context)
    db.commit()
    return ok({"id": row.id, "asset_code": row.asset_code, "status": row.status})


@router.post("/assets/{asset_id}/depreciation")
def depreciate_asset(asset_id: str, payload: DepreciationRun, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = run_asset_depreciation(db, asset_id, payload.period, context)
    db.commit()
    return ok({"id": row.id, "asset_id": row.asset_id, "period": row.period, "amount": str(row.amount), "voucher_id": row.voucher_id})


@router.get("/receivables")
def receivables(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_receivables(db, context))


@router.get("/payables")
def payables(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_payables(db, context))


@router.get("/receipts")
def receipts(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_receipts(db, context))


@router.get("/payments")
def payments(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_payments(db, context))


@router.get("/expenses")
def expenses(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_expenses(db, context))


@router.get("/vouchers")
def vouchers(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_vouchers(db, context))


@router.post("/vouchers")
def manual_voucher(payload: ManualVoucherCreate, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = create_manual_voucher(db, payload, context)
    db.commit()
    return ok({"id": row.id, "voucher_no": row.voucher_no, "status": row.status})


@router.post("/vouchers/{voucher_id}/post")
def post_voucher_api(voucher_id: str, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = post_voucher(db, voucher_id, context)
    db.commit()
    return ok({"id": row.id, "voucher_no": row.voucher_no, "status": row.status})


@router.post("/vouchers/{voucher_id}/reverse")
def reverse_voucher_api(voucher_id: str, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = reverse_voucher(db, voucher_id, context)
    db.commit()
    return ok({"id": row.id, "voucher_no": row.voucher_no, "status": row.status, "reversed_from_id": row.reversed_from_id})


@router.post("/receipts")
def receipt(payload: dict, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = create_receipt(db, context, customer_id=payload["customer_id"], amount=payload["amount"])
    db.commit()
    return ok({"id": row.id, "doc_no": row.doc_no, "status": row.status})


@router.post("/receipts/{receipt_id}/reconcile")
def reconcile_receipt(receipt_id: str, payload: dict, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    reconcile_receivable(db, receipt_id, payload["receivable_id"], payload["amount"], context)
    db.commit()
    return ok(msg="收款核销成功")


@router.post("/payments")
def payment(payload: dict, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = create_payment(db, context, supplier_id=payload["supplier_id"], amount=payload["amount"])
    db.commit()
    return ok({"id": row.id, "doc_no": row.doc_no, "status": row.status})


@router.post("/payments/{payment_id}/reconcile")
def reconcile_payment(payment_id: str, payload: dict, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    reconcile_payable(db, payment_id, payload["payable_id"], payload["amount"], context)
    db.commit()
    return ok(msg="付款核销成功")


@router.post("/expenses")
def expense(payload: dict, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = create_expense(db, context, amount=payload["amount"], expense_type=payload["expense_type"], description=payload.get("description", ""))
    db.commit()
    return ok({"id": row.id, "doc_no": row.doc_no, "status": row.status})


@router.post("/expenses/{expense_id}/approve")
def approve_expense_api(expense_id: str, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = approve_expense(db, expense_id, context)
    db.commit()
    return ok({"id": row.id, "doc_no": row.doc_no, "status": row.status})


@router.post("/expenses/{expense_id}/settle")
def settle_expense_api(expense_id: str, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = settle_expense(db, expense_id, context)
    db.commit()
    return ok({"id": row.id, "doc_no": row.doc_no, "status": row.status})




@router.post("/vouchers/{source_type}/{source_id}")
def voucher(source_type: str, source_id: str, context: UserContext = Depends(require_permission("finance:manage")), db: Session = Depends(get_db)):
    row = generate_voucher(db, source_type, source_id, context)
    db.commit()
    return ok({"id": row.id, "voucher_no": row.voucher_no, "status": row.status})
