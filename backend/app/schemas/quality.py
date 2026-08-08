from pydantic import BaseModel, Field

class InspectionCreate(BaseModel):
    inspection_type: str = Field(min_length=1, max_length=32)
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=36)

class QaPlanCreate(BaseModel): name: str=Field(min_length=1,max_length=128); items: list[dict]=Field(min_length=1)
class InspectionResult(BaseModel): item: str=Field(min_length=1); value: str=Field(min_length=1); passed: bool | None=None
