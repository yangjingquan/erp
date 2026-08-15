from collections import OrderedDict
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError
from app.core.time import local_now
from app.models.inventory import InvStock
from app.models.master_data import MdMaterial, MdWarehouse
from app.models.production import MfgBom, MfgBomItem, MfgMps, MfgMrpResult, MfgMrpRun, MfgPlannedOrder
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.business_extensions import PurchaseRequest, PurchaseRequestItem
from app.models.sales import SalesOrder, SalesOrderItem
from app.services.auth_service import UserContext
from app.services.configuration_service import next_doc_no


QUANTITY_SCALE = Decimal("0.000001")
OPEN_ORDER_STATUSES = ("submitted", "approved")


def _quantity(value: Decimal | int | str | None) -> Decimal:
    return Decimal(value or 0).quantize(QUANTITY_SCALE, rounding=ROUND_HALF_UP)


def _serialize_snapshot_value(value: Decimal) -> str:
    return format(value.normalize(), "f") if value else "0"


def serialize_bom(bom: MfgBom) -> dict:
    return {
        "id": bom.id,
        "material_id": bom.material_id,
        "bom_version": bom.bom_version,
        "status": bom.status,
        "effective_from": bom.effective_from.isoformat(),
        "effective_to": bom.effective_to.isoformat() if bom.effective_to else None,
        "source_type": bom.source_type,
        "source_id": bom.source_id,
        "items": [
            {
                "id": item.id,
                "material_id": item.material_id,
                "quantity": f"{_quantity(item.quantity):.6f}",
                "line_no": item.line_no,
                "scrap_rate": f"{Decimal(item.scrap_rate or 0):.4f}",
                "issue_operation_id": item.issue_operation_id,
                "is_phantom": bool(item.is_phantom),
            }
            for item in bom.items
            if not item.is_deleted
        ],
    }


def serialize_mps(mps: MfgMps) -> dict:
    return {
        "id": mps.id,
        "doc_no": mps.doc_no,
        "material_id": mps.material_id,
        "warehouse_id": mps.warehouse_id,
        "plan_date": mps.plan_date.isoformat(),
        "plan_quantity": f"{_quantity(mps.plan_quantity):.6f}",
        "status": mps.status,
        "source_type": mps.source_type,
        "source_id": mps.source_id,
    }


def serialize_mrp_result(result: MfgMrpResult) -> dict:
    return {
        "id": result.id,
        "material_id": result.material_id,
        "gross_requirement": f"{_quantity(result.gross_requirement):.6f}",
        "available_stock": f"{_quantity(result.available_stock):.6f}",
        "open_supply_quantity": f"{_quantity(result.open_supply_quantity):.6f}",
        "safety_stock": f"{_quantity(result.safety_stock):.6f}",
        "net_requirement": f"{_quantity(result.net_requirement):.6f}",
        "status": result.status,
        "source_snapshot": result.source_snapshot,
        "source_document_ids": result.confirmed_source_ids,
    }


def serialize_mrp_run(run: MfgMrpRun) -> dict:
    return {
        "id": run.id,
        "doc_no": run.doc_no,
        "mps_id": run.mps_id,
        "bom_id": run.bom_id,
        "status": run.status,
        "source_snapshot": run.source_snapshot,
        "results": [serialize_mrp_result(result) for result in run.results if not result.is_deleted],
    }


def _get_bom(db: Session, bom_id: str, context: UserContext) -> MfgBom:
    bom = db.scalar(
        select(MfgBom)
        .options(selectinload(MfgBom.items))
        .where(MfgBom.id == bom_id, MfgBom.org_id == context.org_id, MfgBom.is_deleted.is_(False))
    )
    if bom is None:
        raise AppError("BOM 不存在", code=404)
    return bom


def _validate_bom(bom: MfgBom) -> None:
    if bom.effective_to is not None and bom.effective_to < bom.effective_from:
        raise AppError("BOM 生效日期范围无效", code=400)
    component_ids = [item.material_id for item in bom.items if not item.is_deleted]
    if len(component_ids) != len(set(component_ids)):
        raise AppError("BOM 组件物料不能重复", code=400)
    if bom.material_id in component_ids:
        raise AppError("BOM 不允许引用自身", code=400)
    if not component_ids or any(item.quantity <= 0 for item in bom.items if not item.is_deleted):
        raise AppError("BOM 组件数量必须大于零", code=400)


