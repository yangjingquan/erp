from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import local_now
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


class MfgWorkCenter(AuditMixin, UUIDModel):
    __tablename__ = "mfg_work_center"
    __table_args__ = (UniqueConstraint("org_id", "code", name="uk_mfg_work_center_code"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    daily_capacity_hours: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=8, nullable=False)
    efficiency_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=1, nullable=False)
    labor_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    overhead_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class MfgCapacityCalendar(AuditMixin, UUIDModel):
    __tablename__ = "mfg_capacity_calendar"
    __table_args__ = (
        UniqueConstraint("org_id", "work_center_id", "capacity_date", name="uk_mfg_capacity_calendar_day"),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    work_center_id: Mapped[str] = mapped_column(ForeignKey("mfg_work_center.id"), nullable=False, index=True)
    capacity_date: Mapped[date] = mapped_column(Date, nullable=False)
    available_hours: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class MfgRouting(AuditMixin, UUIDModel):
    __tablename__ = "mfg_routing"
    __table_args__ = (
        UniqueConstraint("org_id", "bom_id", "routing_version", name="uk_mfg_routing_bom_version"),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    bom_id: Mapped[str | None] = mapped_column(ForeignKey("mfg_bom.id"), nullable=True, index=True)
    routing_version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    operations: Mapped[list["MfgRoutingOperation"]] = relationship(
        back_populates="routing", cascade="all, delete-orphan", order_by="MfgRoutingOperation.line_no"
    )


class MfgRoutingOperation(AuditMixin, UUIDModel):
    __tablename__ = "mfg_routing_operation"
    __table_args__ = (UniqueConstraint("routing_id", "line_no", name="uk_mfg_routing_operation_line"),)

    routing_id: Mapped[str] = mapped_column(ForeignKey("mfg_routing.id"), nullable=False, index=True)
    work_center_id: Mapped[str | None] = mapped_column(ForeignKey("mfg_work_center.id"), nullable=True, index=True)
    operation_name: Mapped[str] = mapped_column(String(128), nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False, default=1)
    setup_hours: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    run_hours_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    routing: Mapped[MfgRouting] = relationship(back_populates="operations")


class MfgWorkOrder(AuditMixin, UUIDModel):
    __tablename__ = "mfg_work_order"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    bom_id: Mapped[str] = mapped_column(String(36), nullable=False)
    routing_id: Mapped[str | None] = mapped_column(ForeignKey("mfg_routing.id"), nullable=True)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reported_good_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    reported_scrap_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    completed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    bom_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    routing_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    materials: Mapped[list["MfgWorkOrderMaterial"]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan", order_by="MfgWorkOrderMaterial.line_no"
    )
    issues: Mapped[list["MfgMaterialIssue"]] = relationship(back_populates="work_order")
    reports: Mapped[list["MfgReport"]] = relationship(back_populates="work_order")
    cost: Mapped["MfgWorkOrderCost | None"] = relationship(back_populates="work_order", uselist=False)


class MfgWorkOrderSchedule(AuditMixin, UUIDModel):
    __tablename__ = "mfg_work_order_schedule"
    __table_args__ = (UniqueConstraint("org_id", "work_order_id", "operation_id", name="uk_mfg_work_order_schedule_operation"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    work_order_id: Mapped[str] = mapped_column(ForeignKey("mfg_work_order.id"), nullable=False, index=True)
    operation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    work_center_id: Mapped[str] = mapped_column(ForeignKey("mfg_work_center.id"), nullable=False, index=True)
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_hours: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="planned", nullable=False)
    actual_hours: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class MfgAlternateMaterial(AuditMixin, UUIDModel):
    __tablename__ = "mfg_alternate_material"
    __table_args__ = (UniqueConstraint("org_id", "work_order_id", "material_id", "alternate_material_id", name="uk_mfg_alternate_material"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    work_order_id: Mapped[str] = mapped_column(ForeignKey("mfg_work_order.id"), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    alternate_material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    conversion_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="approved", nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class MfgWorkOrderException(AuditMixin, UUIDModel):
    __tablename__ = "mfg_work_order_exception"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    work_order_id: Mapped[str] = mapped_column(ForeignKey("mfg_work_order.id"), nullable=False, index=True)
    exception_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)
    reported_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(500), nullable=True)


class MfgWorkOrderCost(AuditMixin, UUIDModel):
    __tablename__ = "mfg_work_order_cost"
    __table_args__ = (UniqueConstraint("org_id", "work_order_id", name="uk_mfg_work_order_cost_order"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    work_order_id: Mapped[str] = mapped_column(ForeignKey("mfg_work_order.id"), nullable=False, index=True)
    material_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    overhead_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    subcontract_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    scrap_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    actual_unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    standard_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    variance_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    voucher_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="calculated", nullable=False)
    cost_detail_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    work_order: Mapped[MfgWorkOrder] = relationship(back_populates="cost")


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
    operation_id: Mapped[str | None] = mapped_column(ForeignKey("mfg_routing_operation.id"), nullable=True)
    operation_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    good_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    scrap_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    report_time: Mapped[datetime] = mapped_column(
        default=local_now, nullable=False
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    work_order: Mapped[MfgWorkOrder] = relationship(back_populates="reports")
