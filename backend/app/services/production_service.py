from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError
from app.models.inventory import (
    MFG_COMPLETION_SOURCE,
    MFG_MATERIAL_ISSUE_SOURCE,
    MFG_MATERIAL_RETURN_SOURCE,
    SUBCONTRACT_MATERIAL_ISSUE_SOURCE,
    SUBCONTRACT_RECEIPT_SOURCE,
)
from app.models.master_data import MdMaterial, MdSupplier
from app.models.production import (
    MfgMaterialIssue,
    MfgMaterialIssueItem,
    MfgMaterialReturn,
    MfgMaterialReturnItem,
    MfgReport,
    MfgSubcontractOrder,
    MfgSubcontractReceipt,
    MfgWorkOrder,
    MfgWorkOrderMaterial,
)
from app.services.audit_service import write_operation_log
from app.services.auth_service import UserContext
from app.services.configuration_service import next_doc_no
from app.services.event_service import emit_event
from app.services.finance_service import create_payable_from_subcontract_receipt
from app.services.inventory_service import get_stock_unit_cost, post_stock_transaction
from app.services.planning_service import (
    _approved_bom_for_material,
    _require_material,
    _require_warehouse,
    _validate_source_reference,
)
from app.services.production_resource_service import (
    approved_routing_for_work_order,
    routing_snapshot,
    work_order_readiness,
)


QUANTITY_SCALE = Decimal("0.000001")
MONEY_SCALE = Decimal("0.01")


def _quantity(value: Decimal | int | str | None) -> Decimal:
    return Decimal(value or 0).quantize(QUANTITY_SCALE, rounding=ROUND_HALF_UP)


def _snapshot_quantity(value: Decimal) -> str:
    return format(_quantity(value).normalize(), "f") if value else "0"


def _serialize_material(row: MfgWorkOrderMaterial) -> dict:
    return {
        "material_id": row.material_id,
        "planned_quantity": f"{_quantity(row.required_quantity):.6f}",
        "issued_quantity": f"{_quantity(row.issued_quantity):.6f}",
        "returned_quantity": f"{_quantity(row.returned_quantity):.6f}",
    }


def serialize_work_order(row: MfgWorkOrder) -> dict:
    return {
        "id": row.id,
        "doc_no": row.doc_no,
        "material_id": row.material_id,
        "warehouse_id": row.warehouse_id,
        "bom_id": row.bom_id,
        "routing_id": row.routing_id,
        "plan_date": row.plan_date.isoformat(),
        "quantity": f"{_quantity(row.quantity):.6f}",
        "status": row.status,
        "reported_good_quantity": f"{_quantity(row.reported_good_quantity):.6f}",
        "reported_scrap_quantity": f"{_quantity(row.reported_scrap_quantity):.6f}",
        "completed_quantity": f"{_quantity(row.completed_quantity):.6f}",
        "bom_snapshot": row.bom_snapshot,
        "routing_snapshot": row.routing_snapshot,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "materials": [_serialize_material(item) for item in row.materials if not item.is_deleted],
    }


def serialize_issue(row: MfgMaterialIssue) -> dict:
    return {
        "id": row.id,
        "work_order_id": row.work_order_id,
        "subcontract_order_id": row.subcontract_order_id,
        "warehouse_id": row.warehouse_id,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "items": [
            {
                "material_id": item.material_id,
                "quantity": f"{_quantity(item.quantity):.6f}",
                "returned_quantity": f"{_quantity(item.returned_quantity):.6f}",
            }
            for item in row.items
            if not item.is_deleted
        ],
    }


def serialize_return(row: MfgMaterialReturn) -> dict:
    return {
        "id": row.id,
        "issue_id": row.issue_id,
        "work_order_id": row.work_order_id,
        "warehouse_id": row.warehouse_id,
        "items": [
            {"material_id": item.material_id, "quantity": f"{_quantity(item.quantity):.6f}"}
            for item in row.items
            if not item.is_deleted
        ],
    }


