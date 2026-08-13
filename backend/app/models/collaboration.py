from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, BigInteger, Date, DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, UUIDModel


class BizDocument(AuditMixin, UUIDModel):
    __tablename__ = "biz_document"
    __table_args__ = (
        UniqueConstraint("org_id", "business_type", "business_id", name="uk_biz_document_object"),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    business_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    business_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    party_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    party_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    party_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class BizDocumentRelation(AuditMixin, UUIDModel):
    __tablename__ = "biz_document_relation"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "from_type", "from_id", "to_type", "to_id", "relation_type",
            name="uk_biz_document_relation",
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    from_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    from_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    to_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    to_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)


class BizAttachment(AuditMixin, UUIDModel):
    __tablename__ = "biz_attachment"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    file_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), default="internal", nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(36), nullable=False)


class BizComment(AuditMixin, UUIDModel):
    __tablename__ = "biz_comment"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    author_name: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class BizSavedView(AuditMixin, UUIDModel):
    __tablename__ = "biz_saved_view"
    __table_args__ = (
        UniqueConstraint("org_id", "owner_id", "name", name="uk_biz_saved_view_owner_name"),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    business_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_shared: Mapped[bool] = mapped_column(default=False, nullable=False)


class BizExportJob(AuditMixin, UUIDModel):
    __tablename__ = "biz_export_job"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    business_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    file_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    row_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class BizReportDefinition(AuditMixin, UUIDModel):
    __tablename__ = "biz_report_definition"
    __table_args__ = (
        UniqueConstraint("org_id", "report_key", name="uk_biz_report_definition_org_key"),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    report_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    parameters_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)


class BizReportRun(AuditMixin, UUIDModel):
    __tablename__ = "biz_report_run"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    report_definition_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    report_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    parameters_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False, index=True)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)


class SysNotification(AuditMixin, UUIDModel):
    __tablename__ = "sys_notification"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    recipient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    notification_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(String(500), nullable=False)
    object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class SysIdempotencyRecord(UUIDModel):
    __tablename__ = "sys_idempotency_record"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "idempotency_key", "method", "path",
            name="uk_sys_idempotency_request",
        ),
    )

    org_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(nullable=False)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)
