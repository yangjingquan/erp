from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def new_uuid() -> str:
    return str(uuid4())


class UUIDModel(Base):
    __abstract__ = True

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)


class AuditMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