def serialize_report(row: MfgReport) -> dict:
    return {
        "id": row.id,
        "work_order_id": row.work_order_id,
        "operation_id": row.operation_id,
        "operation_name": row.operation_name,
        "good_quantity": f"{_quantity(row.good_quantity):.6f}",
        "scrap_quantity": f"{_quantity(row.scrap_quantity):.6f}",
        "hours": f"{_quantity(row.hours):.6f}",
        "report_time": row.report_time.isoformat(),
    }


def serialize_subcontract_order(row: MfgSubcontractOrder) -> dict:
    return {
        "id": row.id,
        "doc_no": row.doc_no,
        "supplier_id": row.supplier_id,
        "material_id": row.material_id,
        "warehouse_id": row.warehouse_id,
        "plan_date": row.plan_date.isoformat(),
        "quantity": f"{_quantity(row.quantity):.6f}",
        "received_quantity": f"{_quantity(row.received_quantity):.6f}",
        "processing_fee": f"{Decimal(row.processing_fee).quantize(MONEY_SCALE):.2f}",
        "status": row.status,
        "source_type": row.source_type,
        "source_id": row.source_id,
    }


def serialize_subcontract_receipt(row: MfgSubcontractReceipt) -> dict:
    return {
        "id": row.id,
        "doc_no": row.doc_no,
        "subcontract_order_id": row.subcontract_order_id,
        "warehouse_id": row.warehouse_id,
        "material_id": row.material_id,
        "good_quantity": f"{_quantity(row.good_quantity):.6f}",
        "unit_cost": f"{_quantity(row.unit_cost):.6f}",
        "processing_fee_amount": f"{Decimal(row.processing_fee_amount).quantize(MONEY_SCALE):.2f}",
        "operation_key": row.operation_key,
        "status": row.status,
        "source_type": row.source_type,
        "source_id": row.source_id,
    }


def _get_work_order(db: Session, work_order_id: str, context: UserContext, *, lock: bool = False) -> MfgWorkOrder:
    statement = (
        select(MfgWorkOrder)
        .options(selectinload(MfgWorkOrder.materials))
        .where(
            MfgWorkOrder.id == work_order_id,
            MfgWorkOrder.org_id == context.org_id,
            MfgWorkOrder.is_deleted.is_(False),
        )
    )
    if lock:
        statement = statement.with_for_update()
    row = db.scalar(statement)
    if row is None:
        raise AppError("生产工单不存在", code=404)
    return row


def _get_subcontract_order(
    db: Session, order_id: str, context: UserContext, *, lock: bool = False
) -> MfgSubcontractOrder:
    statement = select(MfgSubcontractOrder).where(
        MfgSubcontractOrder.id == order_id,
        MfgSubcontractOrder.org_id == context.org_id,
        MfgSubcontractOrder.is_deleted.is_(False),
    )
    if lock:
        statement = statement.with_for_update()
    row = db.scalar(statement)
    if row is None:
        raise AppError("委外订单不存在", code=404)
    return row


def _require_allowed_status(row: MfgWorkOrder, action: str, allowed: set[str]) -> None:
    if row.status not in allowed:
        raise AppError(f"工单状态 {row.status} 不允许{action}", code=400)


def _validate_source(payload, db: Session, context: UserContext) -> None:
    _validate_source_reference(db, payload.source_type, payload.source_id, context)


def _ensure_distinct_items(items) -> None:
    material_ids = [item.material_id for item in items]
    if len(material_ids) != len(set(material_ids)):
        raise AppError("物料明细不能重复", code=400)


def _require_supplier(db: Session, supplier_id: str, context: UserContext) -> None:
    supplier = db.scalar(
        select(MdSupplier).where(
            MdSupplier.id == supplier_id,
            MdSupplier.org_id == context.org_id,
            MdSupplier.is_deleted.is_(False),
        )
    )
    if supplier is None:
        raise AppError("供应商不存在或不属于当前组织", code=404)


def _find_subcontract_issue(db: Session, order_id: str, context: UserContext) -> MfgMaterialIssue | None:
    return db.scalar(
        select(MfgMaterialIssue)
        .options(selectinload(MfgMaterialIssue.items))
        .where(
            MfgMaterialIssue.subcontract_order_id == order_id,
            MfgMaterialIssue.org_id == context.org_id,
            MfgMaterialIssue.is_deleted.is_(False),
        )
    )


