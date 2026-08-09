from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.services.auth_service import UserContext
from app.services.backup_service import build_backup_command, run_backup, run_restore, validate_restore_request

router = APIRouter(prefix="/api/system", tags=["backup"])


@router.post("/backup/command")
def backup_command(context: UserContext = Depends(require_permission("system:manage")), db: Session = Depends(get_db)):
    target = Path("var/backups") / f"erp-{context.id}.sql"
    return ok({"command": build_backup_command(target)})


@router.post("/backup")
def backup(context: UserContext = Depends(require_permission("system:manage"))):
    target = Path("var/backups") / f"erp-{context.id}.sql"
    return ok({"path": str(run_backup(target))}, "数据库备份完成")


@router.post("/restore/validate")
def restore_validate(path: str, confirmation_token: str, context: UserContext = Depends(require_permission("system:manage"))):
    validate_restore_request(Path(path), confirmation_token)
    return ok({"valid": True})


@router.post("/restore")
def restore(path: str, confirmation_token: str, context: UserContext = Depends(require_permission("system:manage"))):
    run_restore(Path(path), confirmation_token)
    return ok({"restored": True}, "数据库恢复完成")
