from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.models.logging import SysLoginLog, SysOperationLog


def write_operation_log(
    db: Session,
    *,
    user: object | None,
    action: str,
    resource: str,
    target_id: str | None = None,
    detail: Mapping[str, Any] | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
) -> SysOperationLog:
    row = SysOperationLog(
        request_id=request_id,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", None),
        org_id=getattr(user, "org_id", None),
        department_id=getattr(user, "department_id", None),
        action=action,
        resource=resource,
        target_id=target_id,
        detail_json=dict(detail or {}),
        ip_address=ip_address,
    )
    db.add(row)
    db.flush()
    return row


def write_login_log(
    db: Session,
    *,
    username: str,
    success: bool,
    user_id: str | None = None,
    message: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> SysLoginLog:
    row = SysLoginLog(
        username=username,
        success=success,
        user_id=user_id,
        message=message,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(row)
    db.flush()
    return row
