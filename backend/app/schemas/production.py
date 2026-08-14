from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field
from uuid import uuid4


class BomItemCreate(BaseModel):
    material_id: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    scrap_rate: Decimal = Field(default=Decimal("0"), ge=0, lt=1)
    issue_operation_id: str | None = Field(default=None, max_length=36)
    is_phantom: bool = False


class BomCreate(BaseModel):
    material_id: str = Field(min_length=1)
    bom_version: str = Field(default="1.0", min_length=1, max_length=32)
    effective_from: date
    effective_to: date | None = None
    source_type: str | None = Field(default=None, max_length=64)
    source_id: str | None = Field(default=None, max_length=36)
    items: list[BomItemCreate] = Field(min_length=1)


class MpsCreate(BaseModel):
    material_id: str = Field(min_length=1)
    warehouse_id: str | None = Field(default=None, min_length=1)
    plan_date: date
    plan_quantity: Decimal = Field(gt=0)
    source_type: str | None = Field(default=None, max_length=64)
    source_id: str | None = Field(default=None, max_length=36)


class WorkOrderCreate(BaseModel):
    material_id: str = Field(min_length=1)
    warehouse_id: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    plan_date: date
    routing_id: str | None = Field(default=None, min_length=1)
    source_type: str | None = Field(default=None, max_length=64)
    source_id: str | None = Field(default=None, max_length=36)


class SubcontractOrderCreate(BaseModel):
    supplier_id: str = Field(min_length=1)
    material_id: str = Field(min_length=1)
    warehouse_id: str = Field(min_length=1)
    plan_date: date
    quantity: Decimal = Field(gt=0)
    processing_fee: Decimal = Field(gt=0)
    source_type: str | None = Field(default=None, max_length=64)
    source_id: str | None = Field(default=None, max_length=36)


class MaterialMovementItem(BaseModel):
    material_id: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)


class MaterialIssueCreate(BaseModel):
    items: list[MaterialMovementItem] = Field(min_length=1)


class MaterialReturnCreate(BaseModel):
    items: list[MaterialMovementItem] = Field(min_length=1)


class WorkReportCreate(BaseModel):
    operation_id: str | None = Field(default=None, min_length=1)
    good_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    scrap_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    hours: Decimal = Field(default=Decimal("0"), ge=0)
    execution_key: str = Field(default_factory=lambda: f"report-{uuid4()}", min_length=1, max_length=128)


class WorkCenterCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    daily_capacity_hours: Decimal = Field(default=Decimal("8"), gt=0)
    efficiency_rate: Decimal = Field(default=Decimal("1"), gt=0, le=2)
    labor_rate: Decimal = Field(default=Decimal("0"), ge=0)
    overhead_rate: Decimal = Field(default=Decimal("0"), ge=0)


class WorkCenterUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    daily_capacity_hours: Decimal = Field(gt=0)
    efficiency_rate: Decimal = Field(gt=0, le=2)
    labor_rate: Decimal = Field(default=Decimal("0"), ge=0)
    overhead_rate: Decimal = Field(default=Decimal("0"), ge=0)
    status: str = Field(pattern="^(active|inactive)$")


class CapacityCalendarUpsert(BaseModel):
    work_center_id: str = Field(min_length=1)
    capacity_date: date
    available_hours: Decimal = Field(ge=0)
    note: str | None = Field(default=None, max_length=255)


class RoutingOperationCreate(BaseModel):
    work_center_id: str = Field(min_length=1)
    operation_name: str = Field(min_length=1, max_length=128)
    setup_hours: Decimal = Field(default=Decimal("0"), ge=0)
    run_hours_per_unit: Decimal = Field(default=Decimal("0"), ge=0)
    quality_plan_id: str | None = Field(default=None, max_length=36)
    equipment_requirement: str | None = Field(default=None, max_length=255)


class RoutingCreate(BaseModel):
    material_id: str = Field(min_length=1)
    bom_id: str = Field(min_length=1)
    routing_version: str = Field(default="1.0", min_length=1, max_length=32)
    effective_from: date
    effective_to: date | None = None
    operations: list[RoutingOperationCreate] = Field(min_length=1)


class SubcontractReceiptCreate(BaseModel):
    good_quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(gt=0)
    operation_key: str = Field(min_length=1, max_length=64)


class WorkOrderScheduleCreate(BaseModel):
    operation_id: str | None = Field(default=None, max_length=36)
    work_center_id: str = Field(min_length=1, max_length=36)
    schedule_date: date
    scheduled_hours: Decimal = Field(gt=0)
    override_capacity: bool = False


class AlternateMaterialCreate(BaseModel):
    material_id: str = Field(min_length=1, max_length=36)
    alternate_material_id: str = Field(min_length=1, max_length=36)
    conversion_rate: Decimal = Field(gt=0)
    reason: str | None = Field(default=None, max_length=255)


class WorkOrderExceptionCreate(BaseModel):
    exception_type: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=500)
    severity: str = Field(default="medium", pattern="^(low|medium|high|blocking)$")
    owner_id: str | None = Field(default=None, max_length=36)
    due_at: str | None = Field(default=None, max_length=32)


class WorkOrderExceptionResolve(BaseModel):
    resolution: str = Field(min_length=1, max_length=500)


class PlanRunCreate(BaseModel):
    plan_from: date
    plan_to: date
    warehouse_id: str | None = Field(default=None, max_length=36)
    demand_sources: list[str] = Field(default_factory=lambda: ["sales_order", "mps", "manual"])


class DemandLineCreate(BaseModel):
    material_id: str = Field(min_length=1, max_length=36)
    warehouse_id: str | None = Field(default=None, max_length=36)
    demand_date: date
    quantity: Decimal = Field(gt=0)
    source_type: str = Field(default="manual", min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=36)


class PlannedOrderCommand(BaseModel):
    planned_order_ids: list[str] = Field(min_length=1, max_length=200)
