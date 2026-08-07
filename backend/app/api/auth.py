from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.response import ok
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.services.audit_service import write_login_log, write_operation_log
from app.schemas.auth import ChangePasswordRequest, LoginRequest
from app.services.auth_service import UserContext, authenticate_user, build_user_context

router = APIRouter(prefix="/api/auth", tags=["auth"])


def serialize_user(context: UserContext) -> dict:
    user = context.user
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "org_id": user.org_id,
        "department_id": user.department_id,
        "is_superuser": user.is_superuser,
    }


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    try:
        user = authenticate_user(db, payload.username, payload.password)
    except AppError as exc:
        write_login_log(db, username=payload.username, success=False, message=exc.msg)
        db.commit()
        raise
    context = build_user_context(db, user)
    write_login_log(db, username=user.username, success=True, user_id=user.id)
    db.commit()
    return ok(
        {
            "access_token": create_access_token(user.id, sorted(context.permissions)),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer",
            "user": serialize_user(context),
        }
    )


@router.get("/me")
def me(context: UserContext = Depends(get_current_user)) -> dict:
    return ok(serialize_user(context))


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not verify_password(payload.old_password, context.user.password_hash):
        raise AppError("旧密码错误", code=400)
    context.user.password_hash = hash_password(payload.new_password)
    write_operation_log(
        db,
        user=context.user,
        action="change_password",
        resource="sys_user",
        target_id=context.user.id,
    )
    db.commit()
    return ok(msg="密码修改成功")


@router.get("/permission-check")
def permission_check(
    _: UserContext = Depends(require_permission("system:user:manage")),
) -> dict:
    return ok({"allowed": True})
