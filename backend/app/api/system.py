from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.response import ok
from app.models.logging import SysOperationLog
from app.services.auth_service import UserContext, apply_data_scope

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/operation-logs")
def operation_logs(
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(SysOperationLog).order_by(SysOperationLog.created_at.desc()).limit(100)
    if not context.user.is_superuser:
        statement = statement.where(SysOperationLog.org_id == context.org_id)
    rows = db.scalars(statement).all()
    return ok(
        [
            {
                "id": row.id,
                "action": row.action,
                "resource": row.resource,
                "username": row.username,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    )
