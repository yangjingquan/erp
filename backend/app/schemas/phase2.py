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


class RevisionTransition(BaseModel):
    status: Literal["submitted", "effective", "obsolete"]


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


class SupplierScoreCreate(BaseModel):
    supplier_id: str = Field(min_length=1, max_length=36)
    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    delivery_score: Decimal = Field(ge=0, le=100)
    quality_score: Decimal = Field(ge=0, le=100)
    service_score: Decimal = Field(ge=0, le=100)
    evidence: dict = Field(default_factory=dict)


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


class MilestoneCreate(BaseModel):
    project_id: str = Field(min_length=1, max_length=36)
    wbs_id: str | None = None
    name: str = Field(min_length=2, max_length=255)
    due_date: date


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


class AssetUpdate(BaseModel):
    asset_name: str | None = Field(default=None, min_length=2, max_length=255)
    serial_no: str | None = None
    location: str | None = None
    status: Literal["active", "maintenance", "retired"] | None = None
    retirement_reason: str | None = Field(default=None, max_length=500)
    next_maintenance_date: date | None = None


class AssetWorkOrderCreate(BaseModel):
    asset_id: str = Field(min_length=1, max_length=36)
    service_type: Literal["repair", "maintenance", "inspection"] = "repair"
    description: str = Field(min_length=2, max_length=1000)
    due_date: date | None = None
    owner_id: str | None = Field(default=None, max_length=36)
    maintenance_plan_id: str | None = Field(default=None, max_length=36)


class AssetWorkOrderUpdate(BaseModel):
    owner_id: str | None = Field(default=None, max_length=36)
    due_date: date | None = None
    resolution: str | None = Field(default=None, max_length=1000)
    actual_hours: Decimal = Field(default=0, ge=0)
    parts_cost: Decimal = Field(default=0, ge=0)
    labor_cost: Decimal = Field(default=0, ge=0)


class AssetWorkOrderTransition(BaseModel):
    resolution: str | None = Field(default=None, max_length=1000)
    actual_hours: Decimal | None = Field(default=None, ge=0)
    parts_cost: Decimal | None = Field(default=None, ge=0)
    labor_cost: Decimal | None = Field(default=None, ge=0)


class MaintenancePlanCreate(BaseModel):
    asset_id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=2, max_length=255)
    interval_days: int = Field(default=30, ge=1, le=3650)
    next_due: date


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
    owner_id: str | None = Field(default=None, max_length=36)
    sla_hours: int | None = Field(default=48, ge=1, le=8760)


class ServiceCaseUpdate(BaseModel):
    owner_id: str | None = Field(default=None, max_length=36)
    due_date: date | None = None
    resolution: str | None = Field(default=None, max_length=1000)
    customer_feedback: str | None = Field(default=None, max_length=1000)
    satisfaction_score: int | None = Field(default=None, ge=1, le=5)


class ServiceCaseTransition(BaseModel):
    resolution: str | None = Field(default=None, max_length=1000)
    customer_feedback: str | None = Field(default=None, max_length=1000)
    satisfaction_score: int | None = Field(default=None, ge=1, le=5)


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


class MembershipUpdate(BaseModel):
    org_id: str = Field(min_length=1, max_length=36)
    membership_type: Literal["member", "admin", "viewer"] = "member"
    status: Literal["active", "inactive"] = "active"


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


class VisitUpdate(BaseModel):
    status: Literal["scheduled", "in_progress", "completed", "cancelled"]
    outcome: str | None = Field(default=None, max_length=1000)
    feedback_score: int | None = Field(default=None, ge=1, le=5)
