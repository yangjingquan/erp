from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class SalesOrderItemCreate(BaseModel):
    material_id: str
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    warehouse_id: str | None = None
    tax_rate: Decimal = Field(default=0, ge=0, le=100)


class SalesOrderCreate(BaseModel):
    customer_id: str
    order_date: date
    expected_date: date | None = None
    remark: str | None = None
    items: list[SalesOrderItemCreate] = Field(min_length=1)


class SalesReturnCreate(BaseModel):
    source_delivery_id: str | None = None
    customer_id: str
    warehouse_id: str
    return_date: date | None = None
    items: list[SalesOrderItemCreate] = []


class SalesQuoteCreate(BaseModel):
    customer_id: str
    quote_date: date
    valid_until: date | None = None
    items: list[SalesOrderItemCreate] = Field(min_length=1)
