from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.admin import DepartmentCreate, MenuCreate, RoleAccessUpdate, RoleCreate, StatusUpdate, UserCreate, UserPasswordUpdate, UserRolesUpdate, UserUpdate
from app.services.admin_service import (
    create_department,
    create_menu,
    create_role,
    create_user,
    list_departments,
    list_menus,
    list_roles,
    list_users,
    set_status,
    update_user,
    update_user_password,
    set_user_roles,
)
from app.services.auth_service import UserContext
from app.services.permission_service import get_permission_catalog, get_role_access, save_role_access

router = APIRouter(prefix="/api/admin", tags=["administration"])


@router.get("/departments")
def departments(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_departments(db, context))


@router.post("/departments")
def add_department(payload: DepartmentCreate, context: UserContext = Depends(require_permission("system:department:manage")), db: Session = Depends(get_db)):
    return ok({"id": create_department(db, payload, context).id})


@router.get("/roles")
def roles(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_roles(db, context))


@router.post("/roles")
def add_role(payload: RoleCreate, context: UserContext = Depends(require_permission("system:role:manage")), db: Session = Depends(get_db)):
    return ok({"id": create_role(db, payload, context).id})


@router.get("/users")
def users(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_users(db, context))


@router.post("/users")
def add_user(payload: UserCreate, context: UserContext = Depends(require_permission("system:user:manage")), db: Session = Depends(get_db)):
    return ok({"id": create_user(db, payload, context).id})


@router.put("/users/{user_id}")
def edit_user(user_id: str, payload: UserUpdate, context: UserContext = Depends(require_permission("system:user:manage")), db: Session = Depends(get_db)):
    return ok(update_user(db, user_id, payload, context))


@router.put("/users/{user_id}/password")
def edit_user_password(user_id: str, payload: UserPasswordUpdate, context: UserContext = Depends(require_permission("system:user:manage")), db: Session = Depends(get_db)):
    update_user_password(db, user_id, payload.password, context)
    return ok(msg="用户密码已更新")


@router.put("/users/{user_id}/roles")
def update_user_roles(user_id: str, payload: UserRolesUpdate, context: UserContext = Depends(require_permission("system:user:manage")), db: Session = Depends(get_db)):
    return ok(set_user_roles(db, user_id, payload.role_ids, context))


@router.get("/menus")
def menus(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_menus(db, context))


@router.post("/menus")
def add_menu(payload: MenuCreate, context: UserContext = Depends(require_permission("system:menu:manage")), db: Session = Depends(get_db)):
    return ok({"id": create_menu(db, payload, context).id})


@router.get("/permissions/catalog")
def permission_catalog(context: UserContext = Depends(require_permission("system:role:manage")), db: Session = Depends(get_db)):
    return ok(get_permission_catalog(db))


@router.get("/roles/{role_id}/access")
def role_access(role_id: str, context: UserContext = Depends(require_permission("system:role:manage")), db: Session = Depends(get_db)):
    return ok(get_role_access(db, role_id, context))


@router.put("/roles/{role_id}/access")
def update_role_access(role_id: str, payload: RoleAccessUpdate, context: UserContext = Depends(require_permission("system:role:manage")), db: Session = Depends(get_db)):
    return ok(save_role_access(db, role_id, payload.menu_ids, payload.permission_ids, context, payload.data_scope_type))


@router.post("/{resource}/{row_id}/status")
def update_status(resource: str, row_id: str, payload: StatusUpdate, context: UserContext = Depends(require_permission("system:user:manage")), db: Session = Depends(get_db)):
    row = set_status(db, resource, row_id, payload.status, context)
    return ok({"id": row.id, "status": row.status})