def _find_subcontract_receipt(
    db: Session, order_id: str, operation_key: str, context: UserContext
) -> MfgSubcontractReceipt | None:
    return db.scalar(
        select(MfgSubcontractReceipt).where(
            MfgSubcontractReceipt.subcontract_order_id == order_id,
            MfgSubcontractReceipt.org_id == context.org_id,
            MfgSubcontractReceipt.operation_key == operation_key,
            MfgSubcontractReceipt.is_deleted.is_(False),
        )
    )


def create_work_order(db: Session, payload, context: UserContext) -> MfgWorkOrder:
    _require_material(db, payload.material_id, context)
    _require_warehouse(db, payload.warehouse_id, context)
    _validate_source(payload, db, context)
    bom = _approved_bom_for_material(db, context.org_id, payload.material_id, payload.plan_date)
    if bom is None:
        raise AppError("成品缺少有效的已审核 BOM 版本", code=400)
    quantity = _quantity(payload.quantity)
    routing = approved_routing_for_work_order(
        db,
        context,
        bom_id=bom.id,
        material_id=payload.material_id,
        plan_date=payload.plan_date,
        routing_id=payload.routing_id,
    )
    snapshot_items = [
        {"material_id": item.material_id, "quantity": _snapshot_quantity(item.quantity)}
        for item in bom.items
        if not item.is_deleted
    ]
    row = MfgWorkOrder(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "mfg_work_order", context.org_id, payload.plan_date),
        material_id=payload.material_id,
        warehouse_id=payload.warehouse_id,
        bom_id=bom.id,
        routing_id=routing.id if routing else None,
        plan_date=payload.plan_date,
        quantity=quantity,
        status="draft",
        bom_snapshot={
            "bom_id": bom.id,
            "bom_version": bom.bom_version,
            "plan_quantity": _snapshot_quantity(quantity),
            "items": snapshot_items,
        },
        routing_snapshot=routing_snapshot(routing),
        source_type=payload.source_type,
        source_id=payload.source_id,
        created_by=context.id,
        updated_by=context.id,
    )
    row.materials = [
        MfgWorkOrderMaterial(
            material_id=item.material_id,
            required_quantity=_quantity(quantity * _quantity(item.quantity)),
            line_no=index,
        )
        for index, item in enumerate(bom.items, start=1)
        if not item.is_deleted
    ]
    db.add(row)
    db.flush()
    write_operation_log(db, user=context.user, action="create", resource="mfg_work_order", target_id=row.id)
    return row


def create_subcontract_order(db: Session, payload, context: UserContext) -> MfgSubcontractOrder:
    _require_supplier(db, payload.supplier_id, context)
    _require_material(db, payload.material_id, context)
    _require_warehouse(db, payload.warehouse_id, context)
    _validate_source(payload, db, context)
    quantity = _quantity(payload.quantity)
    processing_fee = Decimal(payload.processing_fee).quantize(MONEY_SCALE, rounding=ROUND_HALF_UP)
    if quantity <= 0 or processing_fee <= 0:
        raise AppError("委外数量和加工费必须大于零", code=400)
    row = MfgSubcontractOrder(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "mfg_subcontract_order", context.org_id, payload.plan_date),
        supplier_id=payload.supplier_id,
        material_id=payload.material_id,
        warehouse_id=payload.warehouse_id,
        plan_date=payload.plan_date,
        quantity=quantity,
        processing_fee=processing_fee,
        status="draft",
        source_type=payload.source_type,
        source_id=payload.source_id,
        created_by=context.id,
        updated_by=context.id,
    )
    db.add(row)
    db.flush()
    write_operation_log(db, user=context.user, action="create", resource="mfg_subcontract_order", target_id=row.id)
    return row


