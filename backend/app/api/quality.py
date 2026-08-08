from fastapi import APIRouter,Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.quality import InspectionCreate, QaPlanCreate,InspectionResult
from app.services.auth_service import UserContext
from app.services.quality_service import *
from app.models.quality import QaInspection
router=APIRouter(prefix="/api/quality",tags=["quality"])
@router.get("/inspections")
def inspections(context:UserContext=Depends(get_current_user),db:Session=Depends(get_db)):
    rows = db.scalars(select(QaInspection).where(QaInspection.org_id == context.org_id).order_by(QaInspection.created_at.desc())).all()
    return ok([{"id": row.id, "inspection_type": row.inspection_type, "source_type": row.source_type, "source_id": row.source_id, "status": row.status, "result": row.result, "disposition": row.disposition} for row in rows])
@router.post("/plans")
def plan(payload:QaPlanCreate,context:UserContext=Depends(require_permission("quality:manage")),db:Session=Depends(get_db)): row=create_quality_plan(db,payload.model_dump(),context);db.commit();return ok({"id":row.id})
@router.post("/inspections")
def inspection(payload:InspectionCreate,context:UserContext=Depends(require_permission("quality:manage")),db:Session=Depends(get_db)): row=create_inspection(db,payload.inspection_type,payload.source_type,payload.source_id,context);db.commit();return ok({"id":row.id,"status":row.status})
@router.post("/inspections/{inspection_id}/submit")
def submit(inspection_id:str,results:list[InspectionResult],context:UserContext=Depends(require_permission("quality:manage")),db:Session=Depends(get_db)): row=submit_inspection(db,inspection_id,[x.model_dump() for x in results],context);db.commit();return ok({"id":row.id,"status":row.status,"result":row.result})
@router.post("/inspections/{inspection_id}/close")
def close(inspection_id:str,payload:dict,context:UserContext=Depends(require_permission("quality:manage")),db:Session=Depends(get_db)): row=close_inspection(db,inspection_id,payload.get("disposition"),context);db.commit();return ok({"id":row.id,"status":row.status})
