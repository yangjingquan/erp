from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MasterBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)


class MaterialCreate(MasterBase):
    category: str | None = None
    unit_id: str | None = None
    tax_rate_id: str | None = None
    material_type: str = "goods"
    standard_cost: Decimal = Decimal("0")
    sale_price: Decimal = Decimal("0")
    purchase_price: Decimal = Decimal("0")
    min_stock: Decimal = Decimal("0")
    max_stock: Decimal = Decimal("0")
    specification: str | None = None


class CustomerCreate(MasterBase):
    short_name: str | None = None
    owner_id: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    credit_limit: Decimal = Decimal("0")


class SupplierCreate(MasterBase):
    short_name: str | None = None
    owner_id: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    credit_days: int = 0


class WarehouseCreate(MasterBase):
    manager_id: str | None = None
    address: str | None = None


class UnitCreate(MasterBase):
    precision_scale: int = 2


class TaxRateCreate(MasterBase):
    rate: Decimal = Decimal("0")