def release_subcontract_order(db: Session, order_id: str, context: UserContext) -> MfgSubcontractOrder:
    row = _get_subcontract_order(db, order_id, context, lock=True)
    if row.status in {"released", "partially_received", "completed"}:
        return row
    if row.status != "draft":
        raise AppError(f"委外订单状态 {row.status} 不允许下达", code=400)
    row.status = "released"
    row.updated_by = context.id
    write_operation_log(db, user=context.user, action="release", resource="mfg_subcontract_order", target_id=row.id)
    db.flush()
    return row


def cancel_subcontract_order(db: Session, order_id: str, context: UserContext) -> MfgSubcontractOrder:
    row = _get_subcontract_order(db, order_id, context, lock=True)
    if row.status == "cancelled":
        return row
    if row.status not in {"draft", "released"}:
        raise AppError(f"委外订单状态 {row.status} 不允许取消", code=400)
    row.status = "cancelled"
    row.updated_by = context.id
    write_operation_log(db, user=context.user, action="cancel", resource="mfg_subcontract_order", target_id=row.id)
    db.flush()
    return row


def issue_subcontract_material(db: Session, order_id: str, items, context: UserContext) -> MfgMaterialIssue:
    row = _get_subcontract_order(db, order_id, context, lock=True)
    existing = _find_subcontract_issue(db, row.id, context)
    if existing is not None:
        return existing
    if row.status not in {"released", "partially_received"}:
        raise AppError(f"委外订单状态 {row.status} 不允许发料", code=400)
    _ensure_distinct_items(items)
    quantities = {item.material_id: _quantity(item.quantity) for item in items}
    for material_id, quantity in quantities.items():
        _require_material(db, material_id, context)
        if quantity <= 0:
            raise AppError("委外发料数量必须大于零", code=400)
    issue = MfgMaterialIssue(
        org_id=context.org_id,
        subcontract_order_id=row.id,
        warehouse_id=row.warehouse_id,
        source_type="mfg_subcontract_order",
        source_id=row.id,
        created_by=context.id,
    )
    try:
        with db.begin_nested():
            db.add(issue)
            db.flush()
    except IntegrityError:
        existing = _find_subcontract_issue(db, row.id, context)
        if existing is None:
            raise
        return existing
    for index, item in enumerate(items, start=1):
        quantity = quantities[item.material_id]
        unit_cost = get_stock_unit_cost(db, context, row.warehouse_id, item.material_id)
        issue.items.append(
            MfgMaterialIssueItem(
                material_id=item.material_id,
                quantity=quantity,
                unit_cost=unit_cost,
                line_no=index,
            )
        )
        post_stock_transaction(
            db,
            context,
            source_type=SUBCONTRACT_MATERIAL_ISSUE_SOURCE,
            source_id=issue.id,
            warehouse_id=row.warehouse_id,
            material_id=item.material_id,
            quantity=quantity,
            direction="out",
            unit_cost=unit_cost,
        )
    row.updated_by = context.id
    write_operation_log(
        db, user=context.user, action="issue", resource="mfg_subcontract_order", target_id=row.id, detail={"issue_id": issue.id}
    )
    db.flush()
    return issue


