from decimal import Decimal
from uuid import uuid4

from sqlalchemy import false, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_today
from app.models.inventory import (
    MFG_COMPLETION_SOURCE,
    MFG_MATERIAL_ISSUE_SOURCE,
    MFG_MATERIAL_RETURN_SOURCE,
    SUBCONTRACT_MATERIAL_ISSUE_SOURCE,
    SUBCONTRACT_RECEIPT_SOURCE,
    InvCount,
    InvCountItem,
    InvStock,
    InvStockTransaction,
    InvTransfer,
    InvTransferItem,
)
from app.models.master_data import MdMaterial
from app.models.purchase import PurchaseReceipt
from app.models.sales import SalesDelivery
from app.services.auth_service import UserContext


def _apply_warehouse_scope(statement, warehouse_column, context: UserContext):
    from app.services.inventory_advanced_service import allowed_warehouse_ids

    warehouse_ids = allowed_warehouse_ids(context)
    if warehouse_ids is None:
        return statement
    if not warehouse_ids:
        return statement.where(false())
    return statement.where(warehouse_column.in_(warehouse_ids))


PRODUCTION_STOCK_SOURCES = frozenset(
    {
        MFG_MATERIAL_ISSUE_SOURCE,
        MFG_MATERIAL_RETURN_SOURCE,
        MFG_COMPLETION_SOURCE,
        SUBCONTRACT_MATERIAL_ISSUE_SOURCE,
        SUBCONTRACT_RECEIPT_SOURCE,
    }
)


def _new_inventory_doc_no(prefix: str) -> str:
    return f"{prefix}-{local_today():%Y%m%d}-{uuid4().hex.upper()}"


def get_stock_unit_cost(
    db: Session, context: UserContext, warehouse_id: str, material_id: str
) -> Decimal:
    from app.services.inventory_advanced_service import assert_warehouse_access

    assert_warehouse_access(context, warehouse_id)
    stock = db.scalar(
        select(InvStock).where(
            InvStock.org_id == context.org_id,
            InvStock.warehouse_id == warehouse_id,
            InvStock.material_id == material_id,
        )
    )
    return Decimal(stock.average_cost) if stock is not None else Decimal("0")


def list_stock(db: Session, context: UserContext, warehouse_id: str | None = None) -> list[InvStock]:
    from app.services.inventory_advanced_service import assert_warehouse_access

    statement = select(InvStock).where(InvStock.org_id == context.org_id)
    if warehouse_id is not None:
        assert_warehouse_access(context, warehouse_id)
        statement = statement.where(InvStock.warehouse_id == warehouse_id)
    else:
        statement = _apply_warehouse_scope(statement, InvStock.warehouse_id, context)
    return list(db.scalars(statement.order_by(InvStock.warehouse_id, InvStock.material_id)).all())


def _get_or_create_stock(db: Session, context: UserContext, warehouse_id: str, material_id: str) -> InvStock:
    stock = db.scalar(
        select(InvStock)
        .where(InvStock.org_id == context.org_id, InvStock.warehouse_id == warehouse_id, InvStock.material_id == material_id)
        .with_for_update()
    )
    if stock is None:
        stock = InvStock(
            org_id=context.org_id,
            warehouse_id=warehouse_id,
            material_id=material_id,
            quantity=Decimal("0"),
            locked_quantity=Decimal("0"),
            available_quantity=Decimal("0"),
        )
        db.add(stock)
        db.flush()
    return stock


def _sync_stock_balances(stock: InvStock) -> InvStock:
    """Validate and derive ATP from the authoritative stock and lock balances.

    ``available_quantity`` is derived data.  A pre-existing inconsistent row is
    rejected so a normal business write cannot silently hide a data-integrity
    problem by overwriting it.
    """
    quantity = Decimal(str(stock.quantity or 0))
    locked = Decimal(str(stock.locked_quantity or 0))
    available = Decimal(str(stock.available_quantity or 0))
    if locked < 0:
        raise AppError("锁定库存不能为负数", code=409)
    expected = quantity - locked
    if available != expected:
        raise AppError("库存余额不一致，请先按库存流水修复", code=409)
    stock.available_quantity = expected
    return stock


# ---------------------------------------------------------------------------
# GAP-08 / GAP-09: costing method & negative stock control.
# ---------------------------------------------------------------------------
MOVING_AVERAGE_METHODS = frozenset({"weighted_average", "moving_average", "moving_weighted_average", "fifo"})
STANDARD_COST_METHODS = frozenset({"standard", "standard_cost"})
COST_SCALE = Decimal("0.000001")


