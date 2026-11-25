import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

DocumentKind = Literal["requirement", "design", "business_logic", "api_spec", "test_cases", "screenshot", "other"]


class DocumentVersionOut(ORMModel):
    id: uuid.UUID
    version: int
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    processing_status: str
    processing_error: str | None
    uploaded_by: uuid.UUID
    created_at: datetime


class DocumentOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    kind: str
    module_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    current_version: DocumentVersionOut | None
    version_count: int


class DocumentDetailOut(DocumentOut):
    versions: list[DocumentVersionOut]


class DocumentUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    kind: DocumentKind | None = None
    module_id: uuid.UUID | None = None
    clear_module: bool = False


class ExtractionOut(ORMModel):
    id: uuid.UUID
    document_version_id: uuid.UUID
    extractor: str
    text: str
    char_count: int
    meta: dict[str, Any]
    created_at: datetime


class DownloadUrlOut(BaseModel):
    url: str
    expires_in: int


class JobOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    kind: str
    status: str
    progress: int
    stage: str | None
    result: dict[str, Any] | None
    error: str | None
    attempts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class UploadOut(BaseModel):
    document: DocumentDetailOut
    job: JobOut


class ActivityOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    actor_id: uuid.UUID | None
    actor_name: str | None = None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    summary: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    created_at: datetime


class DashboardTotals(BaseModel):
    projects: int
    active_projects: int
    archived_projects: int
    documents: int
    modules: int


class DashboardOut(BaseModel):
    totals: DashboardTotals
    recent_activity: list[ActivityOut]
    recent_jobs: list[JobOut]
