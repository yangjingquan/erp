from collections.abc import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.security import decode_token
from app.models.system import SysUser
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
    return build_user_context(db, user, payload.get("permissions", []))


def require_permission(permission: str) -> Callable:
    def dependency(context: UserContext = Depends(get_current_user)) -> UserContext:
        if permission not in context.permissions and "*" not in context.permissions:
            raise AppError("无权执行该操作", code=403)
        return context

    return dependency
