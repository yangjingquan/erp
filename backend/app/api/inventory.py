from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.inventory import CountCreate, TransferCreate
from app.services.auth_service import UserContext
from app.services.inventory_service import (
    approve_transfer,
    complete_count,
    complete_transfer,
    create_count,
    delete_count,
    create_transfer,
    list_counts,
    list_safety_warnings,
    list_stock,
    list_stock_transactions,
    list_transfers,
    serialize_count,
    serialize_transfer,
    update_count,
)

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("/stock")
def stock(
    warehouse_id: str | None = None,
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = list_stock(db, context, warehouse_id)
    return ok([{"id": row.id, "warehouse_id": row.warehouse_id, "material_id": row.material_id, "quantity": str(row.quantity), "available_quantity": str(row.available_quantity)} for row in rows])


@router.get("/warnings")
def warnings(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_safety_warnings(db, context))


@router.get("/transactions")
def transactions(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_stock_transactions(db, context))


@router.get("/transfers")
def transfers(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_transfers(db, context))


@router.post("/transfers")
def create_transfer_api(payload: TransferCreate, context: UserContext = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)):
    transfer = create_transfer(
        db,
        context,
        from_warehouse_id=payload.from_warehouse_id,
        to_warehouse_id=payload.to_warehouse_id,
        items=[item.model_dump() for item in payload.items],
    )
    db.commit()
    return ok(serialize_transfer(transfer))


@router.post("/transfers/{transfer_id}/approve")
def approve_transfer_api(transfer_id: str, context: UserContext = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)):
    transfer = approve_transfer(db, transfer_id, context)
    db.commit()
    return ok(serialize_transfer(transfer))


@router.post("/transfers/{transfer_id}/complete")
def complete_transfer_api(transfer_id: str, context: UserContext = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)):
    transfer = complete_transfer(db, transfer_id, context)
    db.commit()
    return ok(serialize_transfer(transfer))


@router.get("/counts")
def counts(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_counts(db, context))


@router.post("/counts")
def create_count_api(payload: CountCreate, context: UserContext = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)):
    count = create_count(
        db,
        context,
        warehouse_id=payload.warehouse_id,
        items=[item.model_dump() for item in payload.items],
    )
    db.commit()
    return ok(serialize_count(count))


@router.put("/counts/{count_id}")
def update_count_api(count_id: str, payload: CountCreate, context: UserContext = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)):
    count = update_count(
        db,
        count_id,
        context,
        warehouse_id=payload.warehouse_id,
        items=[item.model_dump() for item in payload.items],
    )
    db.commit()
    return ok(serialize_count(count))


@router.delete("/counts/{count_id}")
def delete_count_api(count_id: str, context: UserContext = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)):
    delete_count(db, count_id, context)
    db.commit()
    return ok(msg="盘点单已删除")


@router.post("/counts/{count_id}/complete")
def complete_count_api(count_id: str, context: UserContext = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)):
    count = complete_count(db, count_id, context)
    db.commit()
    return ok(serialize_count(count))
