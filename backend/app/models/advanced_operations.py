"""Operational extensions for HR, quality, transport and OCR workflows."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, UUIDModel


class HrRecruitmentCandidate(AuditMixin, UUIDModel):
    __tablename__ = "hr_recruitment_candidate"
    __table_args__ = (UniqueConstraint("org_id", "candidate_no", name="uk_hr_candidate_no"),)

    org_id: Mapped[str] = mapped_column(String(36), index=True)
    candidate_no: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(64))
    position: Mapped[str] = mapped_column(String(128))
    source: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="new")
    note: Mapped[str | None] = mapped_column(String(500))


class HrEmployeeLifecycle(AuditMixin, UUIDModel):
    __tablename__ = "hr_employee_lifecycle"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    employee_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    effective_date: Mapped[date] = mapped_column(Date)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str | None] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(String(500))


class HrPerformanceReview(AuditMixin, UUIDModel):
    __tablename__ = "hr_performance_review"
    __table_args__ = (UniqueConstraint("org_id", "employee_id", "period", name="uk_hr_performance_period"),)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    employee_id: Mapped[str] = mapped_column(String(36), index=True)
    period: Mapped[str] = mapped_column(String(16))
    score: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    rating: Mapped[str] = mapped_column(String(32), default="pending")
    goals_json: Mapped[list] = mapped_column(JSON, default=list)
    comments: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(32), default="draft")


class HrBenefitRecord(AuditMixin, UUIDModel):
    __tablename__ = "hr_benefit_record"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    employee_id: Mapped[str] = mapped_column(String(36), index=True)
    benefit_type: Mapped[str] = mapped_column(String(64))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    effective_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="active")
    note: Mapped[str | None] = mapped_column(String(500))


class QaSpcRecord(AuditMixin, UUIDModel):
    __tablename__ = "qa_spc_record"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    inspection_id: Mapped[str | None] = mapped_column(String(36), index=True)
    material_id: Mapped[str] = mapped_column(String(36), index=True)
    metric: Mapped[str] = mapped_column(String(128))
    sample_value: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    lsl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    usl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    cpk: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    status: Mapped[str] = mapped_column(String(32), default="in_control")


class QaSupplierQuality(AuditMixin, UUIDModel):
    __tablename__ = "qa_supplier_quality"
    __table_args__ = (UniqueConstraint("org_id", "supplier_id", "period", name="uk_qa_supplier_quality_period"),)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    supplier_id: Mapped[str] = mapped_column(String(36), index=True)
    period: Mapped[str] = mapped_column(String(7))
    inspection_count: Mapped[int] = mapped_column(default=0)
    defect_count: Mapped[int] = mapped_column(default=0)
    defect_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0)
    score: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    note: Mapped[str | None] = mapped_column(String(500))


class QaQualityCost(AuditMixin, UUIDModel):
    __tablename__ = "qa_quality_cost"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    period: Mapped[str] = mapped_column(String(7), index=True)
    cost_type: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    source_id: Mapped[str | None] = mapped_column(String(36))
    note: Mapped[str | None] = mapped_column(String(500))


class QaCustomerClaim(AuditMixin, UUIDModel):
    __tablename__ = "qa_customer_claim"
    __table_args__ = (UniqueConstraint("org_id", "claim_no", name="uk_qa_customer_claim_no"),)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    claim_no: Mapped[str] = mapped_column(String(64))
    customer_id: Mapped[str] = mapped_column(String(36), index=True)
    source_type: Mapped[str | None] = mapped_column(String(64))
    source_id: Mapped[str | None] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    status: Mapped[str] = mapped_column(String(32), default="open")
    root_cause: Mapped[str | None] = mapped_column(String(1000))
    resolution: Mapped[str | None] = mapped_column(String(1000))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)


class TmsShipment(AuditMixin, UUIDModel):
    __tablename__ = "tms_shipment"
    __table_args__ = (UniqueConstraint("org_id", "shipment_no", name="uk_tms_shipment_no"),)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    shipment_no: Mapped[str] = mapped_column(String(64))
    source_type: Mapped[str | None] = mapped_column(String(64))
    source_id: Mapped[str | None] = mapped_column(String(36))
    carrier_name: Mapped[str] = mapped_column(String(128))
    origin: Mapped[str] = mapped_column(String(255))
    destination: Mapped[str] = mapped_column(String(255))
    planned_date: Mapped[date] = mapped_column(Date)
    actual_date: Mapped[date | None] = mapped_column(Date)
    freight_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    note: Mapped[str | None] = mapped_column(String(500))


class TmsShipmentEvent(AuditMixin, UUIDModel):
    __tablename__ = "tms_shipment_event"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    shipment_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(32))
    event_date: Mapped[datetime] = mapped_column(DateTime)
    note: Mapped[str | None] = mapped_column(String(500))


class OcrDocument(AuditMixin, UUIDModel):
    __tablename__ = "ocr_document"
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    document_type: Mapped[str] = mapped_column(String(64))
    source_file: Mapped[str] = mapped_column(String(255))
    raw_text: Mapped[str | None] = mapped_column(String(10000))
    extracted_json: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    error_message: Mapped[str | None] = mapped_column(String(500))