def _bool_parameter(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "是"}


def get_costing_method(db: Session, org_id: str) -> str:
    """Return the normalised ``inventory.costing_method`` (default weighted_average)."""
    from app.services.phase2_parameter_service import get_phase2_parameter

    value = (get_phase2_parameter(db, org_id, "inventory.costing_method", "weighted_average") or "").strip().lower()
    if value in STANDARD_COST_METHODS:
        return "standard"
    return "weighted_average" if value in MOVING_AVERAGE_METHODS or not value else value


def allow_negative_stock(db: Session, org_id: str) -> bool:
    from app.services.phase2_parameter_service import get_phase2_parameter

    return _bool_parameter(get_phase2_parameter(db, org_id, "inventory.allow_negative_stock", "false"))


def _material_label(db: Session, material_id: str) -> str:
    material = db.get(MdMaterial, material_id)
    return f"{material.code} {material.name}" if material is not None else material_id


def _warehouse_label(db: Session, warehouse_id: str) -> str:
    from app.models.master_data import MdWarehouse

    warehouse = db.get(MdWarehouse, warehouse_id)
    return f"{warehouse.code} {warehouse.name}" if warehouse is not None else warehouse_id


def _apply_inbound_cost(db: Session, org_id: str, stock: InvStock, quantity: Decimal, unit_cost: Decimal) -> None:
    """Recalculate ``average_cost`` for an inbound posting according to the costing method."""
    method = get_costing_method(db, org_id)
    if method == "standard":
        material = db.get(MdMaterial, stock.material_id)
        stock.average_cost = Decimal(str(material.standard_cost if material is not None else unit_cost or 0))
        return
    old_qty = Decimal(str(stock.quantity or 0))
    old_avg = Decimal(str(stock.average_cost or 0))
    new_qty = old_qty + quantity
    if old_qty <= 0 or new_qty <= 0:
        # Negative / empty historical balances carry no meaningful value; restart from this receipt.
        stock.average_cost = Decimal(str(unit_cost)).quantize(COST_SCALE)
    else:
        stock.average_cost = ((old_qty * old_avg + quantity * Decimal(str(unit_cost))) / new_qty).quantize(COST_SCALE)


def current_unit_cost(db: Session, org_id: str, warehouse_id: str, material_id: str) -> Decimal:
    """Unit cost used for outbound postings (moving average or standard cost)."""
    if get_costing_method(db, org_id) == "standard":
        material = db.get(MdMaterial, material_id)
        return Decimal(str(material.standard_cost)) if material is not None else Decimal("0")
    stock = db.scalar(select(InvStock).where(InvStock.org_id == org_id, InvStock.warehouse_id == warehouse_id, InvStock.material_id == material_id))
    return Decimal(str(stock.average_cost)) if stock is not None else Decimal("0")


def post_stock_transaction(
    db: Session,
    context: UserContext,
    *,
    source_type: str,
    source_id: str,
    warehouse_id: str,
    material_id: str,
    quantity: Decimal,
    direction: str,
    unit_cost: Decimal = Decimal("0"),
    location_id: str | None = None,
    batch_id: str | None = None,
    consumed_layer_ids: list[str] | None = None,
) -> InvStockTransaction:
    from app.services.inventory_advanced_service import assert_warehouse_access
    from app.services.cost_service import assert_period_open

    assert_warehouse_access(context, warehouse_id)
    assert_period_open(db, context.org_id, local_today())
    if quantity <= 0 or direction not in {"in", "out"}:
        raise AppError("库存数量或方向无效", code=400)
    duplicate = db.scalar(
        select(InvStockTransaction).where(
            InvStockTransaction.org_id == context.org_id,
            InvStockTransaction.source_type == source_type,
            InvStockTransaction.source_id == source_id,
            InvStockTransaction.warehouse_id == warehouse_id,
            InvStockTransaction.material_id == material_id,
            InvStockTransaction.direction == direction,
        )
    )
    if duplicate is not None:
        raise AppError("库存来源单据已入账，禁止重复记账", code=409)
    stock = _get_or_create_stock(db, context, warehouse_id, material_id)
    _sync_stock_balances(stock)
    if direction == "out" and stock.available_quantity < quantity and not allow_negative_stock(db, context.org_id):
        raise AppError(
            f"可用库存不足：仓库「{_warehouse_label(db, warehouse_id)}」物料「{_material_label(db, material_id)}」"
            f"可用 {Decimal(stock.available_quantity).normalize():f}，本次需出库 {Decimal(quantity).normalize():f}，不允许出现负库存",
            code=400,
        )
    if direction == "in":
        _apply_inbound_cost(db, context.org_id, stock, quantity, unit_cost)
    delta = quantity if direction == "in" else -quantity
    stock.quantity += delta
    stock.available_quantity = stock.quantity - stock.locked_quantity
    transaction = InvStockTransaction(
        org_id=context.org_id,
        warehouse_id=warehouse_id,
        material_id=material_id,
        location_id=location_id,
        batch_id=batch_id,
        source_type=source_type,
        source_id=source_id,
        direction=direction,
        quantity=quantity,
        unit_cost=unit_cost,
        amount=(quantity * unit_cost).quantize(Decimal("0.01")),
        created_by=context.id,
        consumed_layer_ids=consumed_layer_ids or [],
    )
    db.add(transaction)
    db.flush()
    return transaction


