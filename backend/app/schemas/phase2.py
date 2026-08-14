from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ProductRevisionCreate(BaseModel):
    material_id: str = Field(min_length=1, max_length=36)
    revision: str = Field(min_length=1, max_length=32)
    effective_from: date | None = None
    effective_to: date | None = None
    change_summary: str = Field(default="", max_length=1000)
    snapshot: dict = Field(default_factory=dict)


class ChangeRequestCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    change_type: Literal["engineering", "quality", "supplier", "production"] = "engineering"
    description: str = Field(min_length=2, max_length=2000)
    due_date: date | None = None
    impact_snapshot: list[dict] = Field(default_factory=list)


class ChangeTransition(BaseModel):
    status: Literal["submitted", "approved", "rejected", "effective", "cancelled"]


class RfqCreate(BaseModel):
    supplier_id: str = Field(min_length=1, max_length=36)
    material_id: str = Field(min_length=1, max_length=36)
    quantity: Decimal = Field(gt=0)
    due_date: date | None = None


class RfqQuoteUpdate(BaseModel):
    quote_amount: Decimal = Field(gt=0)
    promised_date: date | None = None
    supplier_note: str = Field(default="", max_length=1000)


class ProjectCreate(BaseModel):
    project_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=2, max_length=255)
    customer_id: str | None = None
    budget_amount: Decimal = Field(default=0, ge=0)
    start_date: date | None = None
    end_date: date | None = None


class WbsCreate(BaseModel):
    project_id: str = Field(min_length=1, max_length=36)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=2, max_length=255)
    parent_id: str | None = None
    planned_amount: Decimal = Field(default=0, ge=0)


class ProjectEntryCreate(BaseModel):
    project_id: str = Field(min_length=1, max_length=36)
    wbs_id: str | None = None
    entry_date: date
    category: Literal["purchase", "labor", "inventory", "revenue", "expense"]
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=36)
    amount: Decimal = Field(gt=0)


class AssetCreate(BaseModel):
    asset_code: str = Field(min_length=1, max_length=64)
    asset_name: str = Field(min_length=2, max_length=255)
    serial_no: str | None = None
    location: str | None = None
    next_maintenance_date: date | None = None


class AssetWorkOrderCreate(BaseModel):
    asset_id: str = Field(min_length=1, max_length=36)
    service_type: Literal["repair", "maintenance", "inspection"] = "repair"
    description: str = Field(min_length=2, max_length=1000)
    due_date: date | None = None


class ServiceContractCreate(BaseModel):
    customer_id: str = Field(min_length=1, max_length=36)
    start_date: date
    end_date: date
    value: Decimal = Field(default=0, ge=0)


class ServiceCaseCreate(BaseModel):
    customer_id: str = Field(min_length=1, max_length=36)
    contract_id: str | None = None
    title: str = Field(min_length=2, max_length=255)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    due_date: date | None = None


class InvoiceCreate(BaseModel):
    invoice_type: Literal["input", "output", "credit"] = "output"
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=36)
    party_id: str = Field(min_length=1, max_length=36)
    amount: Decimal = Field(gt=0)
    tax_amount: Decimal = Field(default=0, ge=0)
    tax_code: str | None = None


class IntercompanyCreate(BaseModel):
    from_org_id: str = Field(min_length=1, max_length=36)
    to_org_id: str = Field(min_length=1, max_length=36)
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=36)
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="CNY", min_length=3, max_length=8)


class MembershipCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=36)
    org_id: str = Field(min_length=1, max_length=36)
    membership_type: Literal["member", "admin", "viewer"] = "member"


class LeaveRequestCreate(BaseModel):
    employee_id: str = Field(min_length=1, max_length=36)
    leave_type: str = Field(min_length=1, max_length=64)
    start_date: date
    end_date: date
    reason: str = Field(default="", max_length=500)


class LowCodeCreate(BaseModel):
    object_key: str = Field(min_length=2, max_length=128)
    name: str = Field(min_length=2, max_length=128)
    definition_schema: dict = Field(default_factory=dict, alias="schema")
    workflow: dict = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class MetricCreate(BaseModel):
    metric_key: str = Field(min_length=2, max_length=128)
    name: str = Field(min_length=2, max_length=128)
    formula: str = Field(min_length=2, max_length=1000)
    target: Decimal | None = None


class AlertResolve(BaseModel):
    resolution: str = Field(min_length=2, max_length=1000)


class VisitCreate(BaseModel):
    case_id: str = Field(min_length=1, max_length=36)
    scheduled_at: datetime
    technician_id: str | None = None
    notes: str = Field(default="", max_length=1000)
