import uuid
from datetime import datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator

from app.schemas.common import ORMModel

Platform = Literal["web", "android", "ios", "api", "multi_platform"]
RoleKey = Literal["owner", "admin", "qa_engineer", "viewer"]


def _clean_stack(value: list[str]) -> list[str]:
    seen: list[str] = []
    for item in value:
        item = item.strip()
        if item and item.lower() not in (s.lower() for s in seen):
            seen.append(item[:60])
    return seen


class ProjectBase(BaseModel):
    description: str = Field(default="", max_length=5000)
    project_type: str = Field(default="", max_length=80)
    application_url: AnyHttpUrl | None = None
    business_domain: str = Field(default="", max_length=120)
    tech_stack: list[str] = Field(default_factory=list, max_length=30)

    _stack = field_validator("tech_stack")(_clean_stack)


class ProjectCreateIn(ProjectBase):
    name: str = Field(min_length=1, max_length=120)
    platform: Platform

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name must not be blank")
        return v


class ProjectUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    project_type: str | None = Field(default=None, max_length=80)
    application_url: AnyHttpUrl | None = None
    platform: Platform | None = None
    business_domain: str | None = Field(default=None, max_length=120)
    tech_stack: list[str] | None = Field(default=None, max_length=30)

    @field_validator("tech_stack")
    @classmethod
    def _stack(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _clean_stack(v)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Name must not be blank")
        return v.strip() if v else v


class ProjectStats(BaseModel):
    members: int
    modules: int
    documents: int


class ProjectOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str
    project_type: str
    application_url: str | None
    platform: str
    business_domain: str
    tech_stack: list[str]
    status: str
    archived_at: datetime | None
    version: int
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    my_role: str
    stats: ProjectStats


class RoleOut(ORMModel):
    key: str
    name: str
    rank: int
    description: str


class MemberAddIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: RoleKey


class MemberUpdateIn(BaseModel):
    role: RoleKey


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    name: str
    role: str
    added_at: datetime


class ModuleCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=5000)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name must not be blank")
        return v


class ModuleUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)


class ModuleConnectionsIn(BaseModel):
    to_module_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)


class ModuleOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str
    version: int
    created_at: datetime
    updated_at: datetime
    connected_module_ids: list[uuid.UUID] = Field(default_factory=list)
