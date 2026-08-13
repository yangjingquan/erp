from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.models.quality import QaInspection
from app.schemas.quality import (
    CapaActionComplete,
    CapaActionCreate,
    InspectionClose,
    InspectionCreate,
    InspectionResult,
    NonconformanceClose,
    NonconformanceInvestigationUpdate,
    QaPlanCreate,
)
from app.services.auth_service import UserContext
from app.services.quality_service import (
    _serialize_action,
    close_inspection,
    close_nonconformance,
    complete_capa_action,
    create_capa_action,
    create_inspection,
    create_quality_plan,
    list_nonconformances,
    submit_inspection,
    update_nonconformance_investigation,
)

router = APIRouter(prefix="/api/quality", tags=["quality"])


@router.get("/inspections")
def inspections(
    context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)
):
    rows = db.scalars(
        select(QaInspection)
        .where(QaInspection.org_id == context.org_id, QaInspection.is_deleted.is_(False))
        .order_by(QaInspection.created_at.desc())
    ).all()
    return ok(
        [
            {
                "id": row.id,
                "inspection_type": row.inspection_type,
                "source_type": row.source_type,
                "source_id": row.source_id,
                "status": row.status,
                "result": row.result,
                "disposition": row.disposition,
            }
            for row in rows
        ]
    )


@router.post("/plans")
def plan(
    payload: QaPlanCreate,
    context: UserContext = Depends(require_permission("quality:manage")),
    db: Session = Depends(get_db),
):
    row = create_quality_plan(db, payload.model_dump(), context)
    db.commit()
    return ok({"id": row.id})


@router.post("/inspections")
def inspection(
    payload: InspectionCreate,
    context: UserContext = Depends(require_permission("quality:manage")),
    db: Session = Depends(get_db),
):
    row = create_inspection(
        db, payload.inspection_type, payload.source_type, payload.source_id, context
    )
    db.commit()
    return ok({"id": row.id, "status": row.status})


@router.post("/inspections/{inspection_id}/submit")
def submit(
    inspection_id: str,
    results: list[InspectionResult],
    context: UserContext = Depends(require_permission("quality:manage")),
    db: Session = Depends(get_db),
):
    row = submit_inspection(
        db, inspection_id, [result.model_dump() for result in results], context
    )
    db.commit()
    return ok({"id": row.id, "status": row.status, "result": row.result})


@router.post("/inspections/{inspection_id}/close")
def close(
    inspection_id: str,
    payload: InspectionClose,
    context: UserContext = Depends(require_permission("quality:manage")),
    db: Session = Depends(get_db),
):
    row = close_inspection(db, inspection_id, payload.disposition, context)
    db.commit()
    return ok({"id": row.id, "status": row.status})


@router.get("/nonconformances")
def nonconformances(
    context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)
):
    return ok(list_nonconformances(db, context))


@router.put("/nonconformances/{nonconformance_id}/investigation")
def save_investigation(
    nonconformance_id: str,
    payload: NonconformanceInvestigationUpdate,
    context: UserContext = Depends(require_permission("quality:manage")),
    db: Session = Depends(get_db),
):
    row = update_nonconformance_investigation(
        db, nonconformance_id, payload.model_dump(), context
    )
    db.commit()
    return ok({"id": row.id, "status": row.status})


@router.post("/nonconformances/{nonconformance_id}/actions")
def add_action(
    nonconformance_id: str,
    payload: CapaActionCreate,
    context: UserContext = Depends(require_permission("quality:manage")),
    db: Session = Depends(get_db),
):
    row = create_capa_action(db, nonconformance_id, payload.model_dump(), context)
    db.commit()
    return ok(_serialize_action(row))


@router.post("/capa-actions/{action_id}/complete")
def complete_action(
    action_id: str,
    payload: CapaActionComplete,
    context: UserContext = Depends(require_permission("quality:manage")),
    db: Session = Depends(get_db),
):
    row = complete_capa_action(db, action_id, payload.completion_evidence, context)
    db.commit()
    return ok(_serialize_action(row))


@router.post("/nonconformances/{nonconformance_id}/close")
def close_ncr(
    nonconformance_id: str,
    payload: NonconformanceClose,
    context: UserContext = Depends(require_permission("quality:manage")),
    db: Session = Depends(get_db),
):
    row = close_nonconformance(db, nonconformance_id, payload.closure_evidence, context)
    db.commit()
    return ok({"id": row.id, "status": row.status, "closed_at": row.closed_at})
