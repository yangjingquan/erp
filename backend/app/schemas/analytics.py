from typing import Literal

from pydantic import BaseModel, Field


ReportKey = Literal["management_kpi", "operations_kpi"]


class ReportDefinitionCreate(BaseModel):
    report_key: ReportKey
    name: str = Field(min_length=2, max_length=128)
    description: str = Field(default="", max_length=500)
    parameters: dict = Field(default_factory=dict)


class ReportRunRequest(BaseModel):
    period: str | None = Field(default=None, pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")
    warehouse_id: str | None = Field(default=None, max_length=36)
