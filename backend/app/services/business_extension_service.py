from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_now, local_today
from app.models.business_extensions import PurchaseRequest, PurchaseRequestItem, PurchaseReturnItem, SalesQuote, SalesQuoteItem, SalesReturnItem
from app.models.purchase import PurchaseReceipt, PurchaseReturn
from app.models.sales import SalesDelivery, SalesReturn
from app.services.auth_service import UserContext
from app.services.configuration_service import next_doc_no


def _total(items) -> Decimal:
    return sum((item.quantity * getattr(item, "unit_price", getattr(item, "estimated_price", 0)) for item in items), Decimal("0")).quantize(Decimal("0.01"))


def _serialize_items(items, price_key="unit_price"):
    return [{"id": item.id, "material_id": item.material_id, "quantity": str(item.quantity), price_key: str(getattr(item, price_key)), "amount": str(getattr(item, "amount", Decimal("0")))} for item in items]


def serialize_quote(row):
    return {"id": row.id, "doc_no": row.doc_no, "customer_id": row.customer_id, "status": row.status, "quote_date": row.quote_date.isoformat(), "valid_until": row.valid_until.isoformat() if row.valid_until else None, "total_amount": str(row.total_amount), "items": _serialize_items(row.items)}


def list_quotes(db: Session, context: UserContext):
    rows = db.scalars(select(SalesQuote).where(SalesQuote.org_id == context.org_id, SalesQuote.is_deleted.is_(False)).order_by(SalesQuote.created_at.desc())).all()
    return [serialize_quote(row) for row in rows]


def create_quote(db: Session, payload, context: UserContext):
    row = SalesQuote(org_id=context.org_id, doc_no=next_doc_no(db, "sales_quote", context.org_id, payload.quote_date), customer_id=payload.customer_id, owner_id=context.id, quote_date=payload.quote_date, valid_until=payload.valid_until, created_by=context.id)
    row.items = [SalesQuoteItem(material_id=item.material_id, quantity=item.quantity, unit_price=item.unit_price, tax_rate=item.tax_rate, amount=(item.quantity * item.unit_price).quantize(Decimal("0.01")), line_no=index) for index, item in enumerate(payload.items, 1)]
    row.total_amount = _total(row.items)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def transition_quote(db: Session, quote_id: str, new_status: str, context: UserContext):
    row = db.get(SalesQuote, quote_id)
    if row is None or row.org_id != context.org_id:
        raise AppError("报价单不存在", code=404)
    allowed = {"draft": {"submitted"}, "submitted": {"approved", "rejected"}}
    if new_status not in allowed.get(row.status, set()):
        raise AppError(f"报价单状态 {row.status} 不允许此操作", code=400)
    row.status = new_status
    row.updated_by = context.id
    db.commit()
    db.refresh(row)
    return row


def serialize_request(row):
    items = _serialize_items(row.items, "estimated_price")
    return {"id": row.id, "doc_no": row.doc_no, "department_id": row.department_id, "requester_id": row.requester_id, "supplier_id": row.supplier_id, "status": row.status, "request_date": row.request_date.isoformat(), "remark": row.remark, "created_at": row.created_at.isoformat(timespec="seconds"), "total_amount": str(_total(row.items)), "items": items}


def list_requests(db: Session, context: UserContext):
    rows = db.scalars(select(PurchaseRequest).where(PurchaseRequest.org_id == context.org_id).order_by(PurchaseRequest.created_at.desc())).all()
    return [serialize_request(row) for row in rows]


def create_request(db: Session, payload, context: UserContext):
    now = local_now()
    row = PurchaseRequest(org_id=context.org_id, doc_no=next_doc_no(db, "purchase_request", context.org_id, payload.request_date), department_id=context.department_id, requester_id=context.id, supplier_id=payload.supplier_id, request_date=payload.request_date, remark=payload.remark, created_by=context.id, created_at=now, updated_at=now)
    row.items = [PurchaseRequestItem(material_id=item.material_id, quantity=item.quantity, estimated_price=item.estimated_price, line_no=index) for index, item in enumerate(payload.items, 1)]
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_request(db: Session, request_id: str, payload, context: UserContext):
    row = db.get(PurchaseRequest, request_id)
    if row is None or row.org_id != context.org_id:
        raise AppError("采购申请不存在", code=404)
    if row.status != "draft":
        raise AppError("只有草稿状态的采购申请可以修改", code=400)
    row.supplier_id = payload.supplier_id
    row.request_date = payload.request_date
    row.remark = payload.remark
    row.items = [
        PurchaseRequestItem(
            material_id=item.material_id,
            quantity=item.quantity,
            estimated_price=item.estimated_price,
            line_no=index,
        )
        for index, item in enumerate(payload.items, 1)
    ]
    row.version += 1
    row.updated_at = local_now()
    db.commit()
    db.refresh(row)
    return row


