from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    permissions: list[str] | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if permissions is not None:
        payload["permissions"] = permissions
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, permissions: list[str] | None = None) -> str:
    settings = get_settings()
    return _create_token(
        subject,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
        permissions,
    )


def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    return _create_token(
        subject,
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
