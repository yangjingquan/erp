from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    parent_id: str | None = None
    manager_id: str | None = None


class RoleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    data_scope_type: str = "department"


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=128)
    department_id: str | None = None
    email: str | None = None
    phone: str | None = None
    role_ids: list[str] = []


class UserUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=128)
    department_id: str | None = None
    email: str | None = None
    phone: str | None = None
    status: str = Field(default="active", pattern="^(active|inactive)$")


class UserPasswordUpdate(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class MenuCreate(BaseModel):
    code: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    parent_id: str | None = None
    path: str | None = None
    component: str | None = None
    menu_type: str = "menu"
    sort_order: int = 0


class StatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|inactive)$")


class RoleAccessUpdate(BaseModel):
    menu_ids: list[str] = []
    permission_ids: list[str] = []
    data_scope_type: str | None = None


class UserRolesUpdate(BaseModel):
    role_ids: list[str] = []
