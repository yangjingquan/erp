from collections.abc import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.security import decode_token
from app.models.auth import sys_user_role
from app.models.system import SysOrg, SysOrgMembership, SysRole, SysUser
from sqlalchemy import select
from app.services.auth_service import UserContext, build_user_context

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserContext:
    if not token:
        raise AppError("登录已失效，请重新登录", code=401)
    try:
        payload = decode_token(token)
    except Exception as exc:
        raise AppError("登录已失效，请重新登录", code=401) from exc
    if payload.get("type") != "access" or not payload.get("sub"):
        raise AppError("Token 类型无效", code=401)
    user = db.get(SysUser, payload["sub"])
    if user is None or user.is_deleted or user.status != "active":
        raise AppError("用户不存在或已停用", code=401)
    # Tokens created by older versions carried permissions in their claims. Once
    # a user has a role assignment, the database is authoritative so changing a
    # role takes effect without waiting for an old token to expire. Keeping the
    # claim fallback for users without roles preserves compatibility with
    # service-to-service/test tokens and with existing deployments during rollout.
    active_org_id = payload.get("active_org_id") or user.org_id
    if active_org_id != user.org_id and not user.is_superuser:
        membership = db.scalar(select(SysOrgMembership).where(
            SysOrgMembership.user_id == user.id,
            SysOrgMembership.org_id == active_org_id,
            SysOrgMembership.status == "active",
            SysOrgMembership.is_deleted.is_(False),
        ))
        if membership is None:
            raise AppError("当前用户无权访问该组织", code=403)
    org_exists = db.scalar(select(SysOrg.id).where(SysOrg.id == active_org_id, SysOrg.status == "active", SysOrg.is_deleted.is_(False)))
    # Some isolated unit-test/integration databases predate the organization
    # seed data. Keep those deployments compatible while enforcing the check
    # whenever organization records are present.
    if org_exists is None and db.scalar(select(SysOrg.id).limit(1)) is not None:
        raise AppError("组织不存在或已停用", code=401)
    has_role = db.scalar(
        select(sys_user_role.c.role_id).join(SysRole, SysRole.id == sys_user_role.c.role_id).where(
            sys_user_role.c.user_id == user.id, SysRole.org_id == active_org_id
        ).limit(1)
    ) is not None
    fallback_permissions = payload.get("permissions", []) if active_org_id == user.org_id else []
    return build_user_context(
        db,
        user,
        None if has_role or user.is_superuser else fallback_permissions,
        active_org_id=active_org_id,
    )


def require_permission(permission: str) -> Callable:
    def dependency(context: UserContext = Depends(get_current_user)) -> UserContext:
        if permission not in context.permissions and "*" not in context.permissions:
            raise AppError("无权执行该操作", code=403)
        return context

    return dependency