def _require_material(db: Session, material_id: str, context: UserContext) -> None:
    material = db.scalar(
        select(MdMaterial).where(
            MdMaterial.id == material_id,
            MdMaterial.org_id == context.org_id,
            MdMaterial.is_deleted.is_(False),
        )
    )
    if material is None:
        raise AppError("物料不存在或不属于当前组织", code=404)


def _require_warehouse(db: Session, warehouse_id: str, context: UserContext) -> None:
    warehouse = db.scalar(
        select(MdWarehouse).where(
            MdWarehouse.id == warehouse_id,
            MdWarehouse.org_id == context.org_id,
            MdWarehouse.is_deleted.is_(False),
        )
    )
    if warehouse is None:
        raise AppError("仓库不存在或不属于当前组织", code=404)


def _validate_source_reference(
    db: Session, source_type: str | None, source_id: str | None, context: UserContext
) -> None:
    if bool(source_type) != bool(source_id):
        raise AppError("来源类型和来源单据必须同时提供", code=400)
    if source_type is None:
        return
    source_models = {
        "sales_order": SalesOrder,
        "purchase_order": PurchaseOrder,
        "purchase_request": PurchaseRequest,
        "mfg_bom": MfgBom,
        "mfg_mps": MfgMps,
        "mfg_planned_order": MfgPlannedOrder,
    }
    source_model = source_models.get(source_type)
    if source_model is None:
        raise AppError("不支持的来源单据类型", code=400)
    statement = select(source_model).where(
        source_model.id == source_id,
        source_model.org_id == context.org_id,
    )
    if hasattr(source_model, "is_deleted"):
        statement = statement.where(source_model.is_deleted.is_(False))
    if db.scalar(statement) is None:
        raise AppError("来源单据不存在或不属于当前组织", code=404)


def _approved_bom_for_material(db: Session, org_id: str, material_id: str, on_date) -> MfgBom | None:
    return db.scalar(
        select(MfgBom)
        .options(selectinload(MfgBom.items))
        .where(
            MfgBom.org_id == org_id,
            MfgBom.material_id == material_id,
            MfgBom.status == "approved",
            MfgBom.is_deleted.is_(False),
            MfgBom.effective_from <= on_date,
            (MfgBom.effective_to.is_(None) | (MfgBom.effective_to >= on_date)),
        )
        .order_by(MfgBom.effective_from.desc(), MfgBom.created_at.desc())
    )


def _would_be_circular(db: Session, bom: MfgBom) -> bool:
    graph: dict[str, set[str]] = {}
    approved = db.scalars(
        select(MfgBom).options(selectinload(MfgBom.items)).where(
            MfgBom.org_id == bom.org_id,
            MfgBom.status == "approved",
            MfgBom.is_deleted.is_(False),
        )
    ).all()
    for version in approved:
        graph.setdefault(version.material_id, set()).update(
            item.material_id for item in version.items if not item.is_deleted
        )
    graph[bom.material_id] = {item.material_id for item in bom.items if not item.is_deleted}

    def visit(material_id: str, path: set[str]) -> bool:
        if material_id in path:
            return True
        return any(visit(component, path | {material_id}) for component in graph.get(material_id, set()))

    return visit(bom.material_id, set())


def create_bom(db: Session, payload, context: UserContext) -> MfgBom:
    _require_material(db, payload.material_id, context)
    for item in payload.items:
        _require_material(db, item.material_id, context)
    _validate_source_reference(db, payload.source_type, payload.source_id, context)
    duplicate = db.scalar(
        select(MfgBom).where(
            MfgBom.org_id == context.org_id,
            MfgBom.material_id == payload.material_id,
            MfgBom.bom_version == payload.bom_version,
            MfgBom.is_deleted.is_(False),
        )
    )
    if duplicate is not None:
        raise AppError("BOM 版本已存在", code=409)
    bom = MfgBom(
        org_id=context.org_id,
        material_id=payload.material_id,
        bom_version=payload.bom_version,
        status="draft",
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        source_type=payload.source_type,
        source_id=payload.source_id,
        created_by=context.id,
        updated_by=context.id,
    )
    bom.items = [
        MfgBomItem(
            material_id=item.material_id,
            quantity=_quantity(item.quantity),
            line_no=index,
            scrap_rate=item.scrap_rate,
            issue_operation_id=item.issue_operation_id,
            is_phantom=item.is_phantom,
        )
        for index, item in enumerate(payload.items, start=1)
    ]
    _validate_bom(bom)
    db.add(bom)
    db.flush()
    return bom


