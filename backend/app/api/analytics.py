from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.analytics import ReportDefinitionCreate, ReportRunRequest
from app.services.analytics_service import (
    create_report_definition,
    get_report_run,
    list_report_definitions,
    list_report_runs,
    report_run_csv,
    run_report,
    serialize_run,
)
from app.services.auth_service import UserContext

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/reports")
def reports(context: UserContext = Depends(require_permission("dashboard:view")), db: Session = Depends(get_db)):
    return ok(list_report_definitions(db, context))


@router.post("/reports")
def create_report(payload: ReportDefinitionCreate, context: UserContext = Depends(require_permission("config:manage")), db: Session = Depends(get_db)):
    row = create_report_definition(db, payload, context)
    db.commit()
    return ok({"id": row.id, "report_key": row.report_key, "name": row.name, "description": row.description, "parameters": row.parameters_json, "status": row.status})


@router.post("/reports/{report_id}/run")
def execute_report(report_id: str, payload: ReportRunRequest, context: UserContext = Depends(require_permission("dashboard:view")), db: Session = Depends(get_db)):
    result = run_report(db, report_id, payload, context)
    db.commit()
    return ok(result)


@router.get("/runs")
def runs(limit: int = Query(default=50, ge=1, le=100), context: UserContext = Depends(require_permission("dashboard:view")), db: Session = Depends(get_db)):
    return ok(list_report_runs(db, context, limit))


@router.get("/runs/{run_id}")
def run_detail(run_id: str, context: UserContext = Depends(require_permission("dashboard:view")), db: Session = Depends(get_db)):
    return ok(serialize_run(get_report_run(db, run_id, context)))


@router.get("/runs/{run_id}/export")
def export_run(run_id: str, context: UserContext = Depends(require_permission("dashboard:view")), db: Session = Depends(get_db)):
    filename, content = report_run_csv(get_report_run(db, run_id, context))
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