def receive_subcontract_order(db: Session, order_id: str, payload, context: UserContext) -> MfgSubcontractReceipt:
    good_quantity = _quantity(payload.good_quantity)
    unit_cost = _quantity(payload.unit_cost)
    row = _get_subcontract_order(db, order_id, context, lock=True)
    existing = _find_subcontract_receipt(db, row.id, payload.operation_key, context)
    if existing is not None:
        return existing
    if row.status not in {"released", "partially_received"}:
        raise AppError(f"委外订单状态 {row.status} 不允许收货", code=400)
    if good_quantity <= 0 or unit_cost <= 0:
        raise AppError("委外收货数量和单价必须大于零", code=400)
    if _quantity(row.received_quantity + good_quantity) > _quantity(row.quantity):
        raise AppError("委外收货数量超过订单数量", code=400)
    allocated_fee = (Decimal(row.processing_fee) * good_quantity / Decimal(row.quantity)).quantize(
        MONEY_SCALE, rounding=ROUND_HALF_UP
    )
    if _quantity(row.received_quantity + good_quantity) == _quantity(row.quantity):
        allocated_fee = Decimal(row.processing_fee) - sum(
            db.scalars(
                select(MfgSubcontractReceipt.processing_fee_amount).where(
                    MfgSubcontractReceipt.subcontract_order_id == row.id,
                    MfgSubcontractReceipt.org_id == context.org_id,
                    MfgSubcontractReceipt.is_deleted.is_(False),
                )
            )
        )
    receipt = MfgSubcontractReceipt(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "mfg_subcontract_receipt", context.org_id, row.plan_date),
        subcontract_order_id=row.id,
        warehouse_id=row.warehouse_id,
        material_id=row.material_id,
        good_quantity=good_quantity,
        unit_cost=unit_cost,
        processing_fee_amount=allocated_fee,
        operation_key=payload.operation_key,
        status="completed",
        source_type="mfg_subcontract_order",
        source_id=row.id,
        created_by=context.id,
    )
    try:
        with db.begin_nested():
            db.add(receipt)
            db.flush()
    except IntegrityError:
        existing = _find_subcontract_receipt(db, row.id, payload.operation_key, context)
        if existing is None:
            raise
        return existing
    post_stock_transaction(
        db,
        context,
        source_type=SUBCONTRACT_RECEIPT_SOURCE,
        source_id=receipt.id,
        warehouse_id=row.warehouse_id,
        material_id=row.material_id,
        quantity=good_quantity,
        direction="in",
        unit_cost=unit_cost,
    )
    row.received_quantity = _quantity(row.received_quantity + good_quantity)
    row.status = "completed" if row.received_quantity == _quantity(row.quantity) else "partially_received"
    row.updated_by = context.id
    create_payable_from_subcontract_receipt(db, receipt.id, context)
    write_operation_log(
        db, user=context.user, action="receive", resource="mfg_subcontract_order", target_id=row.id, detail={"receipt_id": receipt.id}
    )
    db.flush()
    return receipt


def release_work_order(db: Session, work_order_id: str, context: UserContext) -> MfgWorkOrder:
    row = _get_work_order(db, work_order_id, context, lock=True)
    _require_allowed_status(row, "下达", {"draft"})
    if row.routing_id:
        readiness = work_order_readiness(db, row, context)
        if not readiness["ready"]:
            material_shortages = [
                f"{item['material_id']} 缺 {item['shortage_quantity']}"
                for item in readiness["materials"]
                if not item["ready"]
            ]
            capacity_shortages = [
                f"{item['work_center_code'] or item['work_center_id']} 缺 {item['shortage_hours']} 小时"
                for item in readiness["capacity"]
                if not item["ready"]
            ]
            details = "；".join(material_shortages + capacity_shortages)
            raise AppError(f"工单齐套/产能检查未通过：{details}", code=409)
    row.status = "released"
    row.updated_by = context.id
    write_operation_log(db, user=context.user, action="release", resource="mfg_work_order", target_id=row.id)
    db.flush()
    return row


def issue_material(db: Session, work_order_id: str, items, context: UserContext) -> MfgMaterialIssue:
    row = _get_work_order(db, work_order_id, context, lock=True)
    _require_allowed_status(row, "领料", {"released", "in_progress"})
    _ensure_distinct_items(items)
    material_lines = {line.material_id: line for line in row.materials if not line.is_deleted}
    quantities = {item.material_id: _quantity(item.quantity) for item in items}
    for material_id, quantity in quantities.items():
        line = material_lines.get(material_id)
        if line is None:
            raise AppError("领料物料不在工单 BOM 快照中", code=400)
        if _quantity(line.issued_quantity + quantity) > _quantity(line.required_quantity):
            raise AppError("领料数量超过 BOM 计划数量", code=400)

    issue = MfgMaterialIssue(
        org_id=context.org_id,
        work_order_id=row.id,
        warehouse_id=row.warehouse_id,
        created_by=context.id,
    )
    db.add(issue)
    db.flush()
    for index, item in enumerate(items, start=1):
        quantity = quantities[item.material_id]
        unit_cost = get_stock_unit_cost(db, context, row.warehouse_id, item.material_id)
        issue.items.append(
            MfgMaterialIssueItem(
                material_id=item.material_id,
                quantity=quantity,
                unit_cost=unit_cost,
                line_no=index,
            )
        )
        post_stock_transaction(
            db,
            context,
            source_type=MFG_MATERIAL_ISSUE_SOURCE,
            source_id=issue.id,
            warehouse_id=row.warehouse_id,
            material_id=item.material_id,
            quantity=quantity,
            direction="out",
            unit_cost=unit_cost,
        )
        material_lines[item.material_id].issued_quantity = _quantity(
            material_lines[item.material_id].issued_quantity + quantity
        )
    row.status = "in_progress"
    row.updated_by = context.id
    write_operation_log(
        db, user=context.user, action="issue", resource="mfg_work_order", target_id=row.id, detail={"issue_id": issue.id}
    )
    db.flush()
    return issue


