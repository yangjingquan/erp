from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class PurchaseOrderItemCreate(BaseModel):
    material_id: str
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    warehouse_id: str | None = None
    tax_rate: Decimal = Field(default=0, ge=0)


class PurchaseOrderCreate(BaseModel):
    supplier_id: str
    order_date: date
    expected_date: date | None = None
    items: list[PurchaseOrderItemCreate] = Field(min_length=1)


class PurchaseOrderUpdate(PurchaseOrderCreate):
    pass


class PurchaseRequestItemCreate(BaseModel):
    material_id: str
    quantity: Decimal = Field(gt=0)
    estimated_price: Decimal = Field(ge=0, default=0)


class PurchaseRequestCreate(BaseModel):
    request_date: date
    supplier_id: str | None = None
    remark: str | None = None
    items: list[PurchaseRequestItemCreate] = Field(min_length=1)


class PurchaseRequestUpdate(PurchaseRequestCreate):
    pass


class PurchaseReturnCreate(BaseModel):
    source_receipt_id: str | None = None
    supplier_id: str
    warehouse_id: str
    return_date: date | None = None
    items: list[PurchaseOrderItemCreate] = Field(min_length=1)


class PurchaseReturnUpdate(PurchaseReturnCreate):
    pass
