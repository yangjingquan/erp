"""P1/P2 extension domain models.

The extension domains deliberately keep relationships by business id instead of
hard SQL foreign keys.  This mirrors the existing ERP document model and lets
the modules be installed incrementally while retaining cross-domain traceability.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, UUIDModel


class PlmProductRevision(AuditMixin, UUIDModel):
    __tablename__ = "plm_product_revision"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    material_id: Mapped[str] = mapped_column(String(36), index=True)
    revision: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    change_summary: Mapped[str | None] = mapped_column(String(1000))
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("org_id", "material_id", "revision", name="uk_plm_revision"),)


class PlmChangeRequest(AuditMixin, UUIDModel):
    __tablename__ = "plm_change_request"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    change_no: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    change_type: Mapped[str] = mapped_column(String(32), default="engineering")
    description: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    owner_id: Mapped[str | None] = mapped_column(String(36))
    due_date: Mapped[date | None] = mapped_column(Date)
    impact_snapshot: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (UniqueConstraint("org_id", "change_no", name="uk_plm_change_request_no"),)


class PlmChangeOrder(AuditMixin, UUIDModel):
    __tablename__ = "plm_change_order"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    ecn_no: Mapped[str] = mapped_column(String(64))
    request_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(36))
    effective_at: Mapped[datetime | None] = mapped_column(DateTime)
    __table_args__ = (UniqueConstraint("org_id", "ecn_no", name="uk_plm_change_order_no"),)


class PlmChangeImpact(AuditMixin, UUIDModel):
    __tablename__ = "plm_change_impact"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    change_order_id: Mapped[str] = mapped_column(String(36), index=True)
    object_type: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[str] = mapped_column(String(36))
    impact: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(32), default="pending")


class SrmRfq(AuditMixin, UUIDModel):
    __tablename__ = "srm_rfq"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    rfq_no: Mapped[str] = mapped_column(String(64))
    supplier_id: Mapped[str] = mapped_column(String(36), index=True)
    material_id: Mapped[str] = mapped_column(String(36))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0)
    due_date: Mapped[date | None] = mapped_column(Date)
    quote_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    promised_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    supplier_note: Mapped[str | None] = mapped_column(String(1000))
    __table_args__ = (UniqueConstraint("org_id", "rfq_no", name="uk_srm_rfq_no"),)


class SrmSupplierScore(AuditMixin, UUIDModel):
    __tablename__ = "srm_supplier_score"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    supplier_id: Mapped[str] = mapped_column(String(36), index=True)
    period: Mapped[str] = mapped_column(String(7))
    delivery_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    quality_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    service_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    total_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("org_id", "supplier_id", "period", name="uk_srm_supplier_score"),)


class Project(AuditMixin, UUIDModel):
    __tablename__ = "project"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    project_code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    customer_id: Mapped[str | None] = mapped_column(String(36))
    manager_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    __table_args__ = (UniqueConstraint("org_id", "project_code", name="uk_project_code"),)


class ProjectWbs(AuditMixin, UUIDModel):
    __tablename__ = "project_wbs"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(36))
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="open")
    planned_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)


class ProjectMilestone(AuditMixin, UUIDModel):
    __tablename__ = "project_milestone"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    wbs_id: Mapped[str | None] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(255))
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="pending")


class ProjectEntry(AuditMixin, UUIDModel):
    __tablename__ = "project_entry"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    wbs_id: Mapped[str | None] = mapped_column(String(36))
    entry_date: Mapped[date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(32))
    source_type: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(36))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)


class EamAsset(AuditMixin, UUIDModel):
    __tablename__ = "eam_asset"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    asset_code: Mapped[str] = mapped_column(String(64))
    asset_name: Mapped[str] = mapped_column(String(255))
    serial_no: Mapped[str | None] = mapped_column(String(128))
    location: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active")
    next_maintenance_date: Mapped[date | None] = mapped_column(Date)
    __table_args__ = (UniqueConstraint("org_id", "asset_code", name="uk_eam_asset_code"),)


class EamMaintenancePlan(AuditMixin, UUIDModel):
    __tablename__ = "eam_maintenance_plan"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    asset_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(255))
    interval_days: Mapped[int] = mapped_column(default=30)
    next_due: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="active")


class EamWorkOrder(AuditMixin, UUIDModel):
    __tablename__ = "eam_work_order"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    work_order_no: Mapped[str] = mapped_column(String(64))
    asset_id: Mapped[str] = mapped_column(String(36), index=True)
    service_type: Mapped[str] = mapped_column(String(32), default="repair")
    description: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(32), default="open")
    owner_id: Mapped[str | None] = mapped_column(String(36))
    due_date: Mapped[date | None] = mapped_column(Date)
    resolution: Mapped[str | None] = mapped_column(String(1000))
    __table_args__ = (UniqueConstraint("org_id", "work_order_no", name="uk_eam_work_order_no"),)


class SvcContract(AuditMixin, UUIDModel):
    __tablename__ = "svc_contract"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    contract_no: Mapped[str] = mapped_column(String(64))
    customer_id: Mapped[str] = mapped_column(String(36), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    __table_args__ = (UniqueConstraint("org_id", "contract_no", name="uk_svc_contract_no"),)


class SvcCase(AuditMixin, UUIDModel):
    __tablename__ = "svc_case"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    case_no: Mapped[str] = mapped_column(String(64))
    customer_id: Mapped[str] = mapped_column(String(36), index=True)
    contract_id: Mapped[str | None] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(255))
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    status: Mapped[str] = mapped_column(String(32), default="open")
    owner_id: Mapped[str | None] = mapped_column(String(36))
    due_date: Mapped[date | None] = mapped_column(Date)
    resolution: Mapped[str | None] = mapped_column(String(1000))
    __table_args__ = (UniqueConstraint("org_id", "case_no", name="uk_svc_case_no"),)


class SvcVisit(AuditMixin, UUIDModel):
    __tablename__ = "svc_visit"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    technician_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(32), default="scheduled")
    notes: Mapped[str | None] = mapped_column(String(1000))


class TaxCode(AuditMixin, UUIDModel):
    __tablename__ = "tax_code"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0)
    status: Mapped[str] = mapped_column(String(32), default="active")
    __table_args__ = (UniqueConstraint("org_id", "code", name="uk_tax_code"),)


class TaxInvoice(AuditMixin, UUIDModel):
    __tablename__ = "tax_invoice"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    invoice_no: Mapped[str] = mapped_column(String(64))
    invoice_type: Mapped[str] = mapped_column(String(32), default="output")
    source_type: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(36))
    party_id: Mapped[str] = mapped_column(String(36))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    tax_code: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    __table_args__ = (UniqueConstraint("org_id", "invoice_no", name="uk_tax_invoice_no"),)


class OrgIntercompanyTransaction(AuditMixin, UUIDModel):
    __tablename__ = "org_intercompany_transaction"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    transaction_no: Mapped[str] = mapped_column(String(64))
    from_org_id: Mapped[str] = mapped_column(String(36))
    to_org_id: Mapped[str] = mapped_column(String(36))
    source_type: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(36))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    __table_args__ = (UniqueConstraint("org_id", "transaction_no", name="uk_intercompany_no"),)


class LowCodeDefinition(AuditMixin, UUIDModel):
    __tablename__ = "low_code_definition"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    object_key: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(128))
    schema_json: Mapped[dict] = mapped_column(JSON, default=dict)
    workflow_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    __table_args__ = (UniqueConstraint("org_id", "object_key", name="uk_low_code_object_key"),)


class MetricDefinition(AuditMixin, UUIDModel):
    __tablename__ = "metric_definition"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    metric_key: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(128))
    formula: Mapped[str] = mapped_column(String(1000))
    target: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    owner_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(32), default="active")
    __table_args__ = (UniqueConstraint("org_id", "metric_key", name="uk_metric_definition"),)


class AiExceptionAlert(AuditMixin, UUIDModel):
    __tablename__ = "ai_exception_alert"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    alert_key: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(16), default="warning")
    source_type: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str | None] = mapped_column(String(36))
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    recommended_action: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(32), default="open")
    __table_args__ = (UniqueConstraint("org_id", "alert_key", name="uk_ai_exception_alert"),)


class HrLeaveRequest(AuditMixin, UUIDModel):
    __tablename__ = "hr_leave_request"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    employee_id: Mapped[str] = mapped_column(String(36), index=True)
    leave_type: Mapped[str] = mapped_column(String(64))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(36))
