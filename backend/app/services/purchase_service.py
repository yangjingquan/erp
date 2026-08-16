from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_today
from app.models.master_data import MdMaterial, MdSupplier, MdWarehouse
from app.models.purchase import PurchaseOrder, PurchaseOrderItem, PurchaseReceipt, PurchaseReceiptItem
from app.services.auth_service import UserContext
from app.services.configuration_service import next_doc_no


def _validate_order_payload(db: Session, payload, context: UserContext) -> None:
    supplier = db.scalar(
        select(MdSupplier.id).where(
            MdSupplier.id == payload.supplier_id,
            MdSupplier.org_id == context.org_id,
            MdSupplier.is_deleted.is_(False),
        )
    )
    if supplier is None:
        raise AppError("供应商不存在或已停用", code=404)
    material_ids = {item.material_id for item in payload.items}
    valid_materials = set(db.scalars(
        select(MdMaterial.id).where(
            MdMaterial.org_id == context.org_id,
            MdMaterial.id.in_(material_ids),
            MdMaterial.is_deleted.is_(False),
        )
    ).all())
    if valid_materials != material_ids:
        raise AppError("采购订单包含不存在的物料", code=404)
    warehouse_ids = {item.warehouse_id for item in payload.items if item.warehouse_id}
    if not warehouse_ids:
        raise AppError("采购订单每条明细必须选择仓库", code=422)
    valid_warehouses = set(db.scalars(
        select(MdWarehouse.id).where(
            MdWarehouse.org_id == context.org_id,
            MdWarehouse.id.in_(warehouse_ids),
            MdWarehouse.is_deleted.is_(False),
        )
    ).all())
    if valid_warehouses != warehouse_ids:
        raise AppError("采购订单包含不存在或已停用的仓库", code=404)


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
        "created_at": order.created_at.isoformat(timespec="seconds"),
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
    _validate_order_payload(db, payload, context)
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


def convert_request_to_order(db: Session, request_id: str, warehouse_id: str, context: UserContext) -> PurchaseOrder:
    from app.models.business_extensions import PurchaseRequest
    from app.models.master_data import MdWarehouse
    from app.schemas.purchase import PurchaseOrderCreate, PurchaseOrderItemCreate

    request = db.scalar(
        select(PurchaseRequest).where(
            PurchaseRequest.id == request_id, PurchaseRequest.org_id == context.org_id
        )
    )
    if request is None:
        raise AppError("采购申请不存在", code=404)
    if request.status != "approved":
        raise AppError("只有已审核采购申请可以转采购订单", code=400)
    warehouse = db.scalar(
        select(MdWarehouse.id).where(
            MdWarehouse.id == warehouse_id, MdWarehouse.org_id == context.org_id, MdWarehouse.is_deleted.is_(False)
        )
    )
    if warehouse is None:
        raise AppError("仓库不存在或已停用", code=404)
    if not request.items:
        raise AppError("采购申请没有可转明细", code=400)
    payload = PurchaseOrderCreate(
        supplier_id=request.supplier_id or "",
        order_date=local_today(),
        items=[
            PurchaseOrderItemCreate(
                material_id=item.material_id,
                quantity=item.quantity,
                unit_price=item.estimated_price,
                warehouse_id=warehouse_id,
            )
            for item in request.items
        ],
    )
    if not payload.supplier_id:
        raise AppError("采购申请未指定供应商，无法转采购订单", code=400)
    return create_purchase_order(db, payload, context)


def update_purchase_order(db: Session, order_id: str, payload, context: UserContext) -> PurchaseOrder:
    order = db.get(PurchaseOrder, order_id)
    if order is None or order.org_id != context.org_id or order.is_deleted:
        raise AppError("采购订单不存在", code=404)
    if order.status != "draft":
        raise AppError("只有草稿状态的采购订单可以修改", code=400)
    _validate_order_payload(db, payload, context)
    order.supplier_id = payload.supplier_id
    order.order_date = payload.order_date
    order.expected_date = payload.expected_date
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
    order.updated_by = context.id
    order.version += 1
    db.commit()
    db.refresh(order)
    return order


def delete_purchase_order(db: Session, order_id: str, context: UserContext) -> None:
    order = db.get(PurchaseOrder, order_id)
    if order is None or order.org_id != context.org_id or order.is_deleted:
        raise AppError("采购订单不存在", code=404)
    if order.status != "draft":
        raise AppError("只有草稿状态的采购订单可以删除", code=400)
    order.is_deleted = True
    order.updated_by = context.id
    order.version += 1
    db.commit()


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


def reject_purchase_order(db: Session, order_id: str, context: UserContext) -> PurchaseOrder:
    return _transition(db, order_id, context, "submitted", "draft")


def create_receipt_from_order(db: Session, order_id: str, context: UserContext) -> PurchaseReceipt:
    order = db.get(PurchaseOrder, order_id)
    if order is None or order.org_id != context.org_id:
        raise AppError("采购订单不存在", code=404)
    if order.status != "approved":
        raise AppError("只有已审核订单才能入库", code=400)
    if db.scalar(select(PurchaseReceipt).where(PurchaseReceipt.order_id == order.id, PurchaseReceipt.status != "cancelled")):
        raise AppError("该订单已创建入库单", code=409)
    warehouse_ids = {item.warehouse_id for item in order.items if item.warehouse_id}
    if len(warehouse_ids) != 1:
        raise AppError("采购订单必须指定同一个有效仓库后才能生成入库单", code=422)
    valid_warehouse = db.scalar(
        select(MdWarehouse.id).where(
            MdWarehouse.id == next(iter(warehouse_ids)),
            MdWarehouse.org_id == context.org_id,
            MdWarehouse.is_deleted.is_(False),
        )
    )
    if valid_warehouse is None:
        raise AppError("采购订单指定的仓库不存在或已停用", code=404)
    receipt = PurchaseReceipt(
        org_id=order.org_id,
        doc_no=next_doc_no(db, "purchase_receipt", context.org_id, order.order_date),
        order_id=order.id,
        supplier_id=order.supplier_id,
        warehouse_id=next(iter(warehouse_ids)),
        status="draft",
        receipt_date=local_today(),
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
