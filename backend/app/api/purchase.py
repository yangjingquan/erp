from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.response import ok
from app.models.purchase import PurchaseReceipt
from app.schemas.purchase import PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseRequestCreate, PurchaseRequestUpdate, PurchaseReturnCreate, PurchaseReturnUpdate
from app.services.auth_service import UserContext
from app.services.purchase_service import (
    approve_purchase_order,
    convert_request_to_order,
    create_purchase_order,
    create_receipt_from_order,
    delete_purchase_order,
    list_purchase_orders,
    serialize_order,
    submit_purchase_order,
    update_purchase_order,
)
from app.services.finance_service import create_payable_from_purchase_receipt
from app.services.inventory_service import complete_purchase_receipt
from app.services.business_extension_service import complete_purchase_return, create_purchase_return, create_request, delete_purchase_return, delete_request, list_purchase_returns, list_requests, serialize_request, serialize_return, submit_purchase_return, transition_request, update_purchase_return, update_request
from app.services.workflow_service import has_running_workflow, start_workflow_if_active

router = APIRouter(prefix="/api/purchase", tags=["purchase"])


@router.get("/orders")
def list_orders(
    status: str | None = Query(default=None),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(list_purchase_orders(db, context, status))


@router.post("/orders")
def create_order(payload: PurchaseOrderCreate, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    return ok(serialize_order(create_purchase_order(db, payload, context)))


@router.put("/orders/{order_id}")
def edit_order(order_id: str, payload: PurchaseOrderUpdate, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    return ok(serialize_order(update_purchase_order(db, order_id, payload, context)))


@router.delete("/orders/{order_id}")
def remove_order(order_id: str, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    delete_purchase_order(db, order_id, context)
    return ok(msg="采购订单已删除")


@router.post("/orders/{order_id}/submit")
def submit_order(order_id: str, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    result = submit_purchase_order(db, order_id, context)
    start_workflow_if_active(db, "purchase_order", order_id, context)
    db.commit()
    return ok(serialize_order(result))


@router.post("/orders/{order_id}/approve")
def approve_order(order_id: str, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    if has_running_workflow(db, "purchase_order", order_id, context):
        raise AppError("该单据已进入审批流，请在我的待办中处理", code=409)
    return ok(serialize_order(approve_purchase_order(db, order_id, context)))


@router.post("/orders/{order_id}/create-receipt")
def create_receipt(order_id: str, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    receipt = create_receipt_from_order(db, order_id, context)
    return ok({"id": receipt.id, "doc_no": receipt.doc_no, "status": receipt.status})


@router.post("/receipts/{receipt_id}/complete")
def complete_receipt(receipt_id: str, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    receipt = complete_purchase_receipt(db, receipt_id, context)
    payable = create_payable_from_purchase_receipt(db, receipt.id, context)
    db.commit()
    return ok({"receipt_id": receipt.id, "status": receipt.status, "payable_id": payable.id})


@router.get("/receipts")
def list_receipts(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(PurchaseReceipt)
        .where(PurchaseReceipt.org_id == context.org_id, PurchaseReceipt.status != "cancelled")
        .order_by(PurchaseReceipt.receipt_date.desc(), PurchaseReceipt.doc_no.desc())
    ).all()
    return ok([
        {
            "id": row.id,
            "doc_no": row.doc_no,
            "status": row.status,
            "receipt_date": row.receipt_date.isoformat(),
            "total_amount": str(row.total_amount),
        }
        for row in rows
    ])


@router.get("/requests")
def requests(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_requests(db, context))


@router.post("/requests")
def add_request(payload: PurchaseRequestCreate, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    return ok(serialize_request(create_request(db, payload, context)))


@router.put("/requests/{request_id}")
def edit_request(request_id: str, payload: PurchaseRequestUpdate, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    return ok(serialize_request(update_request(db, request_id, payload, context)))


@router.delete("/requests/{request_id}")
def remove_request(request_id: str, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    delete_request(db, request_id, context)
    return ok(msg="采购申请已删除")


@router.post("/requests/{request_id}/convert")
def convert_request(request_id: str, payload: dict, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    order = convert_request_to_order(db, request_id, str(payload.get("warehouse_id") or ""), context)
    return ok(serialize_order(order), "采购申请已转为采购订单")


@router.post("/requests/{request_id}/{action}")
def request_action(request_id: str, action: str, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    status = {"submit": "submitted", "approve": "approved", "reject": "rejected"}.get(action)
    if status is None:
        raise AppError("不支持的采购申请操作", code=400)
    return ok(serialize_request(transition_request(db, request_id, status, context)))


@router.get("/returns")
def purchase_returns(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_purchase_returns(db, context))


@router.post("/returns")
def add_purchase_return(payload: PurchaseReturnCreate, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    row = create_purchase_return(db, payload, context)
    return ok({"id": row.id, "doc_no": row.doc_no, "status": row.status})


@router.put("/returns/{return_id}")
def edit_purchase_return(return_id: str, payload: PurchaseReturnUpdate, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    return ok(serialize_return(update_purchase_return(db, return_id, payload, context)))


@router.post("/returns/{return_id}/submit")
def submit_return(return_id: str, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    row = submit_purchase_return(db, return_id, context); db.commit(); return ok({"id": row.id, "status": row.status})


@router.post("/returns/{return_id}/complete")
def complete_return(return_id: str, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    row = complete_purchase_return(db, return_id, context); db.commit(); return ok({"id": row.id, "status": row.status})


@router.delete("/returns/{return_id}")
def remove_purchase_return(return_id: str, context: UserContext = Depends(require_permission("purchase:manage")), db: Session = Depends(get_db)):
    delete_purchase_return(db, return_id, context)
    return ok(msg="采购退货单已删除")
