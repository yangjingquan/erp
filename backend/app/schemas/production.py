from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class BomItemCreate(BaseModel):
    material_id: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)


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


class WorkCenterCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    daily_capacity_hours: Decimal = Field(default=Decimal("8"), gt=0)
    efficiency_rate: Decimal = Field(default=Decimal("1"), gt=0, le=2)


class WorkCenterUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    daily_capacity_hours: Decimal = Field(gt=0)
    efficiency_rate: Decimal = Field(gt=0, le=2)
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
