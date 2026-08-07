from datetime import datetime
from pydantic import BaseModel, Field

class LeadCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    phone: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=128)
    source: str | None = Field(default=None, max_length=64)

class OpportunityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    customer_id: str | None = None

class FollowUpCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    occurred_at: datetime
