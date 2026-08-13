from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

class InspectionCreate(BaseModel):
    inspection_type: str = Field(min_length=1, max_length=32)
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=36)

class QaPlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    items: list[dict] = Field(min_length=1)


class QaDefectCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    severity: Literal["minor", "major", "critical"] = "major"
    status: Literal["active", "inactive"] = "active"


class InspectionFromPlanCreate(BaseModel):
    inspection_type: str = Field(min_length=1, max_length=32)
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=36)
    plan_id: str = Field(min_length=1, max_length=36)
    sample_size: int = Field(gt=0, le=100000)


class InspectionResult(BaseModel):
    item: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=500)
    passed: bool | None = None


class InspectionClose(BaseModel):
    disposition: Literal["rework", "accept", "scrap", "return_to_supplier"]


class NonconformanceInvestigationUpdate(BaseModel):
    severity: Literal["minor", "major", "critical"]
    disposition: Literal["rework", "accept", "scrap", "return_to_supplier"]
    owner_id: str = Field(min_length=1, max_length=36)
    due_date: date
    root_cause: str = Field(min_length=2, max_length=1000)


class CapaActionCreate(BaseModel):
    action_type: Literal["corrective", "preventive"]
    description: str = Field(min_length=2, max_length=500)
    owner_id: str = Field(min_length=1, max_length=36)
    due_date: date


class CapaActionComplete(BaseModel):
    completion_evidence: str = Field(min_length=2, max_length=1000)


class NonconformanceClose(BaseModel):
    closure_evidence: str = Field(min_length=2, max_length=1000)
