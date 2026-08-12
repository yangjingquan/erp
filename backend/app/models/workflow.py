from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import local_now
from app.models.base import UUIDModel


class WfDefinition(UUIDModel):
    __tablename__ = "wf_definition"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    business_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    nodes: Mapped[list["WfNode"]] = relationship(
        back_populates="definition", cascade="all, delete-orphan", order_by="WfNode.sort_order"
    )


class WfNode(UUIDModel):
    __tablename__ = "wf_node"

    definition_id: Mapped[str] = mapped_column(ForeignKey("wf_definition.id"), nullable=False, index=True)
    node_key: Mapped[str] = mapped_column(String(64), nullable=False)
    node_name: Mapped[str] = mapped_column(String(128), nullable=False)
    node_type: Mapped[str] = mapped_column(String(32), default="approval", nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    approver_type: Mapped[str] = mapped_column(String(32), default="role", nullable=False)
    approver_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    condition_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    definition: Mapped[WfDefinition] = relationship(back_populates="nodes")


class WfInstance(UUIDModel):
    __tablename__ = "wf_instance"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    business_type: Mapped[str] = mapped_column(String(64), nullable=False)
    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    definition_id: Mapped[str] = mapped_column(String(36), nullable=False)
    current_node_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    started_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=local_now,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    tasks: Mapped[list["WfTask"]] = relationship(
        back_populates="instance", cascade="all, delete-orphan", order_by="WfTask.created_at"
    )


class WfTask(UUIDModel):
    __tablename__ = "wf_task"

    instance_id: Mapped[str] = mapped_column(ForeignKey("wf_instance.id"), nullable=False, index=True)
    node_key: Mapped[str] = mapped_column(String(64), nullable=False)
    assignee_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    assignee_role_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=local_now,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    instance: Mapped[WfInstance] = relationship(back_populates="tasks")


class WfActionLog(UUIDModel):
    __tablename__ = "wf_action_log"

    instance_id: Mapped[str] = mapped_column(String(36), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=local_now,
        nullable=False,
    )
