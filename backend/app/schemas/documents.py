from pydantic import BaseModel, ConfigDict, Field


class DocumentSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class DocumentCommentCreate(DocumentSchema):
    content: str = Field(min_length=1, max_length=2000)


class DocumentCommand(DocumentSchema):
    command: str = Field(min_length=1, max_length=64)
    payload: dict = Field(default_factory=dict)


class DocumentBulkCommand(DocumentSchema):
    business_type: str = Field(min_length=1, max_length=64)
    business_ids: list[str] = Field(min_length=1, max_length=100)
    command: str = Field(min_length=1, max_length=64)
    payload: dict = Field(default_factory=dict)


class SavedViewCreate(DocumentSchema):
    name: str = Field(min_length=1, max_length=128)
    business_type: str | None = Field(default=None, max_length=64)
    filters: dict = Field(default_factory=dict)
    is_shared: bool = False


class DocumentExportCreate(DocumentSchema):
    business_type: str | None = Field(default=None, max_length=64)
    filters: dict = Field(default_factory=dict)
