from decimal import Decimal
import calendar
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inventory import InvStock
from app.models.finance import SalesReceivable
from app.models.cost import CostAllocation
from app.models.crm import CrmLead, CrmOpportunity
from app.models.hr import HrPayroll
from app.models.production import MfgWorkOrder
from app.models.quality import QaInspection
from app.models.master_data import MdCustomer, MdMaterial
from app.models.purchase import PurchaseOrder
from app.models.sales import SalesOrder, SalesDelivery
from app.core.time import local_now, local_today
from app.services.auth_service import UserContext


def _period_bounds(period: str | None) -> tuple[date, date]:
    selected = period or local_today().strftime("%Y-%m")
    try:
        year, month = (int(value) for value in selected.split("-"))
        if month < 1 or month > 12 or len(selected) != 7:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("经营看板期间必须为 YYYY-MM")
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def _sum_orders(db: Session, model, org_id: str, start: date, end: date) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(model.total_amount), 0)).where(
            model.org_id == org_id,
            model.order_date.between(start, end),
            model.status.not_in(["cancelled", "draft"]),
        )
    )
    return Decimal(value or 0).quantize(Decimal("0.01"))


def _change(current: Decimal, previous: Decimal) -> float:
    if previous == 0:
        return 0.0
    return round(float((current - previous) / previous * 100), 1)


def dashboard_overview(db: Session, context: UserContext, period: str | None = None) -> dict:
    start, end = _period_bounds(period)
    previous_end = start - timedelta(days=1)
    previous_start = date(previous_end.year, previous_end.month, 1)
    sales_total = _sum_orders(db, SalesOrder, context.org_id, start, end)
    purchase_total = _sum_orders(db, PurchaseOrder, context.org_id, start, end)
    previous_sales_total = _sum_orders(db, SalesOrder, context.org_id, previous_start, previous_end)
    previous_purchase_total = _sum_orders(db, PurchaseOrder, context.org_id, previous_start, previous_end)
    receivable_total = db.scalar(
        select(func.coalesce(func.sum(SalesReceivable.total_amount - SalesReceivable.reconciled_amount), 0)).where(
            SalesReceivable.org_id == context.org_id,
            SalesReceivable.status != "settled",
        )
    ) or Decimal("0")
    warning_count = db.scalar(
        select(func.count())
        .select_from(InvStock)
        .join(MdMaterial, MdMaterial.id == InvStock.material_id)
        .where(InvStock.org_id == context.org_id, InvStock.quantity < MdMaterial.min_stock)
    ) or 0
    orders = db.scalars(
        select(SalesOrder).where(
            SalesOrder.org_id == context.org_id,
            SalesOrder.order_date.between(start, end),
            SalesOrder.status.not_in(["cancelled", "draft"]),
        ).order_by(SalesOrder.order_date.desc(), SalesOrder.created_at.desc()).limit(3)
    ).all()
    customer_ids = {row.customer_id for row in orders}
    customer_names = {
        row.id: row.name
        for row in db.scalars(select(MdCustomer).where(
            MdCustomer.org_id == context.org_id,
            MdCustomer.id.in_(customer_ids),
            MdCustomer.is_deleted.is_(False),
        )).all()
    } if customer_ids else {}
    materials = db.scalars(
        select(MdMaterial).where(
            MdMaterial.org_id == context.org_id,
            MdMaterial.is_deleted.is_(False),
        ).order_by(MdMaterial.created_at.desc()).limit(3)
    ).all()
    pending_review = db.scalar(select(func.count()).select_from(SalesOrder).where(SalesOrder.org_id == context.org_id, SalesOrder.status == "submitted")) or 0
    overdue = db.scalar(select(func.count()).select_from(SalesReceivable).where(SalesReceivable.org_id == context.org_id, SalesReceivable.status != "settled", SalesReceivable.due_date.is_not(None), SalesReceivable.due_date < local_today())) or 0
    today = local_today()
    trend_end = min(end, today) if (end.year, end.month) == (today.year, today.month) else end
    trend_start = max(start, trend_end - timedelta(days=6))
    trend_orders = db.scalars(select(SalesOrder).where(SalesOrder.org_id == context.org_id, SalesOrder.order_date.between(trend_start, trend_end), SalesOrder.status.not_in(["cancelled", "draft"]))).all()
    trend_purchases = db.scalars(select(PurchaseOrder).where(PurchaseOrder.org_id == context.org_id, PurchaseOrder.order_date.between(trend_start, trend_end), PurchaseOrder.status.not_in(["cancelled", "draft"]))).all()
    trend = []
    cursor = trend_start
    while cursor <= trend_end:
        trend.append({
            "label": cursor.strftime("%m/%d"),
            "sales": sum((Decimal(row.total_amount) for row in trend_orders if row.order_date == cursor), Decimal("0")),
            "purchase": sum((Decimal(row.total_amount) for row in trend_purchases if row.order_date == cursor), Decimal("0")),
        })
        cursor += timedelta(days=1)
    receivable_total = Decimal(receivable_total).quantize(Decimal("0.01"))
    return {
        "period": start.strftime("%Y-%m"),
        "sales_total": sales_total,
        "purchase_total": purchase_total,
        "receivable_total": receivable_total,
        "inventory_warning_count": int(warning_count),
        "sales_change": _change(sales_total, previous_sales_total),
        "purchase_change": _change(purchase_total, previous_purchase_total),
        "trend": trend,
        "tasks": [
            {"key": "sales_review", "label": "销售订单待审核", "description": "销售管理", "count": int(pending_review), "path": "/sales/orders"},
            {"key": "inventory_warning", "label": "库存低于安全线", "description": "库存管理", "count": int(warning_count), "path": "/inventory/stock"},
            {"key": "receivable_overdue", "label": "应收账款逾期", "description": "财务管理", "count": int(overdue), "path": "/finance/receivables"},
        ],
        "materials": [
            {"id": row.id, "code": row.code, "name": row.name, "material_type": row.material_type, "min_stock": str(row.min_stock), "status": "active"}
            for row in materials
        ],
        "sales_orders": [
            {"id": row.id, "doc_no": row.doc_no, "customer_id": row.customer_id, "customer_name": customer_names.get(row.customer_id, row.customer_id), "total_amount": str(row.total_amount), "status": row.status}
            for row in orders
        ],
    }

