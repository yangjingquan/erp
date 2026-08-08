from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.response import ok
from app.schemas.platform import ApiClientCreate
from app.services.auth_service import UserContext
from app.services.openapi_service import create_api_client
from app.models.platform import ExtEventOutbox, SysApiClient
from sqlalchemy import select
router=APIRouter(prefix="/api/platform",tags=["platform"])
@router.post("/api-clients")
def api_client(payload:ApiClientCreate,context:UserContext=Depends(require_permission("config:manage")),db:Session=Depends(get_db)):
 row,secret=create_api_client(db,payload.model_dump(),context);db.commit();return ok({"id":row.id,"client_key":row.client_key,"secret":secret,"scopes":row.scopes})
@router.get("/api-clients")
def api_clients(context:UserContext=Depends(get_current_user),db:Session=Depends(get_db)):
 rows=db.scalars(select(SysApiClient).where(SysApiClient.org_id==context.org_id).order_by(SysApiClient.created_at.desc())).all()
 return ok([{"id":row.id,"client_key":row.client_key,"scopes":row.scopes,"status":row.status,"created_at":row.created_at.isoformat()} for row in rows])
@router.post("/api-clients/{client_id}/status")
def api_client_status(client_id:str,payload:dict,context:UserContext=Depends(require_permission("config:manage")),db:Session=Depends(get_db)):
 row=db.scalar(select(SysApiClient).where(SysApiClient.id==client_id,SysApiClient.org_id==context.org_id))
 if row is None: raise AppError("API 客户端不存在",code=404)
 if payload.get("status") not in {"active","inactive"}: raise AppError("客户端状态无效",code=400)
 row.status=payload["status"];db.commit();return ok({"id":row.id,"status":row.status})
@router.get("/events")
def events(status:str|None=None,context:UserContext=Depends(get_current_user),db:Session=Depends(get_db)):
 q=select(ExtEventOutbox).where(ExtEventOutbox.org_id==context.org_id);q=q.where(ExtEventOutbox.status==status) if status else q;return ok([{"id":r.id,"status":r.status,"event_type":r.event_type,"retry_count":r.retry_count} for r in db.scalars(q).all()])
