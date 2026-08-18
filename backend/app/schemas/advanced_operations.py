from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class CandidateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    phone: str | None = Field(default=None, max_length=64)
    position: str = Field(min_length=1, max_length=128)
    source: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=500)


class CandidateUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=32)
    note: str | None = Field(default=None, max_length=500)


class LifecycleCreate(BaseModel):
    employee_id: str = Field(min_length=1, max_length=36)
    event_type: str = Field(min_length=1, max_length=32)
    effective_date: date
    to_status: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=500)


class PerformanceCreate(BaseModel):
    employee_id: str = Field(min_length=1, max_length=36)
    period: str = Field(min_length=4, max_length=16)
    score: Decimal = Field(ge=0, le=100)
    rating: str = Field(default="pending", min_length=1, max_length=32)
    goals: list[dict] = Field(default_factory=list)
    comments: str | None = Field(default=None, max_length=1000)


class BenefitCreate(BaseModel):
    employee_id: str = Field(min_length=1, max_length=36)
    benefit_type: str = Field(min_length=1, max_length=64)
    amount: Decimal = Field(ge=0)
    effective_date: date
    note: str | None = Field(default=None, max_length=500)


class SpcCreate(BaseModel):
    inspection_id: str | None = Field(default=None, max_length=36)
    material_id: str = Field(min_length=1, max_length=36)
    metric: str = Field(min_length=1, max_length=128)
    sample_value: Decimal
    lsl: Decimal | None = None
    usl: Decimal | None = None
    cpk: Decimal | None = Field(default=None, ge=0)


class SpcExceptionInvestigation(BaseModel):
    severity: str = Field(default="major", min_length=1, max_length=32)
    disposition: str = Field(default="rework", min_length=1, max_length=32)
    owner_id: str = Field(min_length=1, max_length=36)
    due_date: date


class SpcExceptionContainment(BaseModel):
    containment_action: str = Field(min_length=2, max_length=1000)


class SpcExceptionRootCause(BaseModel):
    root_cause: str = Field(min_length=2, max_length=1000)


class SpcRetestCreate(BaseModel):
    sample_value: Decimal


class SpcExceptionClose(BaseModel):
    closure_evidence: str = Field(min_length=2, max_length=1000)


class SpcActionCreate(BaseModel):
    action_type: str = Field(min_length=1, max_length=32)
    description: str = Field(min_length=2, max_length=500)
    owner_id: str = Field(min_length=1, max_length=36)
    due_date: date


class SpcActionComplete(BaseModel):
    completion_evidence: str = Field(min_length=2, max_length=1000)


class SupplierQualityCreate(BaseModel):
    supplier_id: str = Field(min_length=1, max_length=36)
    period: str = Field(min_length=7, max_length=7)
    inspection_count: int = Field(ge=0)
    defect_count: int = Field(ge=0)
    score: Decimal = Field(ge=0, le=100)
    note: str | None = Field(default=None, max_length=500)


class QualityCostCreate(BaseModel):
    period: str = Field(min_length=7, max_length=7)
    cost_type: str = Field(min_length=1, max_length=32)
    amount: Decimal = Field(ge=0)
    source_id: str | None = Field(default=None, max_length=36)
    note: str | None = Field(default=None, max_length=500)


class CustomerClaimCreate(BaseModel):
    customer_id: str = Field(min_length=1, max_length=36)
    source_type: str | None = Field(default=None, max_length=64)
    source_id: str | None = Field(default=None, max_length=36)
    title: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(ge=0)


class CustomerClaimUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=32)
    root_cause: str | None = Field(default=None, max_length=1000)
    resolution: str | None = Field(default=None, max_length=1000)


class ShipmentCreate(BaseModel):
    source_type: str | None = Field(default=None, max_length=64)
    source_id: str | None = Field(default=None, max_length=36)
    carrier_name: str = Field(min_length=1, max_length=128)
    origin: str = Field(min_length=1, max_length=255)
    destination: str = Field(min_length=1, max_length=255)
    planned_date: date
    freight_amount: Decimal = Field(ge=0)
    note: str | None = Field(default=None, max_length=500)


class ShipmentTransition(BaseModel):
    status: str = Field(min_length=1, max_length=32)
    note: str | None = Field(default=None, max_length=500)


class OcrCreate(BaseModel):
    document_type: str = Field(min_length=1, max_length=64)
    source_file: str = Field(min_length=1, max_length=255)
    raw_text: str = Field(min_length=1, max_length=10000)