def update_bom(db: Session, bom_id: str, payload, context: UserContext) -> MfgBom:
    bom = _get_bom(db, bom_id, context)
    if bom.status != "draft":
        raise AppError("只有草稿 BOM 可以编辑", code=409)
    _require_material(db, payload.material_id, context)
    for item in payload.items:
        _require_material(db, item.material_id, context)
    _validate_source_reference(db, payload.source_type, payload.source_id, context)
    bom.material_id = payload.material_id; bom.bom_version = payload.bom_version; bom.effective_from = payload.effective_from; bom.effective_to = payload.effective_to; bom.source_type = payload.source_type; bom.source_id = payload.source_id; bom.updated_by = context.id
    bom.items.clear()
    bom.items.extend(MfgBomItem(material_id=item.material_id, quantity=_quantity(item.quantity), line_no=index, scrap_rate=item.scrap_rate, issue_operation_id=item.issue_operation_id, is_phantom=item.is_phantom) for index, item in enumerate(payload.items, start=1))
    _validate_bom(bom); db.flush(); return bom


def bulk_create_boms(db: Session, payloads, context: UserContext) -> list[MfgBom]:
    return [create_bom(db, payload, context) for payload in payloads]


def submit_bom(db: Session, bom_id: str, context: UserContext) -> MfgBom:
    bom = _get_bom(db, bom_id, context)
    if bom.status != "draft":
        raise AppError(f"BOM 状态 {bom.status} 不允许提交", code=400)
    _validate_bom(bom)
    bom.status = "submitted"
    bom.updated_by = context.id
    db.flush()
    return bom


def approve_bom(db: Session, bom_id: str, context: UserContext) -> MfgBom:
    bom = _get_bom(db, bom_id, context)
    if bom.status != "submitted":
        raise AppError(f"BOM 状态 {bom.status} 不允许审核", code=400)
    _validate_bom(bom)
    if _would_be_circular(db, bom):
        raise AppError("BOM 存在循环引用", code=400)
    bom.status = "approved"
    bom.updated_by = context.id
    db.flush()
    return bom


def disable_bom(db: Session, bom_id: str, context: UserContext) -> MfgBom:
    bom = _get_bom(db, bom_id, context)
    if bom.status != "approved":
        raise AppError("只有已审核 BOM 才能停用", code=400)
    referenced = db.scalar(
        select(MfgMrpRun.id).where(MfgMrpRun.bom_id == bom.id, MfgMrpRun.is_deleted.is_(False))
    )
    if referenced is not None:
        raise AppError("BOM 已被 MRP 引用，禁止停用", code=400)
    bom.status = "disabled"
    bom.updated_by = context.id
    db.flush()
    return bom


def list_boms(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(
        select(MfgBom)
        .options(selectinload(MfgBom.items))
        .where(MfgBom.org_id == context.org_id, MfgBom.is_deleted.is_(False))
        .order_by(MfgBom.created_at.desc())
    ).all()
    return [serialize_bom(row) for row in rows]


def create_mps(db: Session, payload, context: UserContext) -> MfgMps:
    _require_material(db, payload.material_id, context)
    if payload.warehouse_id is not None:
        _require_warehouse(db, payload.warehouse_id, context)
    _validate_source_reference(db, payload.source_type, payload.source_id, context)
    mps = MfgMps(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "mfg_mps", context.org_id, payload.plan_date),
        material_id=payload.material_id,
        warehouse_id=payload.warehouse_id,
        plan_date=payload.plan_date,
        plan_quantity=_quantity(payload.plan_quantity),
        status="draft",
        source_type=payload.source_type,
        source_id=payload.source_id,
        created_by=context.id,
        updated_by=context.id,
    )
    db.add(mps)
    db.flush()
    return mps


