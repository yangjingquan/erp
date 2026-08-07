from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inventory import InvStock
from app.models.master_data import MdMaterial
from app.models.purchase import PurchaseOrder
from app.models.sales import SalesOrder
from app.services.auth_service import UserContext


def dashboard_overview(db: Session, context: UserContext) -> dict:
    sales_total = db.scalar(
        select(func.coalesce(func.sum(SalesOrder.total_amount), 0)).where(
            SalesOrder.org_id == context.org_id,
            SalesOrder.status.not_in(["cancelled", "draft"]),
        )
    ) or Decimal("0")
    purchase_total = db.scalar(
        select(func.coalesce(func.sum(PurchaseOrder.total_amount), 0)).where(
            PurchaseOrder.org_id == context.org_id,
            PurchaseOrder.status.not_in(["cancelled", "draft"]),
        )
    ) or Decimal("0")
    warning_count = db.scalar(
        select(func.count())
        .select_from(InvStock)
        .join(MdMaterial, MdMaterial.id == InvStock.material_id)
        .where(InvStock.org_id == context.org_id, InvStock.quantity < MdMaterial.min_stock)
    ) or 0
    return {
        "sales_total": Decimal(sales_total).quantize(Decimal("0.01")),
        "purchase_total": Decimal(purchase_total).quantize(Decimal("0.01")),
        "inventory_warning_count": int(warning_count),
    }

def dashboard_phase2(db: Session, context: UserContext, period: str, warehouse_id: str | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    base = {"period": period, "source": "erp operational tables", "updated_at": now}
    return {key: {**base, "total": Decimal("0.00")} for key in ("production", "inventory", "crm", "quality", "hr", "project_cost")}
