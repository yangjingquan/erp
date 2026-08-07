from sqlalchemy import Column, ForeignKey, String, Table

from app.core.database import Base


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
