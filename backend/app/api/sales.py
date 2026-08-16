from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.response import ok
from app.schemas.sales import SalesOrderCreate, SalesQuoteCreate, SalesReturnCreate
from app.services.auth_service import UserContext
from app.services.sales_service import (
    approve_sales_order,
    convert_quote_to_order,
    create_delivery_from_order,
    create_sales_order,
    create_sales_return,
    delete_sales_order,
    list_sales_orders,
    serialize_order,
    submit_sales_order,
    update_sales_order,
)
from app.services.finance_service import create_receivable_from_sales_delivery
from app.services.inventory_service import complete_sales_delivery
from app.services.business_extension_service import complete_sales_return, create_quote, delete_sales_return, list_quotes, list_sales_returns, serialize_quote, submit_sales_return, transition_quote, update_sales_return
from app.services.workflow_service import has_running_workflow, start_workflow_if_active

router = APIRouter(prefix="/api/sales", tags=["sales"])


@router.get("/orders")
def list_orders(
    status: str | None = Query(default=None),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(list_sales_orders(db, context, status))


@router.post("/orders")
def create_order(payload: SalesOrderCreate, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    return ok(serialize_order(create_sales_order(db, payload, context)))


@router.put("/orders/{order_id}")
def update_order(order_id: str, payload: SalesOrderCreate, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    return ok(serialize_order(update_sales_order(db, order_id, payload, context)))


@router.delete("/orders/{order_id}")
def delete_order(order_id: str, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    delete_sales_order(db, order_id, context)
    return ok(msg="销售订单已删除")


@router.post("/orders/{order_id}/submit")
def submit_order(order_id: str, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    result = submit_sales_order(db, order_id, context)
    start_workflow_if_active(db, "sales_order", order_id, context)
    db.commit()
    return ok(serialize_order(result))


@router.post("/orders/{order_id}/approve")
def approve_order(order_id: str, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    if has_running_workflow(db, "sales_order", order_id, context):
        raise AppError("该单据已进入审批流，请在我的待办中处理", code=409)
    return ok(serialize_order(approve_sales_order(db, order_id, context)))


@router.post("/orders/{order_id}/create-delivery")
def create_delivery(order_id: str, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    delivery = create_delivery_from_order(db, order_id, context)
    return ok({"id": delivery.id, "doc_no": delivery.doc_no, "status": delivery.status})


@router.post("/returns")
def create_return(payload: SalesReturnCreate, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    result = create_sales_return(db, payload, context)
    return ok({"id": result.id, "doc_no": result.doc_no, "status": result.status})


@router.put("/returns/{return_id}")
def update_return(return_id: str, payload: SalesReturnCreate, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    result = update_sales_return(db, return_id, payload, context)
    return ok({"id": result.id, "doc_no": result.doc_no, "status": result.status})


@router.delete("/returns/{return_id}")
def delete_return(return_id: str, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    delete_sales_return(db, return_id, context)
    return ok(msg="销售退货单已删除")


@router.get("/quotes")
def quotes(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_quotes(db, context))


@router.post("/quotes")
def add_quote(payload: SalesQuoteCreate, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    return ok(serialize_quote(create_quote(db, payload, context)))


@router.post("/quotes/{quote_id}/convert")
def convert_quote(quote_id: str, payload: dict, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    order = convert_quote_to_order(db, quote_id, str(payload.get("warehouse_id") or ""), context)
    return ok(serialize_order(order), "报价单已转为销售订单")


@router.post("/quotes/{quote_id}/{action}")
def quote_action(quote_id: str, action: str, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    status = {"submit": "submitted", "approve": "approved", "reject": "rejected"}.get(action)
    if status is None:
        raise AppError("不支持的报价单操作", code=400)
    return ok(serialize_quote(transition_quote(db, quote_id, status, context)))


@router.get("/returns")
def sales_returns(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_sales_returns(db, context))


@router.post("/returns/{return_id}/submit")
def submit_return(return_id: str, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    row = submit_sales_return(db, return_id, context); db.commit(); return ok({"id": row.id, "status": row.status})


@router.post("/returns/{return_id}/complete")
def complete_return(return_id: str, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    row = complete_sales_return(db, return_id, context); db.commit(); return ok({"id": row.id, "status": row.status})


@router.post("/deliveries/{delivery_id}/complete")
def complete_delivery(delivery_id: str, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    delivery = complete_sales_delivery(db, delivery_id, context)
    receivable = create_receivable_from_sales_delivery(db, delivery.id, context)
    db.commit()
    return ok({"delivery_id": delivery.id, "status": delivery.status, "receivable_id": receivable.id})
