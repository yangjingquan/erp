from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.crm import LeadCreate, OpportunityCreate, FollowUpCreate
from app.services.auth_service import UserContext
from app.services.crm_service import *
router = APIRouter(prefix="/api/crm", tags=["crm"])
def _row(row): return {k: getattr(row, k) for k in ("id", "name", "status", "stage", "phone", "email", "source", "customer_id") if hasattr(row, k)}
@router.get("/leads")
def leads(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)): return ok([_row(x) for x in list_leads(db, context)])
@router.post("/leads")
def lead(payload: LeadCreate, context: UserContext = Depends(require_permission("crm:manage")), db: Session = Depends(get_db)): row=create_lead(db,payload.model_dump(),context); db.commit(); return ok(_row(row))
@router.post("/leads/{lead_id}/transition/{status}")
def lead_transition(lead_id: str,status: str,context: UserContext=Depends(require_permission("crm:manage")),db: Session=Depends(get_db)): row=transition_lead(db,lead_id,status,context);db.commit();return ok(_row(row))
@router.post("/leads/{lead_id}/convert")
def convert(lead_id: str,context: UserContext=Depends(require_permission("crm:manage")),db: Session=Depends(get_db)): result=convert_lead(db,lead_id,context);db.commit();return ok(result)
@router.get("/opportunities")
def opportunities(context: UserContext=Depends(get_current_user),db: Session=Depends(get_db)): return ok([_row(x) for x in list_opportunities(db,context)])
@router.post("/opportunities")
def opportunity(payload: OpportunityCreate,context: UserContext=Depends(require_permission("crm:manage")),db: Session=Depends(get_db)): row=create_opportunity(db,payload.model_dump(),context);db.commit();return ok(_row(row))
@router.post("/opportunities/{opportunity_id}/transition/{stage}")
def opportunity_transition(opportunity_id: str, stage: str, context: UserContext=Depends(require_permission("crm:manage")), db: Session=Depends(get_db)):
    row = transition_opportunity(db, opportunity_id, stage, context); db.commit(); return ok(_row(row))
@router.post("/opportunities/{opportunity_id}/follow-ups")
def followup(opportunity_id: str,payload: FollowUpCreate,context: UserContext=Depends(require_permission("crm:manage")),db: Session=Depends(get_db)): row=add_follow_up(db,opportunity_id,payload.model_dump(),context);db.commit();return ok(_row(row))
