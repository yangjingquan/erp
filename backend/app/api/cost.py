from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.response import ok
from app.schemas.cost import CostAllocationCreate
from app.services.auth_service import UserContext
from app.services.cost_service import calculate_project_cost, close_period, create_allocation, post_allocation, reopen_period

router = APIRouter(prefix="/api/cost", tags=["cost"])

@router.post("/allocations")
def allocation(payload: CostAllocationCreate, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    row = create_allocation(db, payload.model_dump(), context); db.commit(); return ok({"id": row.id, "status": row.status})

@router.post("/allocations/{allocation_id}/post")
def post(allocation_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    row = post_allocation(db, allocation_id, context); db.commit(); return ok({"id": row.id, "status": row.status})

@router.get("/projects/{project_id}")
def project_cost(project_id: str, period: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(calculate_project_cost(db, project_id, period, context))

@router.post("/periods/{period}/close")
def close(period: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    row = close_period(db, context.org_id, period, context); db.commit(); return ok({"id": row.id, "status": row.status})

@router.post("/periods/{period}/reopen")
def reopen(period: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    row = reopen_period(db, context.org_id, period, context); db.commit(); return ok({"id": row.id, "status": row.status})