def create_transfer(db: Session, context: UserContext, *, from_warehouse_id: str, to_warehouse_id: str, items: list[dict]) -> InvTransfer:
    from app.services.inventory_advanced_service import assert_warehouse_access

    if from_warehouse_id == to_warehouse_id:
        raise AppError("调出仓库和调入仓库不能相同", code=400)
    assert_warehouse_access(context, from_warehouse_id)
    assert_warehouse_access(context, to_warehouse_id)
    transfer = InvTransfer(
        org_id=context.org_id,
        doc_no=_new_inventory_doc_no("TR"),
        from_warehouse_id=from_warehouse_id,
        to_warehouse_id=to_warehouse_id,
        status="draft",
        transfer_date=local_today(),
        created_by=context.id,
    )
    transfer.items = [InvTransferItem(material_id=item["material_id"], quantity=item["quantity"], unit_cost=item.get("unit_cost", 0)) for item in items]
    db.add(transfer)
    db.flush()
    return transfer


def serialize_transfer(transfer: InvTransfer) -> dict:
    return {
        "id": transfer.id,
        "doc_no": transfer.doc_no,
        "from_warehouse_id": transfer.from_warehouse_id,
        "to_warehouse_id": transfer.to_warehouse_id,
        "status": transfer.status,
        "transfer_date": transfer.transfer_date.isoformat(),
        "items": [
            {
                "id": item.id,
                "material_id": item.material_id,
                "quantity": str(item.quantity),
                "unit_cost": str(item.unit_cost),
            }
            for item in transfer.items
        ],
    }


def serialize_count(count: InvCount) -> dict:
    return {
        "id": count.id,
        "doc_no": count.doc_no,
        "warehouse_id": count.warehouse_id,
        "status": count.status,
        "count_date": count.count_date.isoformat(),
        "items": [
            {
                "id": item.id,
                "material_id": item.material_id,
                "system_quantity": str(item.system_quantity),
                "actual_quantity": str(item.actual_quantity),
                "difference_quantity": str(item.difference_quantity),
            }
            for item in count.items
        ],
    }


def serialize_transaction(transaction: InvStockTransaction) -> dict:
    return {
        "id": transaction.id,
        "warehouse_id": transaction.warehouse_id,
        "material_id": transaction.material_id,
        "location_id": transaction.location_id,
        "batch_id": transaction.batch_id,
        "source_type": transaction.source_type,
        "source_id": transaction.source_id,
        "direction": transaction.direction,
        "quantity": str(transaction.quantity),
        "unit_cost": str(transaction.unit_cost),
        "amount": str(transaction.amount),
        "transaction_date": transaction.transaction_date.isoformat(),
        "consumed_layer_ids": list(transaction.consumed_layer_ids or []),
    }


def list_stock_transactions(db: Session, context: UserContext) -> list[dict]:
    statement = _apply_warehouse_scope(
        select(InvStockTransaction)
        .where(InvStockTransaction.org_id == context.org_id)
        .order_by(InvStockTransaction.transaction_date.desc()),
        InvStockTransaction.warehouse_id,
        context,
    )
    return [serialize_transaction(row) for row in db.scalars(statement).all()]


