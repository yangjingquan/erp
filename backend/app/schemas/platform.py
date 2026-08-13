from pydantic import BaseModel, Field
class ApiClientCreate(BaseModel):
    client_key: str = Field(min_length=3, max_length=64)
    scopes: list[str] = Field(min_length=1, max_length=50)


class EventSubscriptionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    endpoint_url: str = Field(min_length=8, max_length=500)
    event_types: list[str] = Field(min_length=1, max_length=100)