def dashboard_phase2(db: Session, context: UserContext, period: str, warehouse_id: str | None = None) -> dict:
    start, end = _period_bounds(period)
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time())
    stock_statement = select(func.coalesce(func.sum(InvStock.quantity), 0)).where(InvStock.org_id == context.org_id)
    if warehouse_id:
        stock_statement = stock_statement.where(InvStock.warehouse_id == warehouse_id)
    production_count = db.scalar(select(func.count()).select_from(MfgWorkOrder).where(MfgWorkOrder.org_id == context.org_id, MfgWorkOrder.plan_date.between(start, end))) or 0
    inventory_total = db.scalar(stock_statement) or Decimal("0")
    crm_count = db.scalar(select(func.count()).select_from(CrmLead).where(CrmLead.org_id == context.org_id, CrmLead.created_at >= start_dt, CrmLead.created_at < end_dt)) or 0
    crm_count += db.scalar(select(func.count()).select_from(CrmOpportunity).where(CrmOpportunity.org_id == context.org_id, CrmOpportunity.created_at >= start_dt, CrmOpportunity.created_at < end_dt)) or 0
    quality_count = db.scalar(select(func.count()).select_from(QaInspection).where(QaInspection.org_id == context.org_id, QaInspection.created_at >= start_dt, QaInspection.created_at < end_dt)) or 0
    payroll_total = db.scalar(select(func.coalesce(func.sum(HrPayroll.total_amount), 0)).where(HrPayroll.org_id == context.org_id, HrPayroll.period == period)) or Decimal("0")
    cost_total = db.scalar(select(func.coalesce(func.sum(CostAllocation.amount), 0)).where(CostAllocation.org_id == context.org_id, CostAllocation.period == period, CostAllocation.status != "cancelled")) or Decimal("0")
    now = local_now().isoformat()
    base = {"period": period, "source": "erp operational tables", "updated_at": now}
    return {
        "production": {**base, "total": int(production_count), "unit": "work_orders"},
        "inventory": {**base, "total": Decimal(inventory_total), "unit": "quantity"},
        "crm": {**base, "total": int(crm_count), "unit": "records"},
        "quality": {**base, "total": int(quality_count), "unit": "inspections"},
        "hr": {**base, "total": Decimal(payroll_total), "unit": "amount"},
        "project_cost": {**base, "total": Decimal(cost_total), "unit": "amount"},
    }