def list_transfers(db: Session, context: UserContext) -> list[dict]:
    statement = select(InvTransfer).where(InvTransfer.org_id == context.org_id)
    statement = _apply_warehouse_scope(statement, InvTransfer.from_warehouse_id, context)
    statement = _apply_warehouse_scope(statement, InvTransfer.to_warehouse_id, context)
    statement = statement.order_by(InvTransfer.created_at.desc(), InvTransfer.id.desc())
    return [serialize_transfer(row) for row in db.scalars(statement).all()]


def list_counts(db: Session, context: UserContext) -> list[dict]:
    statement = _apply_warehouse_scope(
        select(InvCount).where(InvCount.org_id == context.org_id).order_by(InvCount.created_at.desc(), InvCount.id.desc()),
        InvCount.warehouse_id,
        context,
    )
    return [serialize_count(row) for row in db.scalars(statement).all()]


def update_transfer(db: Session, transfer_id: str, context: UserContext, *, from_warehouse_id: str, to_warehouse_id: str, items: list[dict]) -> InvTransfer:
    from app.services.inventory_advanced_service import assert_warehouse_access

    transfer = db.get(InvTransfer, transfer_id)
    if transfer is None or transfer.org_id != context.org_id:
        raise AppError("调拨单不存在", code=404)
    if transfer.status != "draft":
        raise AppError("只有草稿调拨单才能修改", code=400)
    if from_warehouse_id == to_warehouse_id:
        raise AppError("调出仓库和调入仓库不能相同", code=400)
    assert_warehouse_access(context, from_warehouse_id)
    assert_warehouse_access(context, to_warehouse_id)
    transfer.from_warehouse_id = from_warehouse_id
    transfer.to_warehouse_id = to_warehouse_id
    transfer.items = [InvTransferItem(material_id=item["material_id"], quantity=item["quantity"], unit_cost=item.get("unit_cost", 0)) for item in items]
    db.flush()
    return transfer


def delete_transfer(db: Session, transfer_id: str, context: UserContext) -> None:
    transfer = db.get(InvTransfer, transfer_id)
    if transfer is None or transfer.org_id != context.org_id:
        raise AppError("调拨单不存在", code=404)
    if transfer.status != "draft":
        raise AppError("只有草稿调拨单才能删除", code=400)
    db.delete(transfer)
    db.commit()


def approve_transfer(db: Session, transfer_id: str, context: UserContext) -> InvTransfer:
    from app.services.inventory_advanced_service import assert_warehouse_access

    transfer = db.get(InvTransfer, transfer_id)
    if transfer is None or transfer.org_id != context.org_id:
        raise AppError("调拨单不存在", code=404)
    assert_warehouse_access(context, transfer.from_warehouse_id)
    assert_warehouse_access(context, transfer.to_warehouse_id)
    if transfer.status != "draft":
        raise AppError("只有草稿调拨单才能审核", code=400)
    transfer.status = "approved"
    db.flush()
    return transfer


def complete_transfer(db: Session, transfer_id: str, context: UserContext) -> InvTransfer:
    from app.services.inventory_advanced_service import assert_warehouse_access

    transfer = db.get(InvTransfer, transfer_id)
    if transfer is None or transfer.org_id != context.org_id:
        raise AppError("调拨单不存在", code=404)
    assert_warehouse_access(context, transfer.from_warehouse_id)
    assert_warehouse_access(context, transfer.to_warehouse_id)
    if transfer.status != "approved":
        raise AppError("只有已审核调拨单才能完成", code=400)
    for item in transfer.items:
        # GAP-08: 调拨按调出仓当前成本平移，避免 0 单价拉低调入仓平均成本。
        transfer_cost = current_unit_cost(db, context.org_id, transfer.from_warehouse_id, item.material_id) or Decimal(str(item.unit_cost or 0))
        post_stock_transaction(
            db, context, source_type="transfer", source_id=transfer.id,
            warehouse_id=transfer.from_warehouse_id, material_id=item.material_id,
            quantity=item.quantity, direction="out", unit_cost=transfer_cost,
        )
        post_stock_transaction(
            db, context, source_type="transfer", source_id=transfer.id,
            warehouse_id=transfer.to_warehouse_id, material_id=item.material_id,
            quantity=item.quantity, direction="in", unit_cost=transfer_cost,
        )
    transfer.status = "completed"
    db.flush()
    return transfer


