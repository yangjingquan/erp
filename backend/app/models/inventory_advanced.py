from datetime import date
from decimal import Decimal

from sqlalchemy import JSON, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, UUIDModel


class InvZone(AuditMixin, UUIDModel):
    __tablename__ = "inv_zone"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (UniqueConstraint("warehouse_id", "code", name="uk_inv_zone_code"),)


class InvLocation(AuditMixin, UUIDModel):
    __tablename__ = "inv_location"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("inv_zone.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (UniqueConstraint("warehouse_id", "code", name="uk_inv_location_code"),)


class InvBatch(AuditMixin, UUIDModel):
    __tablename__ = "inv_batch"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(String(64), nullable=False)
    production_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (UniqueConstraint("org_id", "material_id", "batch_no", name="uk_inv_batch_material_no"),)


class InvCostLayer(AuditMixin, UUIDModel):
    __tablename__ = "inv_cost_layer"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("inv_location.id"), nullable=False, index=True)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("inv_batch.id"), nullable=True, index=True)
    inbound_transaction_id: Mapped[str] = mapped_column(ForeignKey("inv_stock_transaction.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    original_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)


class InvCostLayerConsumption(UUIDModel):
    __tablename__ = "inv_cost_layer_consumption"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    outbound_transaction_id: Mapped[str] = mapped_column(ForeignKey("inv_stock_transaction.id"), nullable=False, index=True)
    cost_layer_id: Mapped[str] = mapped_column(ForeignKey("inv_cost_layer.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)


class InvSlowMovingRule(AuditMixin, UUIDModel):
    __tablename__ = "inv_slow_moving_rule"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    material_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    threshold_days: Mapped[int] = mapped_column(nullable=False, default=90)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class InvWarehouseAccess(AuditMixin, UUIDModel):
    __tablename__ = "inv_warehouse_access"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    access_level: Mapped[str] = mapped_column(String(32), default="view", nullable=False)

    __table_args__ = (UniqueConstraint("warehouse_id", "user_id", name="uk_inv_warehouse_access_user"),)


class InvScanRecord(AuditMixin, UUIDModel):
    """Durable scanner idempotency record and original response snapshot."""

    __tablename__ = "inv_scan_record"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    scan_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (UniqueConstraint("org_id", "scan_id", name="uk_inv_scan_record_org_scan"),)


class InvReservation(AuditMixin, UUIDModel):
    """库存预留，统一扣减 available_quantity，避免订单/工单重复占用。"""

    __tablename__ = "inv_reservation"
    __table_args__ = (
        UniqueConstraint("org_id", "source_type", "source_id", "material_id", "warehouse_id", name="uk_inv_reservation_source_line"),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    released_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="reserved", nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class InvTraceEvent(AuditMixin, UUIDModel):
    """批次/物料正向与反向追溯事件。"""

    __tablename__ = "inv_trace_event"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("inv_batch.id"), nullable=True, index=True)
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("inv_stock_transaction.id"), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    location_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_time: Mapped[date | None] = mapped_column(Date, nullable=True)
