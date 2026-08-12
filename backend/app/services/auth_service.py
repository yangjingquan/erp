from dataclasses import dataclass

from sqlalchemy import Select, and_, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import verify_password
from app.models.auth import sys_role_menu, sys_role_permission, sys_user_role
from app.models.system import SysMenu, SysPermission, SysRole, SysUser


@dataclass
class UserContext:
    user: SysUser
    permissions: set[str]
    warehouse_ids: set[str] = None
    menus: list[dict] = None
    data_scope_type: str = "department"

    def __post_init__(self) -> None:
        if self.warehouse_ids is None:
            self.warehouse_ids = set()
        if self.menus is None:
            self.menus = []

    @property
    def id(self) -> str:
        return self.user.id

    @property
    def org_id(self) -> str:
        return self.user.org_id

    @property
    def department_id(self) -> str | None:
        return self.user.department_id


def authenticate_user(db: Session, username: str, password: str) -> SysUser:
    user = db.scalar(
        select(SysUser).where(
            SysUser.username == username,
            SysUser.is_deleted.is_(False),
        )
    )
    if user is None or user.status != "active" or not verify_password(
        password, user.password_hash
    ):
        raise AppError("用户名或密码错误", code=401)
    return user


def load_permissions(db: Session, user: SysUser) -> set[str]:
    if user.is_superuser:
        return {"*"}
    statement = (
        select(SysPermission.code)
        .join(
            sys_role_permission,
            sys_role_permission.c.permission_id == SysPermission.id,
        )
        .join(sys_user_role, sys_user_role.c.role_id == sys_role_permission.c.role_id)
        .where(sys_user_role.c.user_id == user.id)
    )
    return set(db.scalars(statement).all())


def load_data_scope_type(db: Session, user: SysUser) -> str:
    if user.is_superuser:
        return "all"
    values = db.scalars(
        select(SysRole.data_scope_type)
        .join(sys_user_role, sys_user_role.c.role_id == SysRole.id)
        .where(sys_user_role.c.user_id == user.id, SysRole.status == "active")
    ).all()
    if "all" in values:
        return "all"
    if "department" in values:
        return "department"
    if "own" in values:
        return "own"
    return "department"


def load_menus(db: Session, user: SysUser) -> list[dict]:
    statement = select(SysMenu).where(SysMenu.status == "active").order_by(SysMenu.sort_order, SysMenu.code)
    if not user.is_superuser:
        statement = statement.join(
            sys_role_menu,
            sys_role_menu.c.menu_id == SysMenu.id,
        ).join(
            sys_user_role,
            sys_user_role.c.role_id == sys_role_menu.c.role_id,
        ).where(sys_user_role.c.user_id == user.id).distinct()
    rows = db.scalars(statement).all()
    nodes = {
        row.id: {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "path": row.path,
            "parent_id": row.parent_id,
            "children": [],
        }
        for row in rows
    }
    roots: list[dict] = []
    for node in nodes.values():
        parent = nodes.get(node["parent_id"])
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)
    return roots


def build_user_context(db: Session, user: SysUser, permissions=None) -> UserContext:
    from app.models.inventory_advanced import InvWarehouseAccess

    warehouse_ids = set(
        db.scalars(
            select(InvWarehouseAccess.warehouse_id).where(
                InvWarehouseAccess.org_id == user.org_id,
                InvWarehouseAccess.user_id == user.id,
                InvWarehouseAccess.is_deleted.is_(False),
            )
        ).all()
    )
    return UserContext(
        user=user,
        permissions=set(permissions) if permissions is not None else load_permissions(db, user),
        warehouse_ids=warehouse_ids,
        menus=load_menus(db, user),
        data_scope_type=load_data_scope_type(db, user),
    )


def data_scope_condition(model, user: object, scope_type: str = "department"):
    if getattr(user, "is_superuser", False) or scope_type == "all":
        return True
    conditions = [model.org_id == getattr(user, "org_id")]
    if scope_type == "own" and hasattr(model, "owner_id"):
        conditions.append(model.owner_id == getattr(user, "id"))
    elif scope_type == "department" and hasattr(model, "department_id"):
        conditions.append(model.department_id == getattr(user, "department_id"))
    return and_(*conditions)


def apply_data_scope(statement: Select, model, context: UserContext, scope_type=None):
    condition = data_scope_condition(model, context.user, scope_type or context.data_scope_type)
    return statement if condition is True else statement.where(condition)