def create_count(db: Session, context: UserContext, *, warehouse_id: str, items: list[dict]) -> InvCount:
    from app.services.inventory_advanced_service import assert_warehouse_access

    assert_warehouse_access(context, warehouse_id)
    count = InvCount(
        org_id=context.org_id,
        doc_no=_new_inventory_doc_no("CT"),
        warehouse_id=warehouse_id,
        status="draft",
        count_date=local_today(),
        created_by=context.id,
    )
    count.items = []
    for item in items:
        stock = db.scalar(select(InvStock).where(InvStock.org_id == context.org_id, InvStock.warehouse_id == warehouse_id, InvStock.material_id == item["material_id"]))
        system_quantity = stock.quantity if stock else Decimal("0")
        actual_quantity = Decimal(item["actual_quantity"])
        count.items.append(
            InvCountItem(
                material_id=item["material_id"],
                system_quantity=system_quantity,
                actual_quantity=actual_quantity,
                difference_quantity=actual_quantity - system_quantity,
                unit_cost=stock.average_cost if stock else Decimal("0"),
            )
        )
    db.add(count)
    db.flush()
    return count


def update_count(db: Session, count_id: str, context: UserContext, *, warehouse_id: str, items: list[dict]) -> InvCount:
    from app.services.inventory_advanced_service import assert_warehouse_access

    count = db.get(InvCount, count_id)
    if count is None or count.org_id != context.org_id:
        raise AppError("盘点单不存在", code=404)
    if count.status != "draft":
        raise AppError("只有草稿状态的盘点单可以修改", code=400)
    assert_warehouse_access(context, warehouse_id)
    count.warehouse_id = warehouse_id
    count.items = []
    for item in items:
        stock = db.scalar(
            select(InvStock).where(
                InvStock.org_id == context.org_id,
                InvStock.warehouse_id == warehouse_id,
                InvStock.material_id == item["material_id"],
            )
        )
        system_quantity = stock.quantity if stock else Decimal("0")
        actual_quantity = Decimal(item["actual_quantity"])
        count.items.append(
            InvCountItem(
                material_id=item["material_id"],
                system_quantity=system_quantity,
                actual_quantity=actual_quantity,
                difference_quantity=actual_quantity - system_quantity,
                unit_cost=stock.average_cost if stock else Decimal("0"),
            )
        )
    count.version += 1
    db.flush()
    return count


def delete_count(db: Session, count_id: str, context: UserContext) -> None:
    from app.services.inventory_advanced_service import assert_warehouse_access

    count = db.get(InvCount, count_id)
    if count is None or count.org_id != context.org_id:
        raise AppError("盘点单不存在", code=404)
    assert_warehouse_access(context, count.warehouse_id)
    if count.status != "draft":
        raise AppError("只有草稿状态的盘点单可以删除", code=400)
    db.delete(count)


def complete_count(db: Session, count_id: str, context: UserContext) -> InvCount:
    from app.services.inventory_advanced_service import assert_warehouse_access

    count = db.get(InvCount, count_id)
    if count is None or count.org_id != context.org_id:
        raise AppError("盘点单不存在", code=404)
    assert_warehouse_access(context, count.warehouse_id)
    if count.status != "draft":
        raise AppError("盘点单当前不可完成", code=400)
    for item in count.items:
        if item.difference_quantity > 0:
            post_stock_transaction(db, context, source_type="count", source_id=count.id, warehouse_id=count.warehouse_id, material_id=item.material_id, quantity=item.difference_quantity, direction="in", unit_cost=item.unit_cost)
        elif item.difference_quantity < 0:
            post_stock_transaction(db, context, source_type="count", source_id=count.id, warehouse_id=count.warehouse_id, material_id=item.material_id, quantity=-item.difference_quantity, direction="out", unit_cost=item.unit_cost)
    count.status = "completed"
    db.flush()
    return count


def list_safety_warnings(db: Session, context: UserContext) -> list[dict]:
    statement = _apply_warehouse_scope(
        select(InvStock, MdMaterial)
        .join(MdMaterial, MdMaterial.id == InvStock.material_id)
        .where(
            InvStock.org_id == context.org_id,
            MdMaterial.min_stock > 0,
            InvStock.available_quantity < MdMaterial.min_stock,
        ),
        InvStock.warehouse_id,
        context,
    )
    rows = db.execute(statement).all()
    return [
        {
            "warehouse_id": stock.warehouse_id,
            "material_id": stock.material_id,
            "current_quantity": str(stock.available_quantity),
            "min_quantity": str(material.min_stock),
        }
        for stock, material in rows
    ]