def return_material(db: Session, issue_id: str, items, context: UserContext) -> MfgMaterialReturn:
    issue = db.scalar(
        select(MfgMaterialIssue)
        .options(selectinload(MfgMaterialIssue.items))
        .where(MfgMaterialIssue.id == issue_id, MfgMaterialIssue.org_id == context.org_id, MfgMaterialIssue.is_deleted.is_(False))
        .with_for_update()
    )
    if issue is None:
        raise AppError("生产领料单不存在", code=404)
    row = _get_work_order(db, issue.work_order_id, context, lock=True)
    _require_allowed_status(row, "退料", {"released", "in_progress"})
    _ensure_distinct_items(items)
    issue_lines = {line.material_id: line for line in issue.items if not line.is_deleted}
    work_order_lines = {line.material_id: line for line in row.materials if not line.is_deleted}
    quantities = {item.material_id: _quantity(item.quantity) for item in items}
    for material_id, quantity in quantities.items():
        issue_line = issue_lines.get(material_id)
        if issue_line is None or _quantity(issue_line.returned_quantity + quantity) > _quantity(issue_line.quantity):
            raise AppError("退料数量超过原领料数量", code=400)

    material_return = MfgMaterialReturn(
        org_id=context.org_id,
        work_order_id=row.id,
        issue_id=issue.id,
        warehouse_id=row.warehouse_id,
        created_by=context.id,
    )
    db.add(material_return)
    db.flush()
    for index, item in enumerate(items, start=1):
        issue_line = issue_lines[item.material_id]
        quantity = quantities[item.material_id]
        material_return.items.append(
            MfgMaterialReturnItem(
                material_id=item.material_id,
                quantity=quantity,
                unit_cost=issue_line.unit_cost,
                line_no=index,
            )
        )
        post_stock_transaction(
            db,
            context,
            source_type=MFG_MATERIAL_RETURN_SOURCE,
            source_id=material_return.id,
            warehouse_id=row.warehouse_id,
            material_id=item.material_id,
            quantity=quantity,
            direction="in",
            unit_cost=issue_line.unit_cost,
        )
        issue_line.returned_quantity = _quantity(issue_line.returned_quantity + quantity)
        work_order_lines[item.material_id].returned_quantity = _quantity(
            work_order_lines[item.material_id].returned_quantity + quantity
        )
    row.updated_by = context.id
    write_operation_log(
        db, user=context.user, action="return", resource="mfg_work_order", target_id=row.id, detail={"return_id": material_return.id}
    )
    db.flush()
    return material_return


