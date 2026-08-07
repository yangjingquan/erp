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
    good_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    scrap_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    hours: Decimal = Field(default=Decimal("0"), ge=0)


class SubcontractReceiptCreate(BaseModel):
    good_quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(gt=0)
    operation_key: str = Field(min_length=1, max_length=64)
