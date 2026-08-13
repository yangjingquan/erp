from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, UUIDModel


class SysOrg(AuditMixin, UUIDModel):
    __tablename__ = "sys_org"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class SysOrgMembership(AuditMixin, UUIDModel):
    """用户可访问的组织，用于集团多组织上下文切换。"""

    __tablename__ = "sys_org_membership"
    __table_args__ = (UniqueConstraint("user_id", "org_id", name="uk_sys_org_membership_user_org"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("sys_user.id"), nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("sys_org.id"), nullable=False, index=True)
    membership_type: Mapped[str] = mapped_column(String(32), default="member", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class SysDepartment(AuditMixin, UUIDModel):
    __tablename__ = "sys_department"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    manager_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class SysUser(AuditMixin, UUIDModel):
    __tablename__ = "sys_user"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SysRole(AuditMixin, UUIDModel):
    __tablename__ = "sys_role"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    data_scope_type: Mapped[str] = mapped_column(
        String(32), default="department", nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class SysMenu(UUIDModel):
    __tablename__ = "sys_menu"

    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    component: Mapped[str | None] = mapped_column(String(255), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(128), nullable=True)
    menu_type: Mapped[str] = mapped_column(String(32), default="menu", nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class SysPermission(UUIDModel):
    __tablename__ = "sys_permission"

    menu_id: Mapped[str] = mapped_column(ForeignKey("sys_menu.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    permission_type: Mapped[str] = mapped_column(
        String(32), default="button", nullable=False
    )


class SysUserDataScope(UUIDModel):
    __tablename__ = "sys_user_data_scope"

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_value: Mapped[str | None] = mapped_column(Text, nullable=True)