def report_work(db: Session, work_order_id: str, payload, context: UserContext) -> MfgReport:
    row = _get_work_order(db, work_order_id, context, lock=True)
    _require_allowed_status(row, "报工", {"released", "in_progress"})
    good_quantity = _quantity(payload.good_quantity)
    scrap_quantity = _quantity(payload.scrap_quantity)
    if good_quantity < 0 or scrap_quantity < 0:
        raise AppError("合格数量和报废数量不能为负数", code=400)
    if good_quantity + scrap_quantity <= 0:
        raise AppError("合格数量和报废数量之和必须大于零", code=400)
    operation_id = getattr(payload, "operation_id", None)
    operation_name = None
    is_final_operation = True
    if row.routing_id:
        operations = sorted((row.routing_snapshot or {}).get("operations", []), key=lambda item: item.get("line_no", 0))
        operation = next((item for item in operations if item.get("id") == operation_id), None)
        if operation is None:
            raise AppError("绑定工艺路线的工单必须选择有效工序报工", code=400)
        operation_name = operation.get("operation_name")
        is_final_operation = operation_id == operations[-1].get("id")
        previous_good, previous_scrap = db.execute(
            select(
                func.coalesce(func.sum(MfgReport.good_quantity), 0),
                func.coalesce(func.sum(MfgReport.scrap_quantity), 0),
            ).where(
                MfgReport.work_order_id == row.id,
                MfgReport.operation_id == operation_id,
                MfgReport.is_deleted.is_(False),
            )
        ).one()
        operation_total = _quantity(previous_good + previous_scrap + good_quantity + scrap_quantity)
        if operation_total > _quantity(row.quantity):
            raise AppError("该工序累计报工数量超过工单计划数量", code=400)
    if is_final_operation:
        reported_total = _quantity(row.reported_good_quantity + row.reported_scrap_quantity + good_quantity + scrap_quantity)
        if reported_total > _quantity(row.quantity):
            raise AppError("报工数量超过工单计划数量", code=400)
    report = MfgReport(
        work_order_id=row.id,
        operation_id=operation_id,
        operation_name=operation_name,
        good_quantity=good_quantity,
        scrap_quantity=scrap_quantity,
        hours=_quantity(payload.hours),
        created_by=context.id,
    )
    db.add(report)
    if is_final_operation:
        row.reported_good_quantity = _quantity(row.reported_good_quantity + good_quantity)
        row.reported_scrap_quantity = _quantity(row.reported_scrap_quantity + scrap_quantity)
    row.status = "in_progress"
    row.updated_by = context.id
    db.flush()
    write_operation_log(
        db, user=context.user, action="report", resource="mfg_work_order", target_id=row.id, detail={"report_id": report.id}
    )
    return report


def complete_work_order(db: Session, work_order_id: str, context: UserContext) -> MfgWorkOrder:
    row = _get_work_order(db, work_order_id, context, lock=True)
    if row.status == "completed":
        return row
    _require_allowed_status(row, "完工", {"released", "in_progress"})
    completion_quantity = _quantity(row.reported_good_quantity - row.completed_quantity)
    if completion_quantity <= 0:
        raise AppError("工单没有可完工入库的合格数量", code=400)
    material = db.scalar(
        select(MdMaterial).where(
            MdMaterial.id == row.material_id,
            MdMaterial.org_id == context.org_id,
            MdMaterial.is_deleted.is_(False),
        )
    )
    if material is None:
        raise AppError("成品物料不存在或不属于当前组织", code=404)
    post_stock_transaction(
        db,
        context,
        source_type=MFG_COMPLETION_SOURCE,
        source_id=row.id,
        warehouse_id=row.warehouse_id,
        material_id=row.material_id,
        quantity=completion_quantity,
        direction="in",
        unit_cost=_quantity(material.standard_cost),
    )
    row.completed_quantity = _quantity(row.completed_quantity + completion_quantity)
    row.status = "completed"
    row.updated_by = context.id
    emit_event(
        db,
        "work_order.completed",
        "mfg_work_order",
        row.id,
        {"work_order_id": row.id, "quantity": f"{completion_quantity:.6f}"},
    )
    write_operation_log(db, user=context.user, action="complete", resource="mfg_work_order", target_id=row.id)
    db.flush()
    return row


def cancel_work_order(db: Session, work_order_id: str, context: UserContext) -> MfgWorkOrder:
    row = _get_work_order(db, work_order_id, context, lock=True)
    _require_allowed_status(row, "取消", {"released", "in_progress"})
    row.status = "cancelled"
    row.updated_by = context.id
    write_operation_log(db, user=context.user, action="cancel", resource="mfg_work_order", target_id=row.id)
    db.flush()
    return row
