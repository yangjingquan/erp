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
    create_delivery_from_order,
    create_sales_order,
    create_sales_return,
    list_sales_orders,
    serialize_order,
    submit_sales_order,
)
from app.services.finance_service import create_receivable_from_sales_delivery
from app.services.inventory_service import complete_sales_delivery
from app.services.business_extension_service import create_quote, list_quotes, list_sales_returns, serialize_quote, transition_quote

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


@router.post("/orders/{order_id}/submit")
def submit_order(order_id: str, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    return ok(serialize_order(submit_sales_order(db, order_id, context)))


@router.post("/orders/{order_id}/approve")
def approve_order(order_id: str, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    return ok(serialize_order(approve_sales_order(db, order_id, context)))


@router.post("/orders/{order_id}/create-delivery")
def create_delivery(order_id: str, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    delivery = create_delivery_from_order(db, order_id, context)
    return ok({"id": delivery.id, "doc_no": delivery.doc_no, "status": delivery.status})


@router.post("/returns")
def create_return(payload: SalesReturnCreate, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    result = create_sales_return(db, payload, context)
    return ok({"id": result.id, "doc_no": result.doc_no, "status": result.status})


@router.get("/quotes")
def quotes(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_quotes(db, context))


@router.post("/quotes")
def add_quote(payload: SalesQuoteCreate, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    return ok(serialize_quote(create_quote(db, payload, context)))


@router.post("/quotes/{quote_id}/{action}")
def quote_action(quote_id: str, action: str, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    status = {"submit": "submitted", "approve": "approved", "reject": "rejected"}.get(action)
    if status is None:
        raise AppError("不支持的报价单操作", code=400)
    return ok(serialize_quote(transition_quote(db, quote_id, status, context)))


@router.get("/returns")
def sales_returns(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_sales_returns(db, context))


@router.post("/deliveries/{delivery_id}/complete")
def complete_delivery(delivery_id: str, context: UserContext = Depends(require_permission("sales:manage")), db: Session = Depends(get_db)):
    delivery = complete_sales_delivery(db, delivery_id, context)
    receivable = create_receivable_from_sales_delivery(db, delivery.id, context)
    db.commit()
    return ok({"delivery_id": delivery.id, "status": delivery.status, "receivable_id": receivable.id})