def list_mps(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(
        select(MfgMps)
        .where(MfgMps.org_id == context.org_id, MfgMps.is_deleted.is_(False))
        .order_by(MfgMps.created_at.desc())
    ).all()
    return [serialize_mps(row) for row in rows]


def _open_purchase_quantity(db: Session, org_id: str, material_id: str, warehouse_id: str | None) -> Decimal:
    statement = (
        select(func.coalesce(func.sum(PurchaseOrderItem.quantity - PurchaseOrderItem.received_quantity), 0))
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.order_id)
        .where(
            PurchaseOrder.org_id == org_id,
            PurchaseOrder.status.in_(OPEN_ORDER_STATUSES),
            PurchaseOrder.is_deleted.is_(False),
            PurchaseOrderItem.material_id == material_id,
        )
    )
    if warehouse_id is not None:
        statement = statement.where(PurchaseOrderItem.warehouse_id == warehouse_id)
    return _quantity(db.scalar(statement))


def _open_sales_quantity(db: Session, org_id: str, material_id: str, warehouse_id: str | None) -> Decimal:
    statement = (
        select(func.coalesce(func.sum(SalesOrderItem.quantity - SalesOrderItem.delivered_quantity), 0))
        .join(SalesOrder, SalesOrder.id == SalesOrderItem.order_id)
        .where(
            SalesOrder.org_id == org_id,
            SalesOrder.status.in_(OPEN_ORDER_STATUSES),
            SalesOrder.is_deleted.is_(False),
            SalesOrderItem.material_id == material_id,
        )
    )
    if warehouse_id is not None:
        statement = statement.where(SalesOrderItem.warehouse_id == warehouse_id)
    return _quantity(db.scalar(statement))


def _material_supply_snapshot(
    db: Session, mps: MfgMps, material_id: str, bom_version: str | None
) -> tuple[Decimal, Decimal, Decimal, dict]:
    stock_statement = select(func.coalesce(func.sum(InvStock.available_quantity), 0)).where(
        InvStock.org_id == mps.org_id,
        InvStock.material_id == material_id,
    )
    if mps.warehouse_id is not None:
        stock_statement = stock_statement.where(InvStock.warehouse_id == mps.warehouse_id)
    available_stock = _quantity(db.scalar(stock_statement))
    open_purchase = _open_purchase_quantity(db, mps.org_id, material_id, mps.warehouse_id)
    open_sales = _open_sales_quantity(db, mps.org_id, material_id, mps.warehouse_id)
    material = db.scalar(
        select(MdMaterial).where(MdMaterial.id == material_id, MdMaterial.org_id == mps.org_id, MdMaterial.is_deleted.is_(False))
    )
    safety_stock = _quantity(material.min_stock if material else Decimal("0"))
    return available_stock, open_purchase, safety_stock, {
        "mps_id": mps.id,
        "plan_quantity": _serialize_snapshot_value(_quantity(mps.plan_quantity)),
        "bom_version": bom_version,
        "available_stock": _serialize_snapshot_value(available_stock),
        "open_purchase_quantity": _serialize_snapshot_value(open_purchase),
        "open_sales_quantity": _serialize_snapshot_value(open_sales),
        "safety_stock": _serialize_snapshot_value(safety_stock),
    }


