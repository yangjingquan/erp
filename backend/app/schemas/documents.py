from pydantic import BaseModel, Field


class DocumentCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class DocumentCommand(BaseModel):
    command: str = Field(min_length=1, max_length=64)
    payload: dict = Field(default_factory=dict)

