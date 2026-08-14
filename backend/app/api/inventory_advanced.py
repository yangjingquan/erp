from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.inventory_advanced import BatchCreate, BatchUpdate, FifoInboundCreate, FifoOutboundCreate, LocationCreate, LocationUpdate, PickWaveCreate, ReservationCreate, ScanProcessCreate, WarehouseTaskCreate, WarehouseTaskTransition
from app.services.auth_service import UserContext
from app.services.inventory_advanced_service import (
    create_batch,
    create_location,
    delete_batch,
    delete_location,
    create_scan_token,
    list_scan_tasks,
    list_locations,
    list_batches,
    list_slow_moving,
    post_fifo_inbound,
    post_fifo_outbound,
    process_scan,
    update_batch,
    update_location,
    create_reservation,
    release_reservation,
    list_reservations,
    list_trace_events,
    create_warehouse_task,
    list_warehouse_tasks,
    transition_warehouse_task,
    create_pick_wave,
    list_pick_waves,
    release_pick_wave,
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
    warehouse_id: str | None = Query(default=None, min_length=1),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = list_locations(db, warehouse_id, context)
    return ok([_serialize_location(row) for row in rows])


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


@router.put("/locations/{location_id}")
def update_location_api(
    location_id: str,
    payload: LocationUpdate,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    row = update_location(db, location_id, payload, context)
    db.commit()
    return ok(_serialize_location(row))


@router.delete("/locations/{location_id}")
def delete_location_api(
    location_id: str,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    delete_location(db, location_id, context)
    db.commit()
    return ok(msg="库位已删除")


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


@router.put("/batches/{batch_id}")
def update_batch_api(
    batch_id: str,
    payload: BatchUpdate,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    row = update_batch(db, batch_id, payload, context)
    db.commit()
    return ok(_serialize_batch(row))


@router.delete("/batches/{batch_id}")
def delete_batch_api(
    batch_id: str,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    delete_batch(db, batch_id, context)
    db.commit()
    return ok(msg="批次已删除")


@router.get("/batches")
def batches(material_id: str | None = Query(default=None), context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok([_serialize_batch(row) for row in list_batches(db, material_id, context)])


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


@router.get("/reservations")
def reservations(status: str | None = Query(default=None), context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_reservations(db, context, status))


@router.post("/reservations")
def reserve(payload: ReservationCreate, context: UserContext = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)):
    row = create_reservation(db, payload, context)
    db.commit()
    return ok({"id": row.id, "status": row.status, "quantity": str(row.quantity)})


@router.post("/reservations/{reservation_id}/release")
def release(reservation_id: str, context: UserContext = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)):
    row = release_reservation(db, reservation_id, context)
    db.commit()
    return ok({"id": row.id, "status": row.status, "released_quantity": str(row.released_quantity)})


@router.get("/trace")
def trace(material_id: str | None = Query(default=None), batch_id: str | None = Query(default=None), context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_trace_events(db, context, material_id=material_id, batch_id=batch_id))


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


@router.get("/tasks")
def warehouse_tasks(
    status: str | None = Query(default=None),
    task_type: str | None = Query(default=None),
    warehouse_id: str | None = Query(default=None),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = list_warehouse_tasks(db, context, status=status, task_type=task_type, warehouse_id=warehouse_id)
    return ok({"items": rows, "total": len(rows), "page": 1, "page_size": len(rows), "summary": {"open": sum(row["status"] not in {"completed", "cancelled"} for row in rows)}})


@router.post("/tasks")
def create_warehouse_task_api(
    payload: WarehouseTaskCreate,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    row = create_warehouse_task(db, payload, context)
    db.commit()
    return ok({"id": row.id, "task_no": row.task_no, "status": row.status})


@router.post("/tasks/{task_id}/transition")
def transition_warehouse_task_api(
    task_id: str,
    payload: WarehouseTaskTransition,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    row = transition_warehouse_task(db, task_id, payload, context)
    db.commit()
    return ok({"id": row.id, "task_no": row.task_no, "status": row.status, "completed_quantity": str(row.completed_quantity), "wave_id": row.wave_id})


@router.get("/waves")
def pick_waves(status: str | None = Query(default=None), context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = list_pick_waves(db, context, status)
    return ok({"items": rows, "total": len(rows), "page": 1, "page_size": len(rows), "summary": {"released": sum(row["status"] == "released" for row in rows)}})


@router.post("/waves")
def create_pick_wave_api(
    payload: PickWaveCreate,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    row = create_pick_wave(db, payload, context)
    db.commit()
    return ok({"id": row.id, "wave_no": row.wave_no, "status": row.status})


@router.post("/waves/{wave_id}/release")
def release_pick_wave_api(
    wave_id: str,
    context: UserContext = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
):
    row = release_pick_wave(db, wave_id, context)
    db.commit()
    return ok({"id": row.id, "wave_no": row.wave_no, "status": row.status, "released_at": row.released_at.isoformat() if row.released_at else None})