def report_center(db: Session, context: UserContext, period: str | None = None) -> dict:
    """Stable, export-friendly KPI contract for management reports."""
    start, end = _period_bounds(period)
    sales = db.scalars(select(SalesOrder).where(SalesOrder.org_id == context.org_id, SalesOrder.order_date.between(start, end), SalesOrder.status.not_in(["draft", "cancelled"]))).all()
    deliveries = db.scalars(select(SalesDelivery).where(SalesDelivery.org_id == context.org_id, SalesDelivery.delivery_date.between(start, end), SalesDelivery.status == "completed")).all()
    sales_amount = sum((Decimal(row.total_amount) for row in sales), Decimal("0"))
    delivered_amount = sum((Decimal(row.total_amount) for row in deliveries), Decimal("0"))
    order_lines = sum((len(row.items) for row in sales), 0)
    delivered_lines = sum((len(row.items) for row in deliveries), 0)
    stock_value = db.scalar(select(func.coalesce(func.sum(InvStock.quantity * InvStock.average_cost), 0)).where(InvStock.org_id == context.org_id)) or 0
    overdue_amount = db.scalar(select(func.coalesce(func.sum(SalesReceivable.total_amount - SalesReceivable.reconciled_amount), 0)).where(SalesReceivable.org_id == context.org_id, SalesReceivable.status != "settled", SalesReceivable.due_date < local_today())) or 0
    failed_quality = db.scalar(select(func.count()).select_from(QaInspection).where(QaInspection.org_id == context.org_id, QaInspection.created_at >= datetime.combine(start, datetime.min.time()), QaInspection.created_at < datetime.combine(end + timedelta(days=1), datetime.min.time()), QaInspection.result == "failed")) or 0
    work_orders = db.scalars(select(MfgWorkOrder).where(MfgWorkOrder.org_id == context.org_id, MfgWorkOrder.plan_date.between(start, end), MfgWorkOrder.is_deleted.is_(False))).all()
    planned = sum((Decimal(row.quantity) for row in work_orders), Decimal("0"))
    completed = sum((Decimal(row.completed_quantity) for row in work_orders), Decimal("0"))
    return {"period": start.strftime("%Y-%m"), "generated_at": local_now().isoformat(), "metrics": {
        "sales_amount": str(sales_amount.quantize(Decimal("0.01"))),
        "delivery_amount": str(delivered_amount.quantize(Decimal("0.01"))),
        "fulfillment_rate": round(float(delivered_amount / sales_amount * 100), 2) if sales_amount else 0,
        "order_line_fulfillment_rate": round(delivered_lines / order_lines * 100, 2) if order_lines else 0,
        "inventory_value": str(Decimal(stock_value).quantize(Decimal("0.01"))),
        "overdue_receivable": str(Decimal(overdue_amount).quantize(Decimal("0.01"))),
        "failed_inspections": int(failed_quality),
        "production_completion_rate": round(float(completed / planned * 100), 2) if planned else 0,
    }, "definitions": {"fulfillment_rate": "已完成销售出库金额/期间已审核销售订单金额", "inventory_value": "库存数量×当前平均成本", "production_completion_rate": "完工数量/计划数量"}}
