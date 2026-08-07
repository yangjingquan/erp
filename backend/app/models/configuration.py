from decimal import Decimal

from sqlalchemy import JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDModel


class CfgFieldDefinition(UUIDModel):
    __tablename__ = "cfg_field_definition"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    business_type: Mapped[str] = mapped_column(String(64), nullable=False)
    field_key: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    field_type: Mapped[str] = mapped_column(String(32), nullable=False)
    visible: Mapped[bool] = mapped_column(default=True, nullable=False)
    required: Mapped[bool] = mapped_column(default=False, nullable=False)
    readonly: Mapped[bool] = mapped_column(default=False, nullable=False)
    permission_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class CfgNumberRule(UUIDModel):
    __tablename__ = "cfg_number_rule"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_key: Mapped[str] = mapped_column(String(64), nullable=False)
    prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    date_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sequence_length: Mapped[int] = mapped_column(default=4, nullable=False)
    reset_cycle: Mapped[str] = mapped_column(String(16), default="day", nullable=False)
    current_date_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_sequence: Mapped[int] = mapped_column(default=0, nullable=False)


class CfgPrintTemplate(UUIDModel):
    __tablename__ = "cfg_print_template"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    business_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    template_html: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class CfgGlobalParameter(UUIDModel):
    __tablename__ = "cfg_global_parameter"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    parameter_key: Mapped[str] = mapped_column(String(128), nullable=False)
    parameter_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(32), default="string", nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
