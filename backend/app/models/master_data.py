from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, UUIDModel


class MdUnit(AuditMixin, UUIDModel):
    __tablename__ = "md_unit"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    precision_scale: Mapped[int] = mapped_column(default=2, nullable=False)


class MdTaxRate(AuditMixin, UUIDModel):
    __tablename__ = "md_tax_rate"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0, nullable=False)


class MdMaterial(AuditMixin, UUIDModel):
    __tablename__ = "md_material"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unit_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tax_rate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    material_type: Mapped[str] = mapped_column(String(32), default="goods", nullable=False)
    standard_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    sale_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    min_stock: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    max_stock: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    specification: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class MdCustomer(AuditMixin, UUIDModel):
    __tablename__ = "md_customer"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class MdSupplier(AuditMixin, UUIDModel):
    __tablename__ = "md_supplier"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credit_days: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class MdWarehouse(AuditMixin, UUIDModel):
    __tablename__ = "md_warehouse"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    manager_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
