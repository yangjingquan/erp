from datetime import date
from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class LocationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    status: str = Field(default="active", min_length=1, max_length=32)


class LocationUpdate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    status: str = Field(default="active", min_length=1, max_length=32)


class BatchCreate(BaseModel):
    batch_no: str = Field(min_length=1, max_length=64)
    production_date: date | None = None
    expiry_date: date | None = None
    status: str = Field(default="active", min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.production_date and self.expiry_date and self.expiry_date < self.production_date:
            raise ValueError("expiry_date must not precede production_date")
        return self


class BatchUpdate(BaseModel):
    batch_no: str = Field(min_length=1, max_length=64)
    production_date: date | None = None
    expiry_date: date | None = None
    status: str = Field(default="active", min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.production_date and self.expiry_date and self.expiry_date < self.production_date:
            raise ValueError("expiry_date must not precede production_date")
        return self


class FifoInboundCreate(BaseModel):
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=36)
    warehouse_id: str = Field(min_length=1)
    location_id: str = Field(min_length=1)
    material_id: str = Field(min_length=1)
    batch_id: str | None = None
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)


class FifoOutboundCreate(BaseModel):
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=36)
    warehouse_id: str = Field(min_length=1)
    location_id: str = Field(min_length=1)
    material_id: str = Field(min_length=1)
    batch_id: str | None = None
    quantity: Decimal = Field(gt=0)


class ReservationCreate(BaseModel):
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=36)
    material_id: str = Field(min_length=1, max_length=36)
    warehouse_id: str = Field(min_length=1, max_length=36)
    quantity: Decimal = Field(gt=0)
    note: str | None = Field(default=None, max_length=255)


class ScanItem(BaseModel):
    material_id: str = Field(min_length=1, max_length=36)
    quantity: Decimal = Field(gt=0)


class ScanProcessCreate(BaseModel):
    token: str = Field(min_length=1, max_length=4096)
    scan_id: str = Field(min_length=1, max_length=128)
    action: Literal["receive", "fill", "return", "count"]
    document_id: str = Field(min_length=1, max_length=36)
    warehouse_id: str = Field(min_length=1, max_length=36)
    location_id: str | None = Field(default=None, max_length=36)
    batch_id: str | None = Field(default=None, max_length=36)
    material_id: str | None = Field(default=None, max_length=36)
    quantity: Decimal | None = Field(default=None, gt=0)
    actual_quantity: Decimal | None = Field(default=None, ge=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)
    items: list[ScanItem] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_operation_payload(self):
        if self.action == "receive" and (not self.material_id or self.quantity is None or not self.location_id):
            raise ValueError("receive requires material_id, location_id and quantity")
        if self.action in {"fill", "return"} and not self.items and (not self.material_id or self.quantity is None):
            raise ValueError("fill/return requires items or material_id and quantity")
        if self.action == "count" and (not self.material_id or self.actual_quantity is None):
            raise ValueError("count requires material_id and actual_quantity")
        return self