def delete_request(db: Session, request_id: str, context: UserContext) -> None:
    row = db.get(PurchaseRequest, request_id)
    if row is None or row.org_id != context.org_id:
        raise AppError("采购申请不存在", code=404)
    if row.status != "draft":
        raise AppError("只有草稿状态的采购申请可以删除", code=400)
    db.delete(row)
    db.commit()


def transition_request(db: Session, request_id: str, new_status: str, context: UserContext):
    row = db.get(PurchaseRequest, request_id)
    if row is None or row.org_id != context.org_id:
        raise AppError("采购申请不存在", code=404)
    allowed = {"draft": {"submitted"}, "submitted": {"approved", "rejected"}}
    if new_status not in allowed.get(row.status, set()):
        raise AppError(f"采购申请状态 {row.status} 不允许此操作", code=400)
    row.status = new_status
    row.updated_at = local_now()
    db.commit()
    db.refresh(row)
    return row


def serialize_return(row):
    return {"id": row.id, "doc_no": row.doc_no, "status": row.status, "return_date": row.return_date.isoformat(), "created_at": row.created_at.isoformat(timespec="seconds"), "total_amount": str(row.total_amount), "customer_id": getattr(row, "customer_id", None), "supplier_id": getattr(row, "supplier_id", None), "warehouse_id": getattr(row, "warehouse_id", None), "source_delivery_id": getattr(row, "source_delivery_id", None), "source_receipt_id": getattr(row, "source_receipt_id", None), "items": _serialize_items(row.items)}


def list_sales_returns(db: Session, context: UserContext):
    rows = db.scalars(select(SalesReturn).where(SalesReturn.org_id == context.org_id, SalesReturn.is_deleted.is_(False)).order_by(SalesReturn.created_at.desc())).all()
    return [serialize_return(row) for row in rows]


def list_purchase_returns(db: Session, context: UserContext):
    rows = db.scalars(select(PurchaseReturn).where(PurchaseReturn.org_id == context.org_id, PurchaseReturn.is_deleted.is_(False)).order_by(PurchaseReturn.created_at.desc())).all()
    return [serialize_return(row) for row in rows]


def create_return_items(row, items, item_model):
    row.items = [item_model(material_id=item.material_id, quantity=item.quantity, unit_price=item.unit_price, amount=(item.quantity * item.unit_price).quantize(Decimal("0.01"))) for item in items]
    row.total_amount = _total(row.items)


def create_purchase_return(db: Session, payload, context: UserContext):
    if payload.source_receipt_id:
        receipt = db.scalar(select(PurchaseReceipt).where(PurchaseReceipt.id == payload.source_receipt_id, PurchaseReceipt.org_id == context.org_id, PurchaseReceipt.status == "completed"))
        if receipt is None:
            raise AppError("来源采购入库单不存在或未完成", code=400)
        received = {item.material_id: item.quantity for item in receipt.items}
        for item in payload.items:
            if item.quantity > received.get(item.material_id, 0):
                raise AppError(f"退货数量超过已入库数量：{item.material_id}", code=400)
    row = PurchaseReturn(org_id=context.org_id, doc_no=next_doc_no(db, "purchase_return", context.org_id, payload.return_date or local_today()), source_receipt_id=payload.source_receipt_id, supplier_id=payload.supplier_id, warehouse_id=payload.warehouse_id, return_date=payload.return_date or local_today(), created_by=context.id)
    create_return_items(row, payload.items, PurchaseReturnItem)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_purchase_return(db: Session, return_id: str, payload, context: UserContext):
    row = db.get(PurchaseReturn, return_id)
    if row is None or row.org_id != context.org_id or row.is_deleted:
        raise AppError("采购退货单不存在", code=404)
    if row.status != "draft":
        raise AppError("只有草稿状态的采购退货单可以修改", code=400)
    if payload.source_receipt_id:
        receipt = db.scalar(select(PurchaseReceipt).where(PurchaseReceipt.id == payload.source_receipt_id, PurchaseReceipt.org_id == context.org_id, PurchaseReceipt.status == "completed"))
        if receipt is None:
            raise AppError("来源采购入库单不存在或未完成", code=400)
        received = {item.material_id: item.quantity for item in receipt.items}
        for item in payload.items:
            if item.quantity > received.get(item.material_id, 0):
                raise AppError(f"退货数量超过已入库数量：{item.material_id}", code=400)
    row.source_receipt_id = payload.source_receipt_id
    row.supplier_id = payload.supplier_id
    row.warehouse_id = payload.warehouse_id
    row.return_date = payload.return_date or local_today()
    create_return_items(row, payload.items, PurchaseReturnItem)
    row.version += 1
    db.commit()
    db.refresh(row)
    return row


