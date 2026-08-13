from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.response import ok
from app.services.auth_service import UserContext
from app.services.dashboard_service import dashboard_overview, dashboard_phase2, report_center

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
def overview(period: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"), context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(dashboard_overview(db, context, period))

@router.get("/phase2")
def phase2(period: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"), warehouse_id: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(dashboard_phase2(db, context, period, warehouse_id))


@router.get("/report-center")
def report_center_api(period: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"), context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(report_center(db, context, period))
