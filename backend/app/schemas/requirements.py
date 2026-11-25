import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

RequirementType = Literal[
    "functional", "non_functional", "business_rule", "user_role", "permission", "validation",
    "dependency", "workflow", "acceptance_criteria", "constraint",
]  # fmt: skip
Priority = Literal["critical", "high", "medium", "low"]
RequirementStatus = Literal["draft", "approved", "rejected"]


def _clean_criteria(value: list[str]) -> list[str]:
    return [c.strip()[:1000] for c in value if c and c.strip()][:50]


class RequirementCreateIn(BaseModel):
    type: RequirementType
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=10000)
    module_id: uuid.UUID | None = None
    feature: str | None = Field(default=None, max_length=200)
    user_role: str | None = Field(default=None, max_length=120)
    priority: Priority = "medium"
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=50)

    _criteria = field_validator("acceptance_criteria")(_clean_criteria)

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title must not be blank")
        return v.strip()


class RequirementUpdateIn(BaseModel):
    type: RequirementType | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=10000)
    module_id: uuid.UUID | None = None
    clear_module: bool = False
    feature: str | None = Field(default=None, max_length=200)
    user_role: str | None = Field(default=None, max_length=120)
    priority: Priority | None = None
    acceptance_criteria: list[str] | None = Field(default=None, max_length=50)
    change_reason: str | None = Field(default=None, max_length=500)

    @field_validator("acceptance_criteria")
    @classmethod
    def _criteria(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _clean_criteria(v)


class RejectIn(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class BulkStatusIn(BaseModel):
    requirement_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    status: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=1000)


class ExtractIn(BaseModel):
    document_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    instructions: str | None = Field(default=None, max_length=2000)


class SourceRef(BaseModel):
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    document_title: str
    chunk_id: uuid.UUID | None = None
    page: int | None = None
    sheet: str | None = None
    char_start: int
    char_end: int
    quote: str


class RequirementVersionOut(BaseModel):
    id: uuid.UUID
    version: int
    type: str
    title: str
    description: str
    module_id: uuid.UUID | None
    feature: str | None
    user_role: str | None
    priority: str
    acceptance_criteria: list[str]
    source_refs: list[SourceRef]
    origin: str
    confidence: str | None
    change_reason: str | None
    created_by: uuid.UUID
    created_at: datetime


class RequirementOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    key: str
    status: str
    current_version_no: int
    approved_version_no: int | None
    possible_duplicate_of: uuid.UUID | None
    possible_duplicate_key: str | None
    rejection_reason: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    current: RequirementVersionOut


class RequirementDetailOut(RequirementOut):
    versions: list[RequirementVersionOut]


class FieldChange(BaseModel):
    field: str
    before: Any
    after: Any


class RequirementDiffOut(BaseModel):
    from_version: int
    to_version: int
    changes: list[FieldChange]
    description_diff: list[str]


class ContextSearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    module_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    expand_connected: bool = True
    k: int = Field(default=8, ge=1, le=30)


class ContextHit(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    document_title: str
    document_version: int
    module_id: uuid.UUID | None
    page: int | None
    sheet: str | None
    char_start: int
    char_end: int
    content: str
    score: float
    similarity: float | None
    lexical_rank: int | None


class AIStatusOut(BaseModel):
    llm: dict[str, Any]
    embeddings: dict[str, Any]
    ocr: dict[str, Any]
