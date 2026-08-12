from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.core.time import local_today


class AllocationItem(BaseModel):
    project_id: str = Field(min_length=1, max_length=36)
    quantity: Decimal = Field(default=Decimal("0"), ge=0)
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    hours: Decimal = Field(default=Decimal("0"), ge=0)


class CostAllocationCreate(BaseModel):
    allocation_date: date = Field(default_factory=local_today)
    amount: Decimal = Field(gt=0)
    basis: Literal["quantity", "amount", "hours"]
    source_type: str = Field(default="expense", min_length=1, max_length=64)
    source_id: str = Field(default="", max_length=36)
    idempotency_key: str | None = Field(default=None, max_length=128)
    items: list[AllocationItem] = Field(min_length=1, max_length=500)
