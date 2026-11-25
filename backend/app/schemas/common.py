from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.core.context import request_id_var

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PageMeta(BaseModel):
    cursor: str | None = None
    next_cursor: str | None = None
    limit: int


class Meta(BaseModel):
    request_id: str | None = None
    page: PageMeta | None = None


class Envelope(BaseModel, Generic[T]):
    data: T
    meta: Meta = Field(default_factory=Meta)


def ok(data: Any, page: dict[str, Any] | None = None) -> dict[str, Any]:
    """Wrap a payload in the standard success envelope."""
    return {"data": data, "meta": {"request_id": request_id_var.get(), "page": page}}
