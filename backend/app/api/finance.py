from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
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

router = APIRouter(prefix="/api/finance", tags=["finance"])


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
