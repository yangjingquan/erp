from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.inventory_advanced import BatchCreate, FifoInboundCreate, FifoOutboundCreate, LocationCreate, ScanProcessCreate
from app.services.auth_service import UserContext
from app.services.inventory_advanced_service import (
    create_batch,
    create_location,
    create_scan_token,
    list_scan_tasks,
    list_locations,
    list_slow_moving,
    post_fifo_inbound,
    post_fifo_outbound,
    process_scan,
)


router = APIRouter(prefix="/api/inventory/advanced", tags=["inventory-advanced"])


def _serialize_location(row) -> dict:
    return {
        "id": row.id,
        "warehouse_id": row.warehouse_id,
        "zone_id": row.zone_id,
        "code": row.code,
        "name": row.name,
        "status": row.status,
    }


def _serialize_batch(row) -> dict:
    return {
        "id": row.id,
        "material_id": row.material_id,
        "batch_no": row.batch_no,
        "production_date": row.production_date.isoformat() if row.production_date else None,
        "expiry_date": row.expiry_date.isoformat() if row.expiry_date else None,
        "status": row.status,
    }


def _serialize_layer(row) -> dict:
    return {
        "id": row.id,
        "warehouse_id": row.warehouse_id,
        "location_id": row.location_id,
        "batch_id": row.batch_id,
        "material_id": row.material_id,
        "remaining_quantity": str(row.remaining_quantity),
        "unit_cost": str(row.unit_cost),
    }


@router.get("/locations")
def locations(
    warehouse_id: str = Query(min_length=1),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok([_serialize_location(row) for row in list_locations(db, warehouse_id, context)])


@router.post("/locations")
def create_location_api(
    warehouse_id: str = Query(min_length=1),
    zone_id: str | None = Query(default=None),
    payload: LocationCreate = None,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    row = create_location(db, warehouse_id, zone_id, payload, context)
    db.commit()
    return ok(_serialize_location(row))


@router.post("/batches")
def create_batch_api(
    material_id: str = Query(min_length=1),
    payload: BatchCreate = None,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    row = create_batch(db, material_id, payload, context)
    db.commit()
    return ok(_serialize_batch(row))


@router.post("/fifo/inbound")
def fifo_inbound(
    payload: FifoInboundCreate,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    layers = post_fifo_inbound(db, context=context, **payload.model_dump())
    db.commit()
    return ok([_serialize_layer(row) for row in layers])


@router.post("/fifo/outbound")
def fifo_outbound(
    payload: FifoOutboundCreate,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    consumed = post_fifo_outbound(db, context=context, **payload.model_dump())
    db.commit()
    return ok(consumed)


@router.get("/slow-moving")
def slow_moving(
    as_of: date = Query(default_factory=date.today),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(list_slow_moving(db, context, as_of))


@router.post("/scan/token")
def scan_token(
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    return ok({"token": create_scan_token(db, context)})


@router.get("/scan/tasks")
def scan_tasks(
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(list_scan_tasks(db, context))


@router.post("/scan/process")
def scan_process(payload: ScanProcessCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"token"})
    result = process_scan(
        db,
        payload.token,
        payload.scan_id,
        payload.action,
        payload.document_id,
        data,
    )
    db.commit()
    return ok(result)