def _validate_sales_return_source(db: Session, payload, context: UserContext) -> None:
    if not payload.source_delivery_id:
        return
    delivery = db.scalar(select(SalesDelivery).where(SalesDelivery.id == payload.source_delivery_id, SalesDelivery.org_id == context.org_id, SalesDelivery.status == "completed"))
    if delivery is None:
        any_delivery = db.scalar(select(SalesDelivery).where(SalesDelivery.id == payload.source_delivery_id, SalesDelivery.org_id == context.org_id))
        if any_delivery is not None and not payload.items:
            raise AppError("已完成出库单的退货必须提供有效退货明细", code=400)
        raise AppError("来源销售出库单不存在或未完成", code=400)
    if not payload.items:
        raise AppError("已完成出库单的退货必须提供有效退货明细", code=400)
    delivered = {item.material_id: item.quantity for item in delivery.items}
    for item in payload.items:
        if item.quantity > delivered.get(item.material_id, 0):
            raise AppError(f"退货数量超过已出库数量：{item.material_id}", code=400)


def update_sales_return(db: Session, return_id: str, payload, context: UserContext):
    row = db.scalar(select(SalesReturn).where(SalesReturn.id == return_id, SalesReturn.org_id == context.org_id, SalesReturn.is_deleted.is_(False)))
    if row is None: raise AppError("销售退货单不存在", code=404)
    if row.status != "draft": raise AppError("只有草稿状态的销售退货单可以修改", code=400)
    _validate_sales_return_source(db, payload, context)
    row.source_delivery_id = payload.source_delivery_id
    row.customer_id = payload.customer_id
    row.warehouse_id = payload.warehouse_id
    row.return_date = payload.return_date or local_today()
    create_return_items(row, payload.items, SalesReturnItem)
    row.version += 1
    db.commit()
    db.refresh(row)
    return row


def delete_sales_return(db: Session, return_id: str, context: UserContext) -> None:
    row = db.get(SalesReturn, return_id)
    if row is None or row.org_id != context.org_id or row.is_deleted:
        raise AppError("销售退货单不存在", code=404)
    if row.status != "draft":
        raise AppError("只有草稿状态的销售退货单可以删除", code=400)
    row.is_deleted = True
    db.commit()


def submit_sales_return(db: Session, return_id: str, context: UserContext):
    row = db.scalar(select(SalesReturn).where(SalesReturn.id == return_id, SalesReturn.org_id == context.org_id, SalesReturn.is_deleted.is_(False)))
    if row is None: raise AppError("销售退货单不存在", code=404)
    if row.status != "draft": raise AppError("只有草稿退货单可以提交", code=400)
    row.status = "submitted"; row.version += 1; db.flush(); return row


def complete_sales_return(db: Session, return_id: str, context: UserContext):
    row = db.scalar(select(SalesReturn).where(SalesReturn.id == return_id, SalesReturn.org_id == context.org_id, SalesReturn.is_deleted.is_(False)))
    if row is None: raise AppError("销售退货单不存在", code=404)
    if row.status != "submitted": raise AppError("只有已提交退货单可以完成", code=400)
    from app.services.inventory_service import post_stock_transaction
    for item in row.items:
        post_stock_transaction(
            db, context, source_type="sales_return", source_id=row.id,
            warehouse_id=row.warehouse_id, material_id=item.material_id,
            quantity=item.quantity, direction="in", unit_cost=item.unit_price,
        )
    row.status = "completed"; row.version += 1; db.flush(); return row


def submit_purchase_return(db: Session, return_id: str, context: UserContext):
    row = db.scalar(select(PurchaseReturn).where(PurchaseReturn.id == return_id, PurchaseReturn.org_id == context.org_id, PurchaseReturn.is_deleted.is_(False)))
    if row is None: raise AppError("采购退货单不存在", code=404)
    if row.status != "draft": raise AppError("只有草稿退货单可以提交", code=400)
    row.status = "submitted"; row.version += 1; db.flush(); return row


def complete_purchase_return(db: Session, return_id: str, context: UserContext):
    row = db.scalar(select(PurchaseReturn).where(PurchaseReturn.id == return_id, PurchaseReturn.org_id == context.org_id, PurchaseReturn.is_deleted.is_(False)))
    if row is None: raise AppError("采购退货单不存在", code=404)
    if row.status != "submitted": raise AppError("只有已提交退货单可以完成", code=400)
    from app.services.inventory_service import post_stock_transaction
    for item in row.items:
        post_stock_transaction(
            db, context, source_type="purchase_return", source_id=row.id,
            warehouse_id=row.warehouse_id, material_id=item.material_id,
            quantity=item.quantity, direction="out", unit_cost=item.unit_price,
        )
    row.status = "completed"; row.version += 1; db.flush(); return row


def delete_purchase_return(db: Session, return_id: str, context: UserContext) -> None:
    row = db.get(PurchaseReturn, return_id)
    if row is None or row.org_id != context.org_id or row.is_deleted:
        raise AppError("采购退货单不存在", code=404)
    if row.status != "draft":
        raise AppError("只有草稿状态的采购退货单可以删除", code=400)
    row.is_deleted = True
    row.version += 1
    db.commit()
