from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.response import ok
from app.schemas.purchase import PurchaseOrderCreate, PurchaseRequestCreate, PurchaseReturnCreate
from app.services.auth_service import UserContext
from app.services.purchase_service import (
    approve_purchase_order,
    create_purchase_order,
    create_receipt_from_order,
    list_purchase_orders,
    serialize_order,
    submit_purchase_order,
)
from app.services.finance_service import create_payable_from_purchase_receipt
from app.services.inventory_service import complete_purchase_receipt
from app.services.business_extension_service import create_purchase_return, create_request, list_purchase_returns, list_requests, serialize_request, transition_request

router = APIRouter(prefix="/api/purchase", tags=["purchase"])


@router.get("/orders")
def list_orders(
    status: str | None = Query(default=None),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(list_purchase_orders(db, context, status))


@router.post("/orders")
def create_order(payload: PurchaseOrderCreate, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(serialize_order(create_purchase_order(db, payload, context)))


@router.post("/orders/{order_id}/submit")
def submit_order(order_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(serialize_order(submit_purchase_order(db, order_id, context)))


@router.post("/orders/{order_id}/approve")
def approve_order(order_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(serialize_order(approve_purchase_order(db, order_id, context)))


@router.post("/orders/{order_id}/create-receipt")
def create_receipt(order_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    receipt = create_receipt_from_order(db, order_id, context)
    return ok({"id": receipt.id, "doc_no": receipt.doc_no, "status": receipt.status})


@router.post("/receipts/{receipt_id}/complete")
def complete_receipt(receipt_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    receipt = complete_purchase_receipt(db, receipt_id, context)
    payable = create_payable_from_purchase_receipt(db, receipt.id, context)
    db.commit()
    return ok({"receipt_id": receipt.id, "status": receipt.status, "payable_id": payable.id})


@router.get("/requests")
def requests(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_requests(db, context))


@router.post("/requests")
def add_request(payload: PurchaseRequestCreate, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(serialize_request(create_request(db, payload, context)))


@router.post("/requests/{request_id}/{action}")
def request_action(request_id: str, action: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    status = {"submit": "submitted", "approve": "approved", "reject": "rejected"}.get(action)
    if status is None:
        return ok({}, "不支持的采购申请操作")
    return ok(serialize_request(transition_request(db, request_id, status, context)))


@router.get("/returns")
def purchase_returns(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_purchase_returns(db, context))


@router.post("/returns")
def add_purchase_return(payload: PurchaseReturnCreate, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    row = create_purchase_return(db, payload, context)
    return ok({"id": row.id, "doc_no": row.doc_no, "status": row.status})