def run_mrp(db: Session, mps_id: str, context: UserContext) -> MfgMrpRun:
    mps = db.get(MfgMps, mps_id)
    if mps is None or mps.org_id != context.org_id or mps.is_deleted:
        raise AppError("MPS 不存在", code=404)
    root_bom = _approved_bom_for_material(db, context.org_id, mps.material_id, mps.plan_date)
    if root_bom is None:
        raise AppError("MPS 物料缺少有效的已审核 BOM 版本", code=400)

    root_stock, root_purchase, root_safety, root_snapshot = _material_supply_snapshot(
        db, mps, mps.material_id, root_bom.bom_version
    )
    run = MfgMrpRun(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "mfg_mrp", context.org_id, mps.plan_date),
        mps_id=mps.id,
        bom_id=root_bom.id,
        status="running",
        source_snapshot=root_snapshot,
        created_by=context.id,
    )
    db.add(run)
    db.flush()

    gross_by_material: OrderedDict[str, Decimal] = OrderedDict()
    net_by_material: dict[str, Decimal] = {}
    details: dict[str, tuple[Decimal, Decimal, Decimal, dict]] = {}
    pending: OrderedDict[str, Decimal] = OrderedDict([(mps.material_id, _quantity(mps.plan_quantity))])

    while pending:
        material_id, increment = pending.popitem(last=False)
        previous_gross = gross_by_material.get(material_id, Decimal("0"))
        gross_requirement = _quantity(previous_gross + increment)
        bom = _approved_bom_for_material(db, context.org_id, material_id, mps.plan_date)
        available_stock, open_purchase, safety_stock, snapshot = _material_supply_snapshot(
            db, mps, material_id, bom.bom_version if bom else None
        )
        net_requirement = _quantity(max(gross_requirement - available_stock - open_purchase + safety_stock, Decimal("0")))
        gross_by_material[material_id] = gross_requirement
        details[material_id] = (available_stock, open_purchase, safety_stock, snapshot)
        net_increment = _quantity(net_requirement - net_by_material.get(material_id, Decimal("0")))
        net_by_material[material_id] = net_requirement
        if bom is not None and net_increment > 0:
            for item in bom.items:
                if item.is_deleted:
                    continue
                child_increment = _quantity(net_increment * _quantity(item.quantity))
                pending[item.material_id] = _quantity(pending.get(item.material_id, Decimal("0")) + child_increment)

    for material_id, gross_requirement in gross_by_material.items():
        available_stock, open_purchase, safety_stock, snapshot = details[material_id]
        run.results.append(
            MfgMrpResult(
                material_id=material_id,
                gross_requirement=gross_requirement,
                available_stock=available_stock,
                open_supply_quantity=open_purchase,
                safety_stock=safety_stock,
                net_requirement=net_by_material[material_id],
                source_snapshot=snapshot,
            )
        )
    run.status = "completed"
    mps.status = "planned"
    mps.updated_by = context.id
    db.flush()
    return run


def _get_mrp_run(db: Session, run_id: str, context: UserContext) -> MfgMrpRun:
    run = db.scalar(
        select(MfgMrpRun)
        .options(selectinload(MfgMrpRun.results))
        .where(MfgMrpRun.id == run_id, MfgMrpRun.org_id == context.org_id, MfgMrpRun.is_deleted.is_(False))
    )
    if run is None:
        raise AppError("MRP 运算记录不存在", code=404)
    return run


def confirm_mrp_result(db: Session, result_id: str, context: UserContext) -> dict:
    result = db.scalar(
        select(MfgMrpResult)
        .join(MfgMrpRun, MfgMrpRun.id == MfgMrpResult.run_id)
        .where(
            MfgMrpResult.id == result_id,
            MfgMrpResult.is_deleted.is_(False),
            MfgMrpRun.org_id == context.org_id,
            MfgMrpRun.is_deleted.is_(False),
        )
        .with_for_update()
    )
    if result is None:
        raise AppError("MRP 结果不存在", code=404)
    if result.confirmed_source_ids:
        return {"id": result.id, "status": result.status, "source_document_ids": result.confirmed_source_ids}
    if result.net_requirement <= 0:
        raise AppError("净需求为零，无需确认", code=400)

    now = local_now()
    request = PurchaseRequest(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "purchase_request", context.org_id, now.date()),
        department_id=context.department_id,
        requester_id=context.id,
        status="draft",
        request_date=now.date(),
        remark=f"MRP 结果 {result.id}",
        created_by=context.id,
        created_at=now,
        updated_at=now,
    )
    request.items = [
        PurchaseRequestItem(
            material_id=result.material_id,
            quantity=_quantity(result.net_requirement),
            line_no=1,
        )
    ]
    db.add(request)
    db.flush()
    source_document_ids = {"purchase_request_id": request.id, "purchase_request_item_id": request.items[0].id}
    result.status = "confirmed"
    result.source_type = "purchase_request"
    result.source_id = request.id
    result.confirmed_source_ids = source_document_ids
    db.flush()
    return {"id": result.id, "status": result.status, "source_document_ids": source_document_ids}
