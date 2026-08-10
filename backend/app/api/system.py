from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.response import ok
from app.models.logging import SysOperationLog
from app.services.auth_service import UserContext, apply_data_scope

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/operation-logs")
def operation_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(SysOperationLog)
    if not context.user.is_superuser:
        statement = statement.where(SysOperationLog.org_id == context.org_id)
    total = int(db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = db.scalars(
        statement.order_by(SysOperationLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ok(
        {
            "items": [
                {
                    "id": row.id,
                    "action": row.action,
                    "resource": row.resource,
                    "username": row.username,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )
