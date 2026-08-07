from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.master_data import MdCustomer, MdMaterial, MdSupplier
from app.models.purchase import PurchaseOrder
from app.models.sales import SalesOrder
from app.services.auth_service import UserContext


def global_search(db: Session, context: UserContext, keyword: str) -> list[dict]:
    value = keyword.strip()
    if not value:
        return []
    pattern = f"%{value}%"
    result: list[dict] = []
    for model, resource, fields in [
        (MdMaterial, "material", [MdMaterial.code, MdMaterial.name]),
        (MdCustomer, "customer", [MdCustomer.code, MdCustomer.name]),
        (MdSupplier, "supplier", [MdSupplier.code, MdSupplier.name]),
        (SalesOrder, "sales_order", [SalesOrder.doc_no]),
        (PurchaseOrder, "purchase_order", [PurchaseOrder.doc_no]),
    ]:
        conditions = [field.like(pattern) for field in fields]
        rows = db.scalars(select(model).where(model.org_id == context.org_id, or_(*conditions)).limit(20)).all()
        for row in rows:
            result.append({
                "resource": resource,
                "id": row.id,
                "code": getattr(row, "code", None),
                "name": getattr(row, "name", None),
                "doc_no": getattr(row, "doc_no", None),
            })
    return result
