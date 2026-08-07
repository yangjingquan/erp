from pydantic import BaseModel, Field
class ApiClientCreate(BaseModel):
    client_key: str = Field(min_length=3, max_length=64)
    scopes: list[str] = Field(min_length=1, max_length=50)
