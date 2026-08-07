from decimal import Decimal

from pydantic import BaseModel, Field


class InventoryItem(BaseModel):
    material_id: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0)


class TransferCreate(BaseModel):
    from_warehouse_id: str = Field(min_length=1)
    to_warehouse_id: str = Field(min_length=1)
    items: list[InventoryItem] = Field(min_length=1)


class CountItem(BaseModel):
    material_id: str = Field(min_length=1)
    actual_quantity: Decimal = Field(ge=0)


class CountCreate(BaseModel):
    warehouse_id: str = Field(min_length=1)
    items: list[CountItem] = Field(min_length=1)
