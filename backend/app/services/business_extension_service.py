from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.business_extensions import PurchaseRequest, PurchaseRequestItem, PurchaseReturnItem, SalesQuote, SalesQuoteItem, SalesReturnItem
from app.models.purchase import PurchaseReturn
from app.models.sales import SalesReturn
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
    return {"id": row.id, "doc_no": row.doc_no, "department_id": row.department_id, "requester_id": row.requester_id, "status": row.status, "request_date": row.request_date.isoformat(), "remark": row.remark, "items": _serialize_items(row.items, "estimated_price")}


def list_requests(db: Session, context: UserContext):
    rows = db.scalars(select(PurchaseRequest).where(PurchaseRequest.org_id == context.org_id).order_by(PurchaseRequest.created_at.desc())).all()
    return [serialize_request(row) for row in rows]


def create_request(db: Session, payload, context: UserContext):
    now = datetime.now(UTC).replace(tzinfo=None)
    row = PurchaseRequest(org_id=context.org_id, doc_no=next_doc_no(db, "purchase_request", context.org_id, payload.request_date), department_id=context.department_id, requester_id=context.id, request_date=payload.request_date, remark=payload.remark, created_by=context.id, created_at=now, updated_at=now)
    row.items = [PurchaseRequestItem(material_id=item.material_id, quantity=item.quantity, estimated_price=item.estimated_price, line_no=index) for index, item in enumerate(payload.items, 1)]
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def transition_request(db: Session, request_id: str, new_status: str, context: UserContext):
    row = db.get(PurchaseRequest, request_id)
    if row is None or row.org_id != context.org_id:
        raise AppError("采购申请不存在", code=404)
    allowed = {"draft": {"submitted"}, "submitted": {"approved", "rejected"}}
    if new_status not in allowed.get(row.status, set()):
        raise AppError(f"采购申请状态 {row.status} 不允许此操作", code=400)
    row.status = new_status
    row.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(row)
    return row


def serialize_return(row):
    return {"id": row.id, "doc_no": row.doc_no, "status": row.status, "return_date": row.return_date.isoformat(), "total_amount": str(row.total_amount), "customer_id": getattr(row, "customer_id", None), "supplier_id": getattr(row, "supplier_id", None), "warehouse_id": row.warehouse_id}


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
    row = PurchaseReturn(org_id=context.org_id, doc_no=next_doc_no(db, "purchase_return", context.org_id, payload.return_date or date.today()), source_receipt_id=payload.source_receipt_id, supplier_id=payload.supplier_id, warehouse_id=payload.warehouse_id, return_date=payload.return_date or date.today(), created_by=context.id)
    create_return_items(row, payload.items, PurchaseReturnItem)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
