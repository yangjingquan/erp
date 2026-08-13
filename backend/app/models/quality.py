from datetime import date, datetime

from sqlalchemy import Date, DateTime, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import local_now
from app.models.base import AuditMixin, UUIDModel


class QaPlan(AuditMixin, UUIDModel):
    __tablename__ = "qa_plan"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    items_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class QaInspection(AuditMixin, UUIDModel):
    __tablename__ = "qa_inspection"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    inspection_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    result: Mapped[str | None] = mapped_column(String(32))
    results_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    disposition: Mapped[str | None] = mapped_column(String(32))


class QaNonconformity(AuditMixin, UUIDModel):
    # Keep the established MySQL table name.  The previous singular
    # ``qa_nonconformity`` mapping only worked in SQLite tests and failed on
    # databases initialized from database/init.sql.
    __tablename__ = "qa_nonconformance"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    inspection_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="major", nullable=False)
    disposition: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    closure_evidence: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "inspection_id", name="uk_qa_nonconformance_inspection"),
    )


class QaCapaAction(AuditMixin, UUIDModel):
    __tablename__ = "qa_capa_action"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    nonconformance_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    completion_evidence: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    def complete(self, *, evidence: str, user_id: str) -> None:
        self.status = "completed"
        self.completion_evidence = evidence
        self.completed_at = local_now()
        self.completed_by = user_id
