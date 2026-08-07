from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.response import ok
from app.schemas.platform import ApiClientCreate
from app.services.auth_service import UserContext
from app.services.openapi_service import create_api_client
from app.models.platform import ExtEventOutbox
from sqlalchemy import select
router=APIRouter(prefix="/api/platform",tags=["platform"])
@router.post("/api-clients")
def api_client(payload:ApiClientCreate,context:UserContext=Depends(get_current_user),db:Session=Depends(get_db)):
 row,secret=create_api_client(db,payload.model_dump(),context);db.commit();return ok({"id":row.id,"client_key":row.client_key,"secret":secret,"scopes":row.scopes})
@router.get("/events")
def events(status:str|None=None,context:UserContext=Depends(get_current_user),db:Session=Depends(get_db)):
 q=select(ExtEventOutbox).where(ExtEventOutbox.org_id==context.org_id);q=q.where(ExtEventOutbox.status==status) if status else q;return ok([{"id":r.id,"status":r.status,"event_type":r.event_type,"retry_count":r.retry_count} for r in db.scalars(q).all()])
