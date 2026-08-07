from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.response import ok
from app.services.auth_service import UserContext
from app.services.dashboard_service import dashboard_overview, dashboard_phase2

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
def overview(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(dashboard_overview(db, context))

@router.get("/phase2")
def phase2(period: str, warehouse_id: str | None = None, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(dashboard_phase2(db, context, period, warehouse_id))
