from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.response import ok
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.services.audit_service import write_login_log, write_operation_log
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest, SliderCaptchaVerifyRequest
from app.models.system import SysOrg, SysUser
from app.services.auth_service import UserContext, authenticate_user, build_user_context, list_user_organizations
from app.services.captcha_service import consume_captcha_token, create_captcha_challenge, verify_captcha_challenge

router = APIRouter(prefix="/api/auth", tags=["auth"])


def serialize_user(context: UserContext) -> dict:
    user = context.user
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "org_id": context.org_id,
        "active_org_id": context.org_id,
        "department_id": user.department_id,
        "is_superuser": user.is_superuser,
        "permissions": sorted(context.permissions),
        "menus": context.menus,
        "data_scope_type": context.data_scope_type,
    }


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    if not consume_captcha_token(db, payload.captcha_token):
        write_login_log(db, username=payload.username, success=False, message="滑块验证无效或已使用")
        db.commit()
        raise AppError("滑块验证已失效，请重新验证", code=400)
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


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    if not consume_captcha_token(db, payload.captcha_token):
        raise AppError("滑块验证已失效，请重新验证", code=400)
    username = payload.username.strip()
    if len(username) < 3:
        raise AppError("账号至少 3 位", code=400)
    if db.scalar(select(SysUser).where(SysUser.username == username, SysUser.is_deleted.is_(False))):
        raise AppError("账号已存在，请更换账号", code=409)
    org_id = db.scalar(select(SysOrg.id).where(SysOrg.status == "active").order_by(SysOrg.created_at).limit(1))
    if org_id is None:
        org_id = db.scalar(select(SysUser.org_id).order_by(SysUser.created_at).limit(1))
    if org_id is None:
        raise AppError("系统尚未初始化组织，暂时无法注册", code=503)
    user = SysUser(
        org_id=org_id,
        username=username,
        display_name=username,
        password_hash=hash_password(payload.password),
        status="active",
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    return ok({"id": user.id, "username": user.username})


@router.get("/captcha/challenge")
def captcha_challenge(db: Session = Depends(get_db)) -> dict:
    return ok(create_captcha_challenge(db))


@router.post("/captcha/verify")
def captcha_verify(payload: SliderCaptchaVerifyRequest, db: Session = Depends(get_db)) -> dict:
    captcha_token = verify_captcha_challenge(db, payload.challenge_id, payload.offset_x)
    return ok({"captcha_token": captcha_token})


@router.get("/me")
def me(context: UserContext = Depends(get_current_user)) -> dict:
    return ok(serialize_user(context))


@router.get("/organizations")
def organizations(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return ok(list_user_organizations(db, context.user))


@router.post("/switch-organization/{org_id}")
def switch_organization(org_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    available = {item["id"] for item in list_user_organizations(db, context.user)}
    if org_id not in available and not context.user.is_superuser:
        raise AppError("当前用户无权切换到该组织", code=403)
    target = db.scalar(select(SysOrg).where(SysOrg.id == org_id, SysOrg.status == "active", SysOrg.is_deleted.is_(False)))
    if target is None:
        raise AppError("组织不存在或已停用", code=404)
    permissions = sorted(context.permissions)
    token = create_access_token(context.user.id, permissions, active_org_id=org_id)
    target_context = build_user_context(db, context.user, permissions if context.user.is_superuser else None, active_org_id=org_id)
    return ok({"access_token": token, "token_type": "bearer", "user": serialize_user(target_context), "organization": {"id": target.id, "code": target.code, "name": target.name}})


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
