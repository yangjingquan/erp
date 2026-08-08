from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.services.auth_service import UserContext
from app.services.workflow_service import (
    approve_task,
    get_workflow_definition,
    reject_task,
    save_workflow_definition,
)

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


@router.get("/definitions/{business_type}")
def get_definition(business_type: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(get_workflow_definition(db, business_type, context))


@router.put("/definitions/{business_type}")
def save_definition(
    business_type: str,
    payload: dict,
    context: UserContext = Depends(require_permission("workflow:manage")),
    db: Session = Depends(get_db),
):
    result = save_workflow_definition(db, business_type, payload, context)
    db.commit()
    return ok(result, "审批流程已保存")


@router.post("/tasks/{task_id}/approve")
def approve(task_id: str, comment: str = "", context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    instance = approve_task(db, task_id, context, comment)
    db.commit()
    return ok({"instance_id": instance.id, "status": instance.status})


@router.post("/tasks/{task_id}/reject")
def reject(task_id: str, comment: str = "", context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    instance = reject_task(db, task_id, context, comment)
    db.commit()
    return ok({"instance_id": instance.id, "status": instance.status})
