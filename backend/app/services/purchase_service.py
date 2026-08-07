from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.purchase import PurchaseOrder, PurchaseOrderItem, PurchaseReceipt, PurchaseReceiptItem
from app.services.auth_service import UserContext
from app.services.configuration_service import next_doc_no


def _total(items) -> Decimal:
    return sum((item.quantity * item.unit_price for item in items), Decimal("0")).quantize(Decimal("0.01"))


def serialize_order(order: PurchaseOrder) -> dict:
    return {
        "id": order.id,
        "doc_no": order.doc_no,
        "supplier_id": order.supplier_id,
        "owner_id": order.owner_id,
        "status": order.status,
        "order_date": order.order_date.isoformat(),
        "expected_date": order.expected_date.isoformat() if order.expected_date else None,
        "total_amount": str(order.total_amount),
        "payable_amount": str(order.payable_amount),
        "items": [
            {
                "id": item.id,
                "material_id": item.material_id,
                "warehouse_id": item.warehouse_id,
                "quantity": str(item.quantity),
                "received_quantity": str(item.received_quantity),
                "unit_price": str(item.unit_price),
                "amount": str(item.amount),
            }
            for item in order.items
        ],
    }


def list_purchase_orders(db: Session, context: UserContext, status: str | None = None) -> list[dict]:
    statement = (
        select(PurchaseOrder)
        .where(PurchaseOrder.org_id == context.org_id, PurchaseOrder.is_deleted.is_(False))
        .order_by(PurchaseOrder.created_at.desc())
    )
    if status:
        statement = statement.where(PurchaseOrder.status == status)
    return [serialize_order(order) for order in db.scalars(statement).all()]


def create_purchase_order(db: Session, payload, context: UserContext) -> PurchaseOrder:
    order = PurchaseOrder(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "purchase_order", context.org_id, payload.order_date),
        supplier_id=payload.supplier_id,
        owner_id=context.id,
        department_id=context.department_id,
        status="draft",
        order_date=payload.order_date,
        expected_date=payload.expected_date,
        created_by=context.id,
    )
    order.items = [
        PurchaseOrderItem(
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
    order.payable_amount = order.total_amount
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def _transition(db: Session, order_id: str, context: UserContext, expected: str, new_status: str) -> PurchaseOrder:
    order = db.get(PurchaseOrder, order_id)
    if order is None or order.org_id != context.org_id:
        raise AppError("采购订单不存在", code=404)
    if order.status != expected:
        raise AppError(f"采购订单状态 {order.status} 不允许此操作", code=400)
    order.status = new_status
    order.updated_by = context.id
    db.commit()
    db.refresh(order)
    return order


def submit_purchase_order(db: Session, order_id: str, context: UserContext) -> PurchaseOrder:
    return _transition(db, order_id, context, "draft", "submitted")


def approve_purchase_order(db: Session, order_id: str, context: UserContext) -> PurchaseOrder:
    return _transition(db, order_id, context, "submitted", "approved")


def create_receipt_from_order(db: Session, order_id: str, context: UserContext) -> PurchaseReceipt:
    order = db.get(PurchaseOrder, order_id)
    if order is None or order.org_id != context.org_id:
        raise AppError("采购订单不存在", code=404)
    if order.status != "approved":
        raise AppError("只有已审核订单才能入库", code=400)
    if db.scalar(select(PurchaseReceipt).where(PurchaseReceipt.order_id == order.id, PurchaseReceipt.status != "cancelled")):
        raise AppError("该订单已创建入库单", code=409)
    receipt = PurchaseReceipt(
        org_id=order.org_id,
        doc_no=next_doc_no(db, "purchase_receipt", context.org_id, order.order_date),
        order_id=order.id,
        supplier_id=order.supplier_id,
        warehouse_id=next((item.warehouse_id for item in order.items if item.warehouse_id), "warehouse-1"),
        status="draft",
        receipt_date=date.today(),
        total_amount=order.total_amount,
    )
    receipt.items = [
        PurchaseReceiptItem(
            order_item_id=item.id,
            material_id=item.material_id,
            quantity=item.quantity - item.received_quantity,
            unit_price=item.unit_price,
            amount=item.amount,
        )
        for item in order.items
        if item.quantity > item.received_quantity
    ]
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return receipt
