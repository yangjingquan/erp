from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_today
from app.models.sales import SalesDelivery, SalesDeliveryItem, SalesOrder, SalesOrderItem, SalesReturn
from app.services.auth_service import UserContext
from app.services.configuration_service import next_doc_no


def _total(items) -> Decimal:
    return sum((item.quantity * item.unit_price for item in items), Decimal("0")).quantize(Decimal("0.01"))


def serialize_order(order: SalesOrder) -> dict:
    return {
        "id": order.id,
        "doc_no": order.doc_no,
        "customer_id": order.customer_id,
        "owner_id": order.owner_id,
        "status": order.status,
        "order_date": order.order_date.isoformat(),
        "expected_date": order.expected_date.isoformat() if order.expected_date else None,
        "total_amount": str(order.total_amount),
        "receivable_amount": str(order.receivable_amount),
        "remark": order.remark,
        "items": [
            {
                "id": item.id,
                "material_id": item.material_id,
                "warehouse_id": item.warehouse_id,
                "quantity": str(item.quantity),
                "delivered_quantity": str(item.delivered_quantity),
                "unit_price": str(item.unit_price),
                "amount": str(item.amount),
            }
            for item in order.items
        ],
    }


def list_sales_orders(db: Session, context: UserContext, status: str | None = None) -> list[dict]:
    statement = (
        select(SalesOrder)
        .where(SalesOrder.org_id == context.org_id, SalesOrder.is_deleted.is_(False))
        .order_by(SalesOrder.created_at.desc())
    )
    if status:
        statement = statement.where(SalesOrder.status == status)
    return [serialize_order(order) for order in db.scalars(statement).all()]


def create_sales_order(db: Session, payload, context: UserContext) -> SalesOrder:
    order = SalesOrder(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "sales_order", context.org_id, payload.order_date),
        customer_id=payload.customer_id,
        owner_id=context.id,
        department_id=context.department_id,
        status="draft",
        order_date=payload.order_date,
        expected_date=payload.expected_date,
        remark=payload.remark,
        created_by=context.id,
    )
    order.items = [
        SalesOrderItem(
            material_id=item.material_id,
            warehouse_id=item.warehouse_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            tax_rate=item.tax_rate,
            amount=(item.quantity * item.unit_price).quantize(Decimal("0.01")),
            line_no=index,
        )
        for index, item in enumerate(payload.items, start=1)
    ]
    order.total_amount = _total(order.items)
    order.receivable_amount = order.total_amount
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def _transition(db: Session, order_id: str, context: UserContext, expected: str, new_status: str) -> SalesOrder:
    order = db.get(SalesOrder, order_id)
    if order is None or order.org_id != context.org_id:
        raise AppError("销售订单不存在", code=404)
    if order.status != expected:
        raise AppError(f"销售订单状态 {order.status} 不允许此操作", code=400)
    order.status = new_status
    order.updated_by = context.id
    db.commit()
    db.refresh(order)
    return order


def submit_sales_order(db: Session, order_id: str, context: UserContext) -> SalesOrder:
    return _transition(db, order_id, context, "draft", "submitted")


def approve_sales_order(db: Session, order_id: str, context: UserContext) -> SalesOrder:
    return _transition(db, order_id, context, "submitted", "approved")


def create_delivery_from_order(db: Session, order_id: str, context: UserContext) -> SalesDelivery:
    order = db.get(SalesOrder, order_id)
    if order is None or order.org_id != context.org_id:
        raise AppError("销售订单不存在", code=404)
    if order.status != "approved":
        raise AppError("只有已审核订单才能出库", code=400)
    if db.scalar(select(SalesDelivery).where(SalesDelivery.order_id == order.id, SalesDelivery.status != "cancelled")):
        raise AppError("该订单已创建出库单", code=409)
    delivery = SalesDelivery(
        org_id=order.org_id,
        doc_no=next_doc_no(db, "sales_delivery", context.org_id, order.order_date),
        order_id=order.id,
        customer_id=order.customer_id,
        warehouse_id=next((item.warehouse_id for item in order.items if item.warehouse_id), "warehouse-1"),
        status="draft",
        delivery_date=local_today(),
        total_amount=order.total_amount,
    )
    delivery.items = [
        SalesDeliveryItem(
            order_item_id=item.id,
            material_id=item.material_id,
            quantity=item.quantity - item.delivered_quantity,
            unit_price=item.unit_price,
            amount=item.amount,
        )
        for item in order.items
        if item.quantity > item.delivered_quantity
    ]
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery


def create_sales_return(db: Session, payload, context: UserContext) -> SalesReturn:
    if payload.source_delivery_id:
        delivery = db.get(SalesDelivery, payload.source_delivery_id)
        if delivery is None or delivery.org_id != context.org_id:
            raise AppError("来源出库单不存在", code=404)
        if delivery.status == "completed":
            raise AppError("已完成出库单的退货必须走库存退货流程", code=400)
    result = SalesReturn(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "sales_return", context.org_id, payload.return_date or local_today()),
        source_delivery_id=payload.source_delivery_id,
        customer_id=payload.customer_id,
        warehouse_id=payload.warehouse_id,
        status="draft",
        return_date=payload.return_date or local_today(),
    )
    from app.models.business_extensions import SalesReturnItem
    from app.services.business_extension_service import create_return_items
    create_return_items(result, payload.items, SalesReturnItem)
    db.add(result)
    db.commit()
    db.refresh(result)
    return result