def complete_sales_delivery(db: Session, delivery_id: str, context: UserContext) -> SalesDelivery:
    delivery = db.get(SalesDelivery, delivery_id)
    if delivery is None or delivery.org_id != context.org_id:
        raise AppError("销售出库单不存在", code=404)
    if delivery.status != "draft":
        raise AppError("销售出库单当前不可完成", code=400)
    for item in delivery.items:
        post_stock_transaction(
            db,
            context,
            source_type="sales_delivery",
            source_id=delivery.id,
            warehouse_id=delivery.warehouse_id,
            material_id=item.material_id,
            quantity=item.quantity,
            direction="out",
            # GAP-08: 出库成本取移动加权平均（或标准成本），而不是销售单价。
            unit_cost=current_unit_cost(db, context.org_id, delivery.warehouse_id, item.material_id),
        )
    delivery.status = "completed"
    db.flush()
    writeback_sales_order_delivered(db, delivery)
    return delivery


def complete_purchase_receipt(db: Session, receipt_id: str, context: UserContext) -> PurchaseReceipt:
    receipt = db.get(PurchaseReceipt, receipt_id)
    if receipt is None or receipt.org_id != context.org_id:
        raise AppError("采购入库单不存在", code=404)
    if receipt.status != "draft":
        raise AppError("采购入库单当前不可完成", code=400)
    for item in receipt.items:
        post_stock_transaction(
            db,
            context,
            source_type="purchase_receipt",
            source_id=receipt.id,
            warehouse_id=receipt.warehouse_id,
            material_id=item.material_id,
            quantity=item.quantity,
            direction="in",
            unit_cost=item.unit_price,
        )
    receipt.status = "completed"
    db.flush()
    writeback_purchase_order_received(db, receipt)
    return receipt


# ---------------------------------------------------------------------------
# GAP-01: write completed receipt/delivery quantities back to the source order.
# ---------------------------------------------------------------------------
PURCHASE_PARTIAL_STATUS = "partially_received"
SALES_PARTIAL_STATUS = "partially_delivered"


def _order_progress_status(lines, done_attr: str, partial_status: str, current: str) -> str:
    total_done = sum((Decimal(str(getattr(line, done_attr) or 0)) for line in lines), Decimal("0"))
    if lines and all(Decimal(str(getattr(line, done_attr) or 0)) >= Decimal(str(line.quantity)) for line in lines):
        return "completed"
    if total_done > 0:
        return partial_status
    return current


def writeback_purchase_order_received(db: Session, receipt: PurchaseReceipt) -> None:
    """Accumulate received quantity on the purchase order lines and derive order status."""
    from app.models.purchase import PurchaseOrder

    order = db.get(PurchaseOrder, receipt.order_id) if receipt.order_id else None
    if order is None:
        return
    lines = {line.id: line for line in order.items}
    for item in receipt.items:
        line = lines.get(item.order_item_id) if item.order_item_id else None
        if line is None:
            line = next((row for row in order.items if row.material_id == item.material_id and row.received_quantity < row.quantity), None)
        if line is None:
            continue
        line.received_quantity = Decimal(str(line.received_quantity or 0)) + Decimal(str(item.quantity))
    if order.status in {"approved", PURCHASE_PARTIAL_STATUS}:
        order.status = _order_progress_status(order.items, "received_quantity", PURCHASE_PARTIAL_STATUS, order.status)
    db.flush()


def writeback_sales_order_delivered(db: Session, delivery: SalesDelivery) -> None:
    """Accumulate delivered quantity on the sales order lines and derive order status."""
    from app.models.sales import SalesOrder

    order = db.get(SalesOrder, delivery.order_id) if delivery.order_id else None
    if order is None:
        return
    lines = {line.id: line for line in order.items}
    for item in delivery.items:
        line = lines.get(item.order_item_id) if item.order_item_id else None
        if line is None:
            line = next((row for row in order.items if row.material_id == item.material_id and row.delivered_quantity < row.quantity), None)
        if line is None:
            continue
        line.delivered_quantity = Decimal(str(line.delivered_quantity or 0)) + Decimal(str(item.quantity))
    if order.status in {"approved", SALES_PARTIAL_STATUS}:
        order.status = _order_progress_status(order.items, "delivered_quantity", SALES_PARTIAL_STATUS, order.status)
    db.flush()
