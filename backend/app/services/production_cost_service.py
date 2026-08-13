from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError
from app.core.time import local_today
from app.models.finance import FinAccount, FinVoucher, FinVoucherEntry
from app.models.inventory import InvStock
from app.models.master_data import MdMaterial
from app.models.production import (
    MfgMaterialIssue,
    MfgReport,
    MfgSubcontractOrder,
    MfgSubcontractReceipt,
    MfgWorkCenter,
    MfgWorkOrder,
    MfgWorkOrderCost,
)
from app.services.audit_service import write_operation_log
from app.services.auth_service import UserContext
from app.services.ledger_service import assert_fiscal_period_open, ensure_default_accounts, post_voucher

CENT = Decimal("0.01")
QUANTITY = Decimal("0.000001")


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def _quantity(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(QUANTITY, rounding=ROUND_HALF_UP)


def serialize_work_order_cost(row: MfgWorkOrderCost | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row.id,
        "work_order_id": row.work_order_id,
        "material_cost": str(row.material_cost),
        "labor_cost": str(row.labor_cost),
        "overhead_cost": str(row.overhead_cost),
        "subcontract_cost": str(row.subcontract_cost),
        "scrap_cost": str(row.scrap_cost),
        "total_cost": str(row.total_cost),
        "actual_unit_cost": f"{row.actual_unit_cost:.6f}",
        "standard_cost": str(row.standard_cost),
        "variance_amount": str(row.variance_amount),
        "voucher_id": row.voucher_id,
        "status": row.status,
        "details": row.cost_detail_json,
    }


def _material_cost(db: Session, work_order: MfgWorkOrder) -> tuple[Decimal, list[dict]]:
    issues = db.scalars(select(MfgMaterialIssue).options(selectinload(MfgMaterialIssue.items)).where(
        MfgMaterialIssue.org_id == work_order.org_id,
        MfgMaterialIssue.work_order_id == work_order.id,
        MfgMaterialIssue.is_deleted.is_(False),
    )).unique().all()
    details: dict[str, dict] = {}
    total = Decimal("0")
    for issue in issues:
        for item in issue.items:
            if item.is_deleted:
                continue
            net_quantity = _quantity(item.quantity - item.returned_quantity)
            amount = _money(net_quantity * item.unit_cost)
            total += amount
            detail = details.setdefault(item.material_id, {"material_id": item.material_id, "quantity": Decimal("0"), "amount": Decimal("0")})
            detail["quantity"] += net_quantity
            detail["amount"] += amount
    return _money(total), [{"material_id": item["material_id"], "quantity": f"{item['quantity']:.6f}", "amount": str(_money(item["amount"]))} for item in details.values()]


def _conversion_cost(db: Session, work_order: MfgWorkOrder) -> tuple[Decimal, Decimal, list[dict]]:
    reports = db.scalars(select(MfgReport).where(
        MfgReport.work_order_id == work_order.id,
        MfgReport.is_deleted.is_(False),
    ).order_by(MfgReport.report_time, MfgReport.id)).all()
    operations = {str(item.get("id")): item for item in (work_order.routing_snapshot or {}).get("operations", []) if item.get("id")}
    center_ids = {str(item.get("work_center_id")) for item in operations.values() if item.get("work_center_id")}
    centers = db.scalars(select(MfgWorkCenter).where(
        MfgWorkCenter.org_id == work_order.org_id,
        MfgWorkCenter.id.in_(center_ids),
        MfgWorkCenter.is_deleted.is_(False),
    )).all() if center_ids else []
    center_map = {row.id: row for row in centers}
    labor = Decimal("0")
    overhead = Decimal("0")
    details: list[dict] = []
    for report in reports:
        operation = operations.get(str(report.operation_id), {})
        center = center_map.get(str(operation.get("work_center_id")))
        labor_rate = _money(center.labor_rate if center else 0)
        overhead_rate = _money(center.overhead_rate if center else 0)
        hours = _quantity(report.hours)
        labor_amount = _money(hours * labor_rate)
        overhead_amount = _money(hours * overhead_rate)
        labor += labor_amount
        overhead += overhead_amount
        details.append({
            "report_id": report.id, "operation_id": report.operation_id,
            "operation_name": report.operation_name, "hours": f"{hours:.6f}",
            "labor_rate": str(labor_rate), "overhead_rate": str(overhead_rate),
            "labor_amount": str(labor_amount), "overhead_amount": str(overhead_amount),
        })
    return _money(labor), _money(overhead), details


def _subcontract_cost(db: Session, work_order: MfgWorkOrder) -> tuple[Decimal, list[dict]]:
    orders = db.scalars(select(MfgSubcontractOrder).where(
        MfgSubcontractOrder.org_id == work_order.org_id,
        MfgSubcontractOrder.source_type.in_(("mfg_work_order", "work_order")),
        MfgSubcontractOrder.source_id == work_order.id,
        MfgSubcontractOrder.is_deleted.is_(False),
    )).all()
    if not orders:
        return Decimal("0.00"), []
    order_ids = [row.id for row in orders]
    receipts = db.scalars(select(MfgSubcontractReceipt).where(
        MfgSubcontractReceipt.org_id == work_order.org_id,
        MfgSubcontractReceipt.subcontract_order_id.in_(order_ids),
        MfgSubcontractReceipt.is_deleted.is_(False),
    )).all()
    total = _money(sum((row.processing_fee_amount for row in receipts), Decimal("0")))
    return total, [{"receipt_id": row.id, "subcontract_order_id": row.subcontract_order_id, "amount": str(_money(row.processing_fee_amount))} for row in receipts]


def _create_cost_voucher(db: Session, cost: MfgWorkOrderCost, context: UserContext) -> FinVoucher:
    from app.services.finance_service import _new_finance_doc_no

    assert_fiscal_period_open(db, context.org_id, local_today())
    ensure_default_accounts(db, context.org_id)
    components = [
        ("1403", "实际耗用原材料", cost.material_cost),
        ("2211", "实际人工成本", cost.labor_cost),
        ("4101", "实际制造费用", cost.overhead_cost),
        ("2202", "实际委外加工费", cost.subcontract_cost),
    ]
    used_codes = {"1405", *(code for code, _, amount in components if amount > 0)}
    accounts = db.scalars(select(FinAccount).where(
        FinAccount.org_id == context.org_id, FinAccount.code.in_(used_codes),
        FinAccount.status == "active", FinAccount.allow_posting.is_(True), FinAccount.is_deleted.is_(False),
    )).all()
    account_map = {row.code: row for row in accounts}
    if set(account_map) != used_codes:
        raise AppError("生产成本结转所需会计科目缺失或不可记账", code=409)
    voucher = FinVoucher(
        org_id=context.org_id, voucher_no=_new_finance_doc_no("PC", context),
        voucher_date=local_today(), period=local_today().strftime("%Y-%m"),
        source_type="mfg_work_order_cost", source_id=cost.id, status="draft",
        total_debit=cost.total_cost, total_credit=cost.total_cost,
    )
    finished_account = account_map["1405"]
    entries = [FinVoucherEntry(
        line_no=1, account_id=finished_account.id, account_code=finished_account.code,
        account_name=finished_account.name, summary="生产完工实际成本入库",
        debit_amount=cost.total_cost, credit_amount=0, dimensions_json={},
    )]
    for code, summary, amount in components:
        if amount <= 0:
            continue
        account = account_map[code]
        entries.append(FinVoucherEntry(
            line_no=len(entries) + 1, account_id=account.id, account_code=account.code,
            account_name=account.name, summary=summary, debit_amount=0,
            credit_amount=amount, dimensions_json={},
        ))
    voucher.entries = entries
    db.add(voucher)
    db.flush()
    post_voucher(db, voucher.id, context)
    return voucher


def calculate_and_post_work_order_cost(
    db: Session,
    work_order: MfgWorkOrder,
    completion_quantity: Decimal,
    material: MdMaterial,
    context: UserContext,
) -> MfgWorkOrderCost:
    existing = db.scalar(select(MfgWorkOrderCost).where(
        MfgWorkOrderCost.org_id == context.org_id,
        MfgWorkOrderCost.work_order_id == work_order.id,
        MfgWorkOrderCost.is_deleted.is_(False),
    ).with_for_update())
    if existing:
        return existing
    material_cost, material_details = _material_cost(db, work_order)
    if work_order.materials and material_cost <= 0:
        # Legacy work orders could be completed without a material-issue document.
        # Preserve that flow while making the fallback explicit in the cost detail.
        material_ids = {line.material_id for line in work_order.materials if not line.is_deleted}
        materials = db.scalars(select(MdMaterial).where(
            MdMaterial.org_id == context.org_id,
            MdMaterial.id.in_(material_ids),
            MdMaterial.is_deleted.is_(False),
        )).all()
        material_map = {row.id: row for row in materials}
        stock_rows = db.scalars(select(InvStock).where(
            InvStock.org_id == context.org_id,
            InvStock.warehouse_id == work_order.warehouse_id,
            InvStock.material_id.in_(material_ids),
        )).all()
        stock_cost_map = {row.material_id: row.average_cost for row in stock_rows}
        ratio = Decimal("1") if work_order.quantity <= 0 else completion_quantity / work_order.quantity
        fallback_details = []
        for line in work_order.materials:
            component = material_map.get(line.material_id)
            if line.is_deleted or component is None:
                continue
            quantity = _quantity(line.required_quantity * ratio)
            unit_cost = stock_cost_map.get(line.material_id) or component.standard_cost
            amount = _money(quantity * unit_cost)
            material_cost += amount
            fallback_details.append({"material_id": line.material_id, "quantity": f"{quantity:.6f}", "unit_cost": str(unit_cost), "amount": str(amount), "source": "inventory_or_standard_cost_fallback"})
        material_cost = _money(material_cost)
        material_details = fallback_details
    labor_cost, overhead_cost, conversion_details = _conversion_cost(db, work_order)
    subcontract_cost, subcontract_details = _subcontract_cost(db, work_order)
    total_cost = _money(material_cost + labor_cost + overhead_cost + subcontract_cost)
    if total_cost <= 0:
        material_cost = _money(material.standard_cost * completion_quantity)
        material_details = [{"material_id": material.id, "quantity": f"{completion_quantity:.6f}", "amount": str(material_cost), "source": "finished_standard_cost_fallback"}]
        total_cost = material_cost
    if total_cost <= 0:
        raise AppError("工单实际成本及标准成本均为零，请先维护成本数据", code=409)
    good_quantity = _quantity(completion_quantity)
    output_quantity = _quantity(work_order.reported_good_quantity + work_order.reported_scrap_quantity)
    scrap_ratio = Decimal("0") if output_quantity <= 0 else work_order.reported_scrap_quantity / output_quantity
    scrap_cost = _money(total_cost * scrap_ratio)
    standard_cost = _money(material.standard_cost * good_quantity)
    row = MfgWorkOrderCost(
        org_id=context.org_id, work_order_id=work_order.id, material_cost=material_cost,
        labor_cost=labor_cost, overhead_cost=overhead_cost, subcontract_cost=subcontract_cost,
        scrap_cost=scrap_cost, total_cost=total_cost,
        actual_unit_cost=(total_cost / good_quantity).quantize(QUANTITY, rounding=ROUND_HALF_UP),
        standard_cost=standard_cost, variance_amount=_money(total_cost - standard_cost),
        status="calculated", cost_detail_json={
            "materials": material_details, "conversion": conversion_details,
            "subcontract": subcontract_details, "reported_good_quantity": f"{work_order.reported_good_quantity:.6f}",
            "reported_scrap_quantity": f"{work_order.reported_scrap_quantity:.6f}",
        },
    )
    db.add(row)
    db.flush()
    voucher = _create_cost_voucher(db, row, context)
    row.voucher_id = voucher.id
    row.status = "posted"
    write_operation_log(db, user=context.user, action="calculate", resource="mfg_work_order_cost", target_id=row.id, detail={"work_order_id": work_order.id, "total_cost": str(total_cost), "voucher_id": voucher.id})
    db.flush()
    return row


def get_work_order_cost(db: Session, work_order_id: str, context: UserContext) -> dict | None:
    row = db.scalar(select(MfgWorkOrderCost).where(
        MfgWorkOrderCost.org_id == context.org_id,
        MfgWorkOrderCost.work_order_id == work_order_id,
        MfgWorkOrderCost.is_deleted.is_(False),
    ))
    return serialize_work_order_cost(row)
