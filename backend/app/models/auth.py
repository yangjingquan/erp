from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import local_now
from app.models.base import UUIDModel


class AuthCaptchaChallenge(UUIDModel):
    __tablename__ = "auth_captcha_challenge"

    target_x: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)
    verified_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=local_now, nullable=False)


sys_user_role = Table(
    "sys_user_role",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("sys_user.id"), primary_key=True),
    Column("role_id", String(36), ForeignKey("sys_role.id"), primary_key=True),
)

sys_role_menu = Table(
    "sys_role_menu",
    Base.metadata,
    Column("role_id", String(36), ForeignKey("sys_role.id"), primary_key=True),
    Column("menu_id", String(36), ForeignKey("sys_menu.id"), primary_key=True),
)

sys_role_permission = Table(
    "sys_role_permission",
    Base.metadata,
    Column("role_id", String(36), ForeignKey("sys_role.id"), primary_key=True),
    Column(
        "permission_id",
        String(36),
        ForeignKey("sys_permission.id"),
        primary_key=True,
    ),
)
