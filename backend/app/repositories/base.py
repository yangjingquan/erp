from typing import Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.services.auth_service import UserContext, apply_data_scope

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    def __init__(self, db: Session, model: type[ModelT]) -> None:
        self.db = db
        self.model = model

    def list(
        self,
        *,
        context: UserContext | None = None,
        scope_type: str = "department",
        page: int = 1,
        page_size: int = 20,
    ) -> list[ModelT]:
        statement: Select = select(self.model)
        if hasattr(self.model, "is_deleted"):
            statement = statement.where(self.model.is_deleted.is_(False))
        if context is not None:
            statement = apply_data_scope(statement, self.model, context, scope_type)
        statement = statement.offset(max(page - 1, 0) * page_size).limit(page_size)
        return list(self.db.scalars(statement).all())

    def get(self, item_id: str) -> ModelT | None:
        return self.db.get(self.model, item_id)

    def create(self, instance: ModelT) -> ModelT:
        self.db.add(instance)
        self.db.flush()
        return instance

    def update(self, instance: ModelT, values: dict) -> ModelT:
        for key, value in values.items():
            if not hasattr(instance, key):
                raise AppError(f"不支持更新字段：{key}", code=400)
            setattr(instance, key, value)
        self.db.flush()
        return instance

    def soft_delete(self, instance: ModelT) -> ModelT:
        if not hasattr(instance, "is_deleted"):
            raise AppError("该数据不支持删除", code=400)
        instance.is_deleted = True
        self.db.flush()
        return instance
