from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, UUIDModel


class MfgBom(AuditMixin, UUIDModel):
    __tablename__ = "mfg_bom"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    bom_version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    items: Mapped[list["MfgBomItem"]] = relationship(
        back_populates="bom", cascade="all, delete-orphan", order_by="MfgBomItem.line_no"
    )


class MfgBomItem(AuditMixin, UUIDModel):
    __tablename__ = "mfg_bom_item"

    bom_id: Mapped[str] = mapped_column(ForeignKey("mfg_bom.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False, default=1)
    bom: Mapped[MfgBom] = relationship(back_populates="items")


class MfgMps(AuditMixin, UUIDModel):
    __tablename__ = "mfg_mps"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    plan_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    runs: Mapped[list["MfgMrpRun"]] = relationship(back_populates="mps")


class MfgMrpRun(AuditMixin, UUIDModel):
    __tablename__ = "mfg_mrp_run"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    mps_id: Mapped[str] = mapped_column(ForeignKey("mfg_mps.id"), nullable=False)
    bom_id: Mapped[str] = mapped_column(ForeignKey("mfg_bom.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    source_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    mps: Mapped[MfgMps] = relationship(back_populates="runs")
    results: Mapped[list["MfgMrpResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="MfgMrpResult.material_id"
    )


class MfgMrpResult(AuditMixin, UUIDModel):
    __tablename__ = "mfg_mrp_result"

    run_id: Mapped[str] = mapped_column(ForeignKey("mfg_mrp_run.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    gross_requirement: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    available_stock: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    open_supply_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    net_requirement: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confirmed_source_ids: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    run: Mapped[MfgMrpRun] = relationship(back_populates="results")


class MfgWorkOrder(AuditMixin, UUIDModel):
    __tablename__ = "mfg_work_order"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    bom_id: Mapped[str] = mapped_column(String(36), nullable=False)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reported_good_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    reported_scrap_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    completed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    bom_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    materials: Mapped[list["MfgWorkOrderMaterial"]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan", order_by="MfgWorkOrderMaterial.line_no"
    )
    issues: Mapped[list["MfgMaterialIssue"]] = relationship(back_populates="work_order")
    reports: Mapped[list["MfgReport"]] = relationship(back_populates="work_order")


class MfgWorkOrderMaterial(AuditMixin, UUIDModel):
    __tablename__ = "mfg_work_order_material"

    work_order_id: Mapped[str] = mapped_column(ForeignKey("mfg_work_order.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    required_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    issued_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    returned_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False, default=1)
    work_order: Mapped[MfgWorkOrder] = relationship(back_populates="materials")


class MfgSubcontractOrder(AuditMixin, UUIDModel):
    __tablename__ = "mfg_subcontract_order"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    processing_fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    issues: Mapped[list["MfgMaterialIssue"]] = relationship(back_populates="subcontract_order")
    receipts: Mapped[list["MfgSubcontractReceipt"]] = relationship(
        back_populates="subcontract_order", order_by="MfgSubcontractReceipt.created_at"
    )


class MfgMaterialIssue(AuditMixin, UUIDModel):
    __tablename__ = "mfg_material_issue"
    __table_args__ = (UniqueConstraint("subcontract_order_id", name="uk_mfg_material_issue_subcontract_order"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    work_order_id: Mapped[str | None] = mapped_column(ForeignKey("mfg_work_order.id"), nullable=True)
    subcontract_order_id: Mapped[str | None] = mapped_column(ForeignKey("mfg_subcontract_order.id"), nullable=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    work_order: Mapped[MfgWorkOrder | None] = relationship(back_populates="issues")
    subcontract_order: Mapped[MfgSubcontractOrder | None] = relationship(back_populates="issues")
    items: Mapped[list["MfgMaterialIssueItem"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan", order_by="MfgMaterialIssueItem.line_no"
    )


class MfgMaterialIssueItem(AuditMixin, UUIDModel):
    __tablename__ = "mfg_material_issue_item"

    issue_id: Mapped[str] = mapped_column(ForeignKey("mfg_material_issue.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    returned_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False, default=1)
    issue: Mapped[MfgMaterialIssue] = relationship(back_populates="items")


class MfgSubcontractReceipt(AuditMixin, UUIDModel):
    __tablename__ = "mfg_subcontract_receipt"
    __table_args__ = (
        UniqueConstraint("org_id", "subcontract_order_id", "operation_key", name="uk_mfg_subcontract_receipt_operation"),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    subcontract_order_id: Mapped[str] = mapped_column(ForeignKey("mfg_subcontract_order.id"), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    good_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    processing_fee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    operation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    subcontract_order: Mapped[MfgSubcontractOrder] = relationship(back_populates="receipts")


class MfgMaterialReturn(AuditMixin, UUIDModel):
    __tablename__ = "mfg_material_return"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    work_order_id: Mapped[str] = mapped_column(ForeignKey("mfg_work_order.id"), nullable=False)
    issue_id: Mapped[str] = mapped_column(ForeignKey("mfg_material_issue.id"), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    items: Mapped[list["MfgMaterialReturnItem"]] = relationship(
        back_populates="material_return", cascade="all, delete-orphan", order_by="MfgMaterialReturnItem.line_no"
    )


class MfgMaterialReturnItem(AuditMixin, UUIDModel):
    __tablename__ = "mfg_material_return_item"

    return_id: Mapped[str] = mapped_column(ForeignKey("mfg_material_return.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False, default=1)
    material_return: Mapped[MfgMaterialReturn] = relationship(back_populates="items")


class MfgReport(AuditMixin, UUIDModel):
    __tablename__ = "mfg_work_report"

    work_order_id: Mapped[str] = mapped_column(ForeignKey("mfg_work_order.id"), nullable=False)
    good_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    scrap_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    report_time: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    work_order: Mapped[MfgWorkOrder] = relationship(back_populates="reports")
