from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.admin import DepartmentCreate, MenuCreate, RoleCreate, StatusUpdate, UserCreate
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
)
from app.services.auth_service import UserContext

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


@router.get("/menus")
def menus(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_menus(db, context))


@router.post("/menus")
def add_menu(payload: MenuCreate, context: UserContext = Depends(require_permission("system:menu:manage")), db: Session = Depends(get_db)):
    return ok({"id": create_menu(db, payload, context).id})


@router.post("/{resource}/{row_id}/status")
def update_status(resource: str, row_id: str, payload: StatusUpdate, context: UserContext = Depends(require_permission("system:user:manage")), db: Session = Depends(get_db)):
    row = set_status(db, resource, row_id, payload.status, context)
    return ok({"id": row.id, "status": row.status})
