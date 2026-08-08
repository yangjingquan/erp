from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import hash_password
from app.models.auth import sys_user_role
from app.models.system import SysDepartment, SysMenu, SysRole, SysUser
from app.services.audit_service import write_operation_log
from app.services.auth_service import UserContext


def _serialize(row, fields):
    return {field: getattr(row, field, None) for field in fields} | {"id": row.id}


def list_departments(db: Session, context: UserContext):
    rows = db.scalars(select(SysDepartment).where(SysDepartment.org_id == context.org_id).order_by(SysDepartment.code)).all()
    return [_serialize(row, ["code", "name", "parent_id", "manager_id", "status"]) for row in rows]


def list_roles(db: Session, context: UserContext):
    rows = db.scalars(select(SysRole).where(SysRole.org_id == context.org_id, SysRole.is_deleted.is_(False)).order_by(SysRole.code)).all()
    return [_serialize(row, ["code", "name", "data_scope_type", "status"]) for row in rows]


def list_users(db: Session, context: UserContext):
    rows = db.scalars(select(SysUser).where(SysUser.org_id == context.org_id, SysUser.is_deleted.is_(False)).order_by(SysUser.username)).all()
    result = []
    for row in rows:
        role_ids = list(db.scalars(select(sys_user_role.c.role_id).where(sys_user_role.c.user_id == row.id)).all())
        result.append(_serialize(row, ["username", "display_name", "department_id", "email", "phone", "status", "is_superuser"]) | {"role_ids": role_ids})
    return result


def list_menus(db: Session, context: UserContext):
    rows = db.scalars(select(SysMenu).order_by(SysMenu.sort_order, SysMenu.code)).all()
    return [_serialize(row, ["code", "name", "parent_id", "path", "component", "menu_type", "sort_order", "status"]) for row in rows]


def _ensure_unique(db: Session, model, context: UserContext, code: str, name: str):
    existing = db.scalar(select(model).where(model.org_id == context.org_id, model.code == code, model.is_deleted.is_(False)))
    if existing:
        raise AppError("编码已存在", code=409)
    existing = db.scalar(select(model).where(model.org_id == context.org_id, model.name == name, model.is_deleted.is_(False)))
    if existing:
        raise AppError("名称已存在", code=409)


def create_department(db: Session, payload, context: UserContext):
    _ensure_unique(db, SysDepartment, context, payload.code, payload.name)
    row = SysDepartment(org_id=context.org_id, **payload.model_dump())
    db.add(row)
    write_operation_log(db, user=context.user, action="create", resource="sys_department", target_id=row.id)
    db.commit()
    db.refresh(row)
    return row


def create_role(db: Session, payload, context: UserContext):
    _ensure_unique(db, SysRole, context, payload.code, payload.name)
    row = SysRole(org_id=context.org_id, **payload.model_dump())
    db.add(row)
    write_operation_log(db, user=context.user, action="create", resource="sys_role", target_id=row.id)
    db.commit()
    db.refresh(row)
    return row


def create_user(db: Session, payload, context: UserContext):
    if db.scalar(select(SysUser).where(SysUser.username == payload.username, SysUser.is_deleted.is_(False))):
        raise AppError("用户名已存在", code=409)
    role_ids = payload.role_ids
    row = SysUser(org_id=context.org_id, password_hash=hash_password(payload.password), **payload.model_dump(exclude={"password", "role_ids"}))
    db.add(row)
    db.flush()
    for role_id in role_ids:
        role = db.scalar(select(SysRole).where(SysRole.id == role_id, SysRole.org_id == context.org_id, SysRole.is_deleted.is_(False)))
        if role is None:
            raise AppError("角色不存在", code=404)
        db.execute(sys_user_role.insert().values(user_id=row.id, role_id=role.id))
    write_operation_log(db, user=context.user, action="create", resource="sys_user", target_id=row.id)
    db.commit()
    db.refresh(row)
    return row


def _get_user(db: Session, user_id: str, context: UserContext):
    row = db.scalar(select(SysUser).where(SysUser.id == user_id, SysUser.org_id == context.org_id, SysUser.is_deleted.is_(False)))
    if row is None:
        raise AppError("用户不存在", code=404)
    return row


def update_user(db: Session, user_id: str, payload, context: UserContext):
    row = _get_user(db, user_id, context)
    if row.id == context.id and payload.status == "inactive":
        raise AppError("不能停用当前登录用户", code=400)
    for field, value in payload.model_dump().items():
        setattr(row, field, value)
    write_operation_log(db, user=context.user, action="update", resource="sys_user", target_id=row.id)
    db.commit()
    return _serialize_user(row, db)


def _serialize_user(row, db: Session):
    role_ids = list(db.scalars(select(sys_user_role.c.role_id).where(sys_user_role.c.user_id == row.id)).all())
    return _serialize(row, ["username", "display_name", "department_id", "email", "phone", "status", "is_superuser"]) | {"role_ids": role_ids}


def update_user_password(db: Session, user_id: str, password: str, context: UserContext):
    row = _get_user(db, user_id, context)
    row.password_hash = hash_password(password)
    write_operation_log(db, user=context.user, action="change_password", resource="sys_user", target_id=row.id)
    db.commit()


def create_menu(db: Session, payload, context: UserContext):
    if db.scalar(select(SysMenu).where(SysMenu.code == payload.code)):
        raise AppError("菜单编码已存在", code=409)
    row = SysMenu(**payload.model_dump())
    db.add(row)
    write_operation_log(db, user=context.user, action="create", resource="sys_menu", target_id=row.id)
    db.commit()
    db.refresh(row)
    return row


def set_status(db: Session, resource: str, row_id: str, status: str, context: UserContext):
    model = {"departments": SysDepartment, "roles": SysRole, "users": SysUser, "menus": SysMenu}.get(resource)
    if model is None:
        raise AppError("不支持的管理资源", code=404)
    row = db.get(model, row_id)
    if row is None or (hasattr(row, "org_id") and row.org_id != context.org_id):
        raise AppError("数据不存在", code=404)
    row.status = status
    write_operation_log(db, user=context.user, action="status", resource=f"sys_{resource[:-1]}", target_id=row.id, detail={"status": status})
    db.commit()
    return row


def set_user_roles(db: Session, user_id: str, role_ids: list[str], context: UserContext):
    user = db.scalar(select(SysUser).where(SysUser.id == user_id, SysUser.org_id == context.org_id, SysUser.is_deleted.is_(False)))
    if user is None:
        raise AppError("用户不存在", code=404)
    roles = db.scalars(select(SysRole).where(SysRole.id.in_(role_ids), SysRole.org_id == context.org_id, SysRole.is_deleted.is_(False))).all() if role_ids else []
    if len(roles) != len(set(role_ids)):
        raise AppError("角色不存在", code=404)
    db.execute(sys_user_role.delete().where(sys_user_role.c.user_id == user_id))
    for role in roles:
        db.execute(sys_user_role.insert().values(user_id=user_id, role_id=role.id))
    write_operation_log(db, user=context.user, action="update_roles", resource="sys_user", target_id=user_id, detail={"role_ids": role_ids})
    db.commit()
    return {"user_id": user_id, "role_ids": role_ids}
